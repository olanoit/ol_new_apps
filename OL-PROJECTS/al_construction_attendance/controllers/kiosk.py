# -*- coding: utf-8 -*-
"""Quiosco de la sede (v1.5, P-27) y parte diario de la cuadrilla (P-26).

El quiosco es una página pública protegida por la clave de la sede (el
enlace se abre en la tablet de la obra): los obreros propios y los de las
contratas marcan ingreso y salida con su documento o PIN, sin usuario. Se
valida la hora límite y la distancia de la tablet a la sede.
"""
import hmac

from odoo import _, fields, http
from odoo.http import request

from odoo.addons.al_construction_planner_subcontract.controllers.portal import ConstructionPortal


class ConstructionKiosk(http.Controller):

    def _site(self, site_id, token):
        # sudo: página pública de la tablet; la clave de la sede la protege.
        site = request.env['l10n_pe.hr.construction.site'].sudo().browse(site_id).exists()
        if not site or not site.kiosk_token or not token \
                or not hmac.compare_digest(site.kiosk_token, token):
            return None
        return site

    @http.route('/obra/quiosco/<int:site_id>/<string:token>', type='http', auth='public',
                methods=['GET', 'POST'], website=True, csrf=False)
    def kiosk(self, site_id, token, **post):
        site = self._site(site_id, token)
        if not site:
            return request.not_found()
        result = None
        if request.httprequest.method == 'POST':
            result = self._kiosk_mark(site, (post.get('document') or '').strip(), post)
        return request.render('al_construction_attendance.kiosk_page', {
            'site': site, 'token': token, 'result': result})

    def _kiosk_mark(self, site, document, post):
        if not document:
            return {'ok': False, 'message': _('Escriba su documento o PIN.')}
        try:
            latitude = float(post.get('latitude') or 0.0)
            longitude = float(post.get('longitude') or 0.0)
        except ValueError:
            latitude = longitude = 0.0
        now = fields.Datetime.now()
        company = site.company_id or request.env.company
        warnings = []
        if site._out_of_range(latitude, longitude):
            warnings.append(_('La tablet está fuera del radio de la sede (%s m).',
                              int(site._distance_to(latitude, longitude))))
        # sudo: la tablet no tiene usuario; se busca solo por documento o PIN
        # en la compañía de la sede.
        Employee_sudo = request.env['hr.employee'].sudo()
        employee = Employee_sudo.search([
            ('company_id', '=', company.id), '|', ('identification_id', '=', document),
            ('pin', '=', document)], limit=1)
        if employee:
            Attendance_sudo = request.env['hr.attendance'].sudo()
            open_attendance = Attendance_sudo.search([
                ('employee_id', '=', employee.id), ('check_out', '=', False)], limit=1)
            if open_attendance:
                open_attendance.write({'check_out': now, 'out_latitude': latitude,
                                       'out_longitude': longitude, 'out_mode': 'kiosk'})
                return {'ok': True, 'warnings': warnings,
                        'message': _('Salida registrada: %s.', employee.name)}
            attendance = Attendance_sudo.create({
                'employee_id': employee.id, 'check_in': now, 'in_mode': 'kiosk',
                'in_latitude': latitude, 'in_longitude': longitude,
                'l10n_pe_construction_site_id': site.id})
            if attendance.l10n_pe_site_late:
                warnings.append(_('Ingreso fuera de hora.'))
            return {'ok': True, 'warnings': warnings,
                    'message': _('Ingreso registrado: %s.', employee.name)}
        Worker_sudo = request.env['construction.contractor.worker'].sudo()
        worker = Worker_sudo.search([
            ('company_id', '=', company.id), '|', ('document_number', '=', document),
            ('pin', '=', document)], limit=1)
        if not worker:
            return {'ok': False, 'message': _('No se encontró a nadie con ese documento o PIN.')}
        Attendance_sudo = request.env['construction.contractor.attendance'].sudo()
        open_attendance = Attendance_sudo.search([
            ('worker_id', '=', worker.id), ('check_out', '=', False)], limit=1)
        if open_attendance:
            open_attendance.check_out = now
            return {'ok': True, 'warnings': warnings,
                    'message': _('Salida registrada: %(name)s (%(partner)s).', name=worker.name,
                                 partner=worker.partner_id.name)}
        attendance = Attendance_sudo.create({
            'worker_id': worker.id, 'site_id': site.id, 'check_in': now, 'mode': 'kiosk',
            'latitude': latitude, 'longitude': longitude, 'sctr_expired': worker.sctr_expired})
        if worker.sctr_expired:
            warnings.append(_('El SCTR de %s está vencido: avise al supervisor.', worker.name))
        if attendance.late:
            warnings.append(_('Ingreso fuera de hora.'))
        return {'ok': True, 'warnings': warnings,
                'message': _('Ingreso registrado: %(name)s (%(partner)s).', name=worker.name,
                             partner=worker.partner_id.name)}


class ConstructionCrewPortal(ConstructionPortal):

    # P-26 · Parte diario de la cuadrilla: quién de su empresa marcó hoy y en
    # qué sede.
    @http.route(['/my/obra/parte'], type='http', auth='user', website=True)
    def portal_crew_report(self, **kw):
        partner = self._construction_partner()
        today = fields.Date.context_today(request.env.user)
        # sudo: solo las marcaciones del personal de la empresa del usuario.
        attendances = request.env['construction.contractor.attendance'].sudo().search([
            ('partner_id', 'child_of', partner.id), ('date', '=', today)])
        values = self._prepare_portal_layout_values()
        values.update({'page_name': 'construction_crew', 'attendances': attendances,
                       'today': today, 'partner': partner})
        return request.render('al_construction_attendance.portal_crew_report', values)
