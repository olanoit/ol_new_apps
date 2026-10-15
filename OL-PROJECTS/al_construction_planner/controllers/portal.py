# -*- coding: utf-8 -*-
"""Portal de obra (v1.5, fase 16): contratas y capataces registran el avance
desde el celular, con fotos y ubicación; los supervisores validan en el
planificador.

Los usuarios portal no tienen acceso a los modelos del planificador: el
controlador lee con sudo solo lo de la empresa del usuario (las líneas del
plan vigente asignadas a ella) y crea el avance a su nombre, con origen
«Portal de obra». Lo que no es suyo no aparece y no se puede reportar.
"""
import base64

from markupsafe import Markup

from odoo import _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.common import DRIVER_TYPES
from ..models.construction_resource_plan import OPEN_STATES

MAX_PHOTO_BYTES = 12 * 1024 * 1024


class ConstructionPortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Alcance del usuario
    # ------------------------------------------------------------------
    def _construction_partner(self):
        return request.env.user.partner_id.commercial_partner_id

    def _construction_lines(self, extra_domain=None):
        """Líneas del plan vigente asignadas a la empresa del usuario."""
        # sudo: el usuario portal no lee el plan; el dominio lo limita a sus
        # líneas (contrata = su empresa) en planes vigentes.
        Line_sudo = request.env['construction.resource.plan.line'].sudo()
        domain = [('partner_id', 'child_of', self._construction_partner().id),
                  ('resource_type', 'in', DRIVER_TYPES), ('activity_id', '!=', False),
                  ('task_id', '!=', False), ('plan_id.state', 'in', OPEN_STATES)]
        return Line_sudo.search(domain + (extra_domain or []))

    def _construction_progress(self):
        # sudo: solo los avances de las líneas de la empresa del usuario.
        return request.env['construction.task.progress'].sudo().search([
            ('partner_id', 'child_of', self._construction_partner().id)],
            order='date desc, id desc', limit=200)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'construction_line_count' in counters:
            values['construction_line_count'] = len(self._construction_lines()) \
                if not request.env.user._is_public() else 0
        return values

    # ------------------------------------------------------------------
    # P-23 · Mis obras y tareas
    # ------------------------------------------------------------------
    @http.route(['/my/obra'], type='http', auth='user', website=True)
    def portal_my_construction(self, **kw):
        lines = self._construction_lines()
        rows = {}
        for line in lines.sorted(lambda l: (l.project_id.name or '', l.floor_task_id.sequence,
                                            l.floor_task_id.name or '', l.apartment_task_id.name or '',
                                            l.activity_id.name or '')):
            key = (line.project_id, line.activity_id)
            row = rows.setdefault(key, {
                'project': line.project_id, 'activity': line.activity_id, 'units': set(),
                'planned': 0.0, 'executed': 0.0, 'pending': 0.0, 'uom': line.product_uom_id})
            row['units'].add(line.apartment_task_id.id or line.task_id.id)
            row['planned'] += line.qty_planned
            row['executed'] += line.qty_executed
            row['pending'] += line._get_reported_qty()
        values = self._prepare_portal_layout_values()
        values.update({'page_name': 'construction', 'rows': list(rows.values()),
                       'partner': self._construction_partner()})
        return request.render('al_construction_planner.portal_my_construction', values)

    # ------------------------------------------------------------------
    # P-24 · Registrar avance
    # ------------------------------------------------------------------
    @http.route(['/my/obra/avance'], type='http', auth='user', website=True,
                methods=['GET', 'POST'])
    def portal_construction_progress(self, project_id=None, activity_id=None, **post):
        try:
            project_id, activity_id = int(project_id or 0), int(activity_id or 0)
        except ValueError:
            return request.redirect('/my/obra')
        lines = self._construction_lines([('project_id', '=', project_id),
                                          ('activity_id', '=', activity_id)])
        if not lines:
            return request.redirect('/my/obra')
        activity = lines.activity_id[:1]
        error, done = None, None
        if request.httprequest.method == 'POST':
            try:
                done = self._construction_register(lines, activity, post)
            except (UserError, ValidationError) as exc:
                request.env.cr.rollback()
                error = exc.args[0] if exc.args else str(exc)
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'construction_progress', 'activity': activity,
            'project': lines.project_id[:1], 'lines': lines.sorted(
                lambda l: (l.floor_task_id.sequence, l.apartment_task_id.name or '',
                           l.task_id.name or '')),
            'tranches': activity.tranche_ids, 'error': error, 'done': done,
            'today': fields.Date.context_today(request.env.user),
        })
        return request.render('al_construction_planner.portal_construction_progress', values)

    def _construction_register(self, lines, activity, post):
        """Crea los avances de las cantidades escritas, con las fotos subidas
        y la ubicación del celular."""
        files = [f for f in request.httprequest.files.getlist('photos') if f and f.filename]
        if not files:
            raise UserError(_('Tome o suba al menos una foto del avance.'))
        tranche = False
        if activity.tranche_ids:
            # sudo: el tramo es del catálogo de la actividad de su línea.
            tranche = activity.sudo().tranche_ids.filtered(
                lambda t: str(t.id) == str(post.get('tranche_id')))
            if not tranche:
                raise UserError(_('Elija el tramo que reporta.'))
        quantities = {}
        for line in lines:
            raw = (post.get('qty_%s' % line.id) or '').replace(',', '.').strip()
            if raw:
                try:
                    qty = float(raw)
                except ValueError:
                    raise UserError(_('Cantidad no válida: %s', raw))
                if qty < 0:
                    raise UserError(_('La cantidad no puede ser negativa.'))
                if qty:
                    quantities[line] = qty
        if not quantities:
            raise UserError(_('Escriba la cantidad avanzada en al menos una unidad.'))
        try:
            latitude = float(post.get('latitude') or 0.0)
            longitude = float(post.get('longitude') or 0.0)
        except ValueError:
            latitude = longitude = 0.0
        date = fields.Date.to_date(post.get('date')) or fields.Date.context_today(request.env.user)
        photos = []
        for upload in files:
            content = upload.read()
            if len(content) > MAX_PHOTO_BYTES:
                raise UserError(_('La foto %s pesa más de 12 MB.', upload.filename))
            photos.append((upload.filename, content, upload.mimetype))
        # sudo: el avance lo crea la contrata desde el portal sobre sus
        # propias líneas (filtradas arriba); queda «Por validar».
        Progress_sudo = request.env['construction.task.progress'].sudo()
        Attachment_sudo = request.env['ir.attachment'].sudo()
        created = Progress_sudo
        for line, qty in quantities.items():
            # Cada avance es dueño de sus fotos (como el asistente interno).
            attachments = Attachment_sudo.create([{
                'name': name, 'datas': base64.b64encode(content), 'mimetype': mimetype,
                'res_model': 'construction.task.progress', 'res_id': 0,
            } for name, content, mimetype in photos])
            progress = Progress_sudo.create({
                'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
                'plan_line_id': line.id, 'date': date, 'qty': qty,
                'tranche_id': tranche.id if tranche else False,
                'reported_by_id': request.env.user.id, 'source': 'portal',
                'latitude': latitude, 'longitude': longitude,
                'attachment_ids': [(6, 0, attachments.ids)],
            })
            attachments.write({'res_id': progress.id})
            created |= progress
        return created

    # ------------------------------------------------------------------
    # P-25 · Mis avances y liquidaciones
    # ------------------------------------------------------------------
    @http.route(['/my/obra/avances'], type='http', auth='user', website=True)
    def portal_my_construction_progress(self, **kw):
        # sudo: solo las liquidaciones de la empresa del usuario.
        settlements = request.env['construction.contract.settlement'].sudo().search([
            ('partner_id', 'child_of', self._construction_partner().id)],
            order='period_end desc, id desc', limit=60)
        values = self._prepare_portal_layout_values()
        values.update({'page_name': 'construction_history',
                       'progresses': self._construction_progress(), 'settlements': settlements})
        return request.render('al_construction_planner.portal_my_construction_progress', values)

    # ------------------------------------------------------------------
    # Material extra (v1.6, M16-06)
    # ------------------------------------------------------------------
    def _construction_extra_scope(self, project_id):
        """Pisos y ambientes donde trabaja la empresa del usuario en la obra, y
        los materiales del plan vigente de esa obra (no todo el catálogo)."""
        lines = self._construction_lines([('project_id', '=', project_id)])
        places = (lines.floor_task_id | lines.space_task_id).sorted(
            lambda t: (t.construction_floor_task_id.sequence or t.sequence, t.display_name))
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
        return request.render('al_construction_planner.portal_construction_extra', values)

    def _construction_create_extra(self, project, places, products, post):
        place = places.filtered(lambda t: str(t.id) == str(post.get('task_id')))
        if not place:
            raise UserError(_('Elija el piso o ambiente del pedido.'))
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
        # se crea en borrador (sin reservar stock) en una obra, un piso o
        # ambiente y un material de su alcance, filtrados arriba.
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
            'al_construction_planner.group_planner_manager').sudo().user_ids[:1]
        if reviewer:
            extra_sudo.activity_schedule(
                'mail.mail_activity_data_todo', user_id=reviewer.id,
                summary=_('Revisar el material extra pedido desde el portal'))
        return extra_sudo
