# -*- coding: utf-8 -*-
"""Servicios JSON del portal de obra, versión 1 (requerimiento CREVAL v1.0,
4.11). Los usan las pantallas del portal y los podrá usar una aplicación
nativa sin cambios en Odoo.

* ``POST /construction/api/v1/login`` y ``/pin``: usuario y clave, o QR de la
  obra con nombre y PIN; devuelven el token del portal.
* El resto pide ``Authorization: Bearer <token>``. El token vale solo aquí.
* Errores: 401 sin token válido, 403 sin permiso, 422 cuando una regla
  rechaza el registro (el motivo va en ``error``)."""
import logging
import re
from functools import wraps

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)
PREFIX = '/construction/api/v1'


def _json(data, status=200):
    return request.make_json_response(data, status=status)


def _body():
    try:
        return request.get_json_data() or {}
    except ValueError:
        return {}


def portal_api(func):
    """Autentica con el token del portal y traduce los errores a JSON."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        header = request.httprequest.headers.get('Authorization', '')
        match = re.match(r'^bearer\s+(.+)$', header, re.IGNORECASE)
        user = request.env['construction.portal.token']._check(match.group(1) if match else '')
        if not user:
            return _json({'error': 'Sesión vencida o no válida: vuelva a ingresar.'}, 401)
        request.update_env(user=user.id)
        try:
            return _json(func(self, *args, **kwargs))
        except AccessError as error:
            request.env.cr.rollback()
            return _json({'error': error.args[0] if error.args else str(error)}, 403)
        except (UserError, ValidationError) as error:
            request.env.cr.rollback()
            return _json({'error': error.args[0] if error.args else str(error)}, 422)
    return wrapper


class ConstructionPortalApi(http.Controller):

    def _service(self):
        return request.env['construction.portal.service']

    # ------------------------------------------------------------------
    # Ingreso
    # ------------------------------------------------------------------
    @http.route(PREFIX + '/login', type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False)
    def login(self, **kw):
        body = _body()
        wsgienv = {
            'interactive': True,
            'base_location': request.httprequest.url_root.rstrip('/'),
            'HTTP_HOST': request.httprequest.environ.get('HTTP_HOST'),
            'REMOTE_ADDR': request.httprequest.environ.get('REMOTE_ADDR'),
        }
        credential = {'login': body.get('login') or '', 'password': body.get('password') or '',
                      'type': 'password'}
        try:
            info = request.env(user=None, su=False)['res.users'].authenticate(credential, wsgienv)
        except AccessDenied:
            return _json({'error': 'Usuario o clave incorrectos.'}, 401)
        user = request.env['res.users'].sudo().browse(info['uid'])
        members = request.env['construction.portal.member'].sudo().search([
            ('user_id', '=', user.id), ('active', '=', True),
            ('project_id.construction_portal_password_login', '=', True)])
        if not members:
            return _json({'error': 'Su usuario no está en el portal de ninguna obra.'}, 403)
        token, expiration = request.env['construction.portal.token']._issue(
            user, 'password', body.get('device'))
        return _json({'token': token, 'expiration': expiration.isoformat(), 'name': user.name})

    @http.route(PREFIX + '/site/<string:code>', type='http', auth='public', methods=['GET'],
                csrf=False, save_session=False)
    def site(self, code, **kw):
        """Obra del QR y su personal (para elegir el nombre)."""
        project = request.env['project.project']._construction_portal_by_code(code)
        if not project:
            return _json({'error': 'El QR no es de una obra con ingreso por QR.'}, 404)
        members = project.construction_portal_member_ids.filtered('active')
        roles = dict(members._fields['role']._description_selection(request.env))
        return _json({'project': project.display_name, 'members': [
            {'id': member.id, 'name': member.name,
             'role': '%s%s' % (roles.get(member.role), (' · %s' % member.partner_id.name)
                               if member.partner_id else ''),
             'locked': member.pin_locked}
            for member in members.sorted('name')]})

    @http.route(PREFIX + '/pin', type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False)
    def pin(self, **kw):
        body = _body()
        project = request.env['project.project']._construction_portal_by_code(body.get('code'))
        member = project.construction_portal_member_ids.filtered(
            lambda m: m.id == int(body.get('member_id') or 0) and m.active) if project else False
        if not member:
            return _json({'error': 'Elija su nombre en la lista de la obra.'}, 404)
        if member.sudo().pin_locked:
            return _json({'error': 'Su ingreso por QR está bloqueado: pida al residente que lo '
                                   'desbloquee.'}, 403)
        if not member._check_pin(body.get('pin')):
            # El contador de PIN errados se guarda aunque falle el ingreso
            # (si no, tres intentos nunca bloquearían).
            request.env.cr.commit()  # pylint: disable=invalid-commit
            if member.sudo().pin_locked:
                return _json({'error': 'Tres PIN errados: su ingreso por QR quedó bloqueado.'},
                             403)
            return _json({'error': 'PIN incorrecto.'}, 401)
        token, expiration = request.env['construction.portal.token']._issue(
            member.user_id, 'qr', body.get('device'))
        return _json({'token': token, 'expiration': expiration.isoformat(),
                      'name': member.name})

    @http.route(PREFIX + '/logout', type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False)
    @portal_api
    def logout(self, **kw):
        header = request.httprequest.headers.get('Authorization', '')
        token = header.split(' ', 1)[-1]
        request.env['construction.portal.token'].sudo().search([
            ('token_hash', '=', request.env['construction.portal.token']._hash_token(token))
        ]).unlink()
        return {'status': 'done'}

    # ------------------------------------------------------------------
    # Datos y registros
    # ------------------------------------------------------------------
    @http.route(PREFIX + '/me', type='http', auth='public', methods=['GET'], csrf=False,
                save_session=False)
    @portal_api
    def me(self, **kw):
        return self._service().me()

    @http.route(PREFIX + '/sync/<int:project_id>', type='http', auth='public', methods=['GET'],
                csrf=False, save_session=False)
    @portal_api
    def sync(self, project_id, **kw):
        return self._service().sync(project_id)

    @http.route(PREFIX + '/progress', type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False)
    @portal_api
    def progress(self, **kw):
        return self._service().progress(_body())

    @http.route(PREFIX + '/daily-report', type='http', auth='public', methods=['POST'],
                csrf=False, save_session=False)
    @portal_api
    def daily_report(self, **kw):
        return self._service().daily_report(_body())

    @http.route(PREFIX + '/crew-day', type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False)
    @portal_api
    def crew_day(self, **kw):
        return self._service().crew_day(_body())

    @http.route(PREFIX + '/material-request', type='http', auth='public', methods=['POST'],
                csrf=False, save_session=False)
    @portal_api
    def material_request(self, **kw):
        return self._service().material_request(_body())

    @http.route(PREFIX + '/reception', type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False)
    @portal_api
    def reception(self, **kw):
        return self._service().reception(_body())

    @http.route(PREFIX + '/return', type='http', auth='public', methods=['POST'], csrf=False,
                save_session=False)
    @portal_api
    def return_material(self, **kw):
        return self._service().return_material(_body())

    @http.route(PREFIX + '/valuations/<int:project_id>', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False)
    @portal_api
    def valuations(self, project_id, **kw):
        return self._service().valuations(project_id)

    @http.route(PREFIX + '/valuation/<int:project_id>/<int:settlement_id>', type='http',
                auth='public', methods=['GET'], csrf=False, save_session=False)
    @portal_api
    def valuation(self, project_id, settlement_id, **kw):
        return self._service().valuation(project_id, settlement_id)
