# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        """Apaga el modo desarrollador si los roles del usuario lo bloquean.

        Se hace en el servidor en cada petición: aunque se abra ?debug=1, la
        sesión queda sin debug.

        La página del cliente web (``/odoo``) es ``auth='none'``: aquí todavía
        no tiene usuario en el entorno (el controlador lo pone después), así
        que se usa el de la sesión. Solo sirve para apagar el debug, nunca
        para dar acceso.
        """
        super()._pre_dispatch(rule, args)
        if not (request.session.debug and request.session.uid and request.env is not None):
            return
        env = request.env
        if not env.uid:
            env = env(user=request.session.uid)
            if not env.user.exists():
                return
        restrictions = env['al.user.role']._al_ui_restrictions()
        if restrictions and restrictions['block_debug']:
            request.session.debug = ''
            # Para avisar al usuario una vez (lo consume session_info).
            request.session['al_debug_blocked'] = True

    def session_info(self):
        """Reaplica los roles para las compañías activas (cookie ``cids``).

        Un rol limitado a una compañía aplica solo si es para todas las
        compañías seleccionadas en el selector de compañías.
        """
        result = super().session_info()
        # sudo: el usuario de la sesión no puede escribir sus propios grupos.
        user_sudo = self.env.user.sudo()
        if request and user_sudo.al_role_line_ids:
            cids = request.httprequest.cookies.get('cids') or str(self.env.company.id)
            company_ids = [int(cid) for cid in cids.replace(',', '-').split('-') if cid.isdigit()]
            user_sudo.with_context(al_active_company_ids=company_ids)._al_apply_roles()
        result['al_role_restrictions'] = self._al_role_restrictions_session()
        if request and request.session.get('al_debug_blocked'):
            # Se avisa una sola vez por intento de activar el debug.
            del request.session['al_debug_blocked']
            result['al_role_restrictions']['debug_blocked_notice'] = True
        return result

    def _al_role_restrictions_session(self):
        """Lo que el cliente web necesita: ocultar Exportar y Archivar, y
        quitar "Activar modo desarrollador" de la paleta de comandos y
        "Enviar mensaje" del chatter."""
        restrictions = self.env['al.user.role']._al_ui_restrictions()
        if not restrictions:
            return {}
        return {
            'block_debug': restrictions['block_debug'],
            'hide_send_message': restrictions['hide_send_message'],
            'readonly_all': restrictions['readonly_all'],
            'models': {
                model: {
                    'hide_export': spec['hide_export'],
                    'hide_archive': spec['hide_archive'] or spec['is_readonly'],
                }
                for model, spec in restrictions['models'].items()
                if spec['hide_export'] or spec['hide_archive'] or spec['is_readonly']
            },
        }
