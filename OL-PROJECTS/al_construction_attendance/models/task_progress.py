# -*- coding: utf-8 -*-
"""Avance de contrata sin asistencia en la sede ese día (v1.5, fase 17)."""
from odoo import fields, models
from odoo.tools import SQL


class ConstructionTaskProgress(models.Model):
    _inherit = 'construction.task.progress'

    attendance_ok = fields.Boolean(
        string='Con asistencia', compute='_compute_attendance_ok', search='_search_attendance_ok',
        # M111-01: la sede es de Nómina; el valor solo dice si la contrata
        # marcó ese día, así que se calcula sin los permisos del usuario.
        compute_sudo=True,
        help='La contrata tuvo personal marcado en la sede de la obra ese día; si no, el avance '
             'queda marcado para revisión.')

    def _attendance_keys(self):
        """(contrata, obra, día) con marcación de contrata, solo de las
        contratas, obras y fechas de estos avances: el campo se calcula al
        abrir cualquier lista de avances y el historial de marcaciones solo
        crece."""
        partners = self.partner_id.commercial_partner_id
        days = [day for day in self.mapped('date') if day]
        if not partners or not self.project_id or not days:
            return set()
        Attendance = self.env['construction.contractor.attendance'].sudo()
        rows = Attendance._read_group(
            [('partner_id', 'child_of', partners.ids), ('project_id', 'in', self.project_id.ids),
             ('date', '>=', min(days)), ('date', '<=', max(days))],
            ['partner_id', 'project_id', 'date:day'])
        return {(partner.commercial_partner_id.id, project.id, day) for partner, project, day in rows}

    def _compute_attendance_ok(self):
        keys = self._attendance_keys() if self else set()
        for progress in self:
            partner = progress.partner_id.commercial_partner_id
            progress.attendance_ok = (partner.id, progress.project_id.id, progress.date) in keys \
                if partner and progress.project_id._construction_site() else True

    def _search_attendance_ok(self, operator, value):
        """Los avances de contrata (no rechazados) con o sin marcación ese
        día, resueltos en la base: antes se cargaban todos los avances para
        filtrarlos en memoria."""
        # Odoo 19 normaliza «= False» a «in [False]»: sin estos operadores el
        # filtro no filtraba nada.
        if operator in ('=', '!='):
            wanted = {bool(value)} if operator == '=' else {not bool(value)}
        elif operator in ('in', 'not in'):
            wanted = {bool(item) for item in value}
            if operator == 'not in':
                wanted = {True, False} - wanted
        else:
            return NotImplemented
        if len(wanted) != 1:
            return [(1, '=', 1)] if wanted else [(0, '=', 1)]
        wanted_ok = wanted.pop()
        self.flush_model(['partner_id', 'project_id', 'date', 'state'])
        self.env['construction.contractor.attendance'].flush_model(
            ['partner_id', 'project_id', 'date'])
        self.env['l10n_pe.hr.construction.site'].flush_model(['project_id'])
        self.env['res.partner'].flush_model(['commercial_partner_id'])
        # Sin sede de obra no hay con qué comparar: el avance cuenta como
        # «con asistencia», igual que en el cálculo del campo.
        without_attendance = SQL("""
            EXISTS (SELECT 1 FROM l10n_pe_hr_construction_site site
                     WHERE site.project_id = progress.project_id)
            AND NOT EXISTS (
                SELECT 1 FROM construction_contractor_attendance attendance
                  JOIN res_partner attendance_partner
                    ON attendance_partner.id = attendance.partner_id
                 WHERE attendance_partner.commercial_partner_id = partner.commercial_partner_id
                   AND attendance.project_id = progress.project_id
                   AND attendance.date = progress.date)""")
        query = SQL("""
            SELECT progress.id
              FROM construction_task_progress progress
              JOIN res_partner partner ON partner.id = progress.partner_id
             WHERE progress.state != 'rejected' AND %s""",
                    SQL("NOT (%s)", without_attendance) if wanted_ok else without_attendance)
        return [('id', 'in', [row[0] for row in self.env.execute_query(query)])]
