# -*- coding: utf-8 -*-
"""Material extra desde el portal de obra (v1.6, M16-06): el capataz de la
contrata pide material de su obra; queda un requerimiento de obra en
borrador para la jefatura."""
import base64

from markupsafe import Markup

from odoo import _, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.al_construction_planner.models.construction_resource_plan import OPEN_STATES
from odoo.addons.al_construction_planner_subcontract.controllers.portal import (
    MAX_PHOTO_BYTES, ConstructionPortal,
)


class ConstructionPortalExtra(ConstructionPortal):

    # ------------------------------------------------------------------
    # Material extra (v1.6, M16-06)
    # ------------------------------------------------------------------
    def _construction_extra_scope(self, project_id):
        """Niveles donde trabaja la empresa del usuario en la obra (los de sus
        líneas y todos los superiores: piso, ambiente, partida, spool…; v1.7,
        M17-16) y los materiales del plan vigente de esa obra (no todo el
        catálogo)."""
        lines = self._construction_lines([('project_id', '=', project_id)])
        ids = {int(i) for path in lines.mapped('task_path') for i in (path or '').split('/') if i}
        places = lines.task_id.browse(ids).filtered(
            lambda t: t.construction_level != 'module').sorted(
            lambda t: (t.construction_path or '', t.id))
        # sudo: el usuario portal no lee el plan; solo los productos de las
        # líneas de material del plan vigente de una obra donde trabaja.
        materials_sudo = request.env['construction.resource.plan.line'].sudo().search([
            ('project_id', '=', project_id), ('resource_type', '=', 'material'),
            ('product_id', '!=', False), ('plan_id.state', 'in', OPEN_STATES)]).product_id
        return lines, places, materials_sudo.sorted('display_name')

    @http.route(['/my/obra/material'], type='http', auth='user', website=True,
                methods=['GET', 'POST'])
    def portal_construction_extra(self, project_id=None, **post):
        """El capataz pide material extra: queda un requerimiento de obra en
        borrador, marcado como extra con su motivo, ligado a su obra, piso y
        ambiente, sin reservar stock, y una actividad a la jefatura."""
        projects = self._construction_lines().project_id
        try:
            project_id = int(project_id or 0) or projects[:1].id
        except ValueError:
            return request.redirect('/my/obra')
        project = projects.filtered(lambda p: p.id == project_id)
        if not project:
            return request.redirect('/my/obra')
        _lines, places, products = self._construction_extra_scope(project.id)
        error, done = None, None
        if request.httprequest.method == 'POST':
            try:
                done = self._construction_create_extra(project, places, products, post)
            except (UserError, ValidationError) as exc:
                request.env.cr.rollback()
                error = exc.args[0] if exc.args else str(exc)
        reasons = request.env['construction.material.request']._fields['extra_reason']
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'construction_extra', 'project': project, 'projects': projects,
            'places': places, 'products': products, 'error': error, 'done': done,
            'reasons': reasons._description_selection(request.env),
        })
        return request.render('al_construction_planner_subcontract_purchase.portal_construction_extra', values)

    def _construction_create_extra(self, project, places, products, post):
        place = places.filtered(lambda t: str(t.id) == str(post.get('task_id')))
        if not place:
            raise UserError(_('Elija el nivel de la obra donde se usa el material.'))
        product = products.filtered(lambda p: str(p.id) == str(post.get('product_id')))
        if not product:
            raise UserError(_('Elija el material.'))
        try:
            qty = float((post.get('qty') or '').replace(',', '.'))
        except ValueError:
            raise UserError(_('Cantidad no válida.'))
        if qty <= 0:
            raise UserError(_('La cantidad debe ser mayor que cero.'))
        reason = post.get('reason')
        Request_model = request.env['construction.material.request']
        if reason not in dict(Request_model._fields['extra_reason']._description_selection(request.env)):
            raise UserError(_('Elija el motivo del pedido extra.'))
        note = (post.get('note') or '').strip()
        upload = request.httprequest.files.get('photo')
        photo = None
        if upload and upload.filename:
            content = upload.read()
            if len(content) > MAX_PHOTO_BYTES:
                raise UserError(_('La foto %s pesa más de 12 MB.', upload.filename))
            photo = (upload.filename, content, upload.mimetype)
        # sudo: el usuario portal no tiene acceso a los requerimientos de obra;
        # se crea en borrador (sin reservar stock) en una obra, un nivel y un
        # material de su alcance, filtrados arriba.
        Request_sudo = Request_model.sudo()
        extra_sudo = Request_sudo.create({
            'project_id': project.id,
            'company_id': project.company_id.id or request.env.company.id,
            'task_id': place.id,
            'requested_by': request.env.user.id,
            'is_extra': True,
            'extra_reason': reason,
            'note': note and Markup('<p>%s</p>') % note,
            'line_ids': [(0, 0, {'product_id': product.id, 'product_qty': qty})],
        })
        if photo:
            request.env['ir.attachment'].sudo().create({
                'name': photo[0], 'datas': base64.b64encode(photo[1]), 'mimetype': photo[2],
                'res_model': 'construction.material.request', 'res_id': extra_sudo.id,
            })
        extra_sudo.message_post(body=_(
            'Material extra pedido desde el portal por %s.', request.env.user.name))
        reviewer = project.user_id or request.env.ref(
            'al_construction_planner.group_planner_project_head').sudo().user_ids[:1]
        if reviewer:
            extra_sudo.activity_schedule(
                'mail.mail_activity_data_todo', user_id=reviewer.id,
                summary=_('Revisar el material extra pedido desde el portal'))
        return extra_sudo
