# -*- coding: utf-8 -*-
"""Avance de contrata sin asistencia en la sede ese día (v1.5, fase 17)."""
from odoo import fields, models


class ConstructionTaskProgress(models.Model):
    _inherit = 'construction.task.progress'

    attendance_ok = fields.Boolean(
        string='Con asistencia', compute='_compute_attendance_ok', search='_search_attendance_ok',
        help='La contrata tuvo personal marcado en la sede de la obra ese día; si no, el avance '
             'queda marcado para revisión.')

    def _attendance_keys(self):
        """(contrata, obra, día) con marcación de contrata."""
        Attendance = self.env['construction.contractor.attendance'].sudo()
        rows = Attendance._read_group(
            [('partner_id', '!=', False), ('project_id', '!=', False)],
            ['partner_id', 'project_id', 'date:day'])
        return {(partner.commercial_partner_id.id, project.id, day) for partner, project, day in rows}

    def _compute_attendance_ok(self):
        keys = self._attendance_keys() if self else set()
        for progress in self:
            partner = progress.partner_id.commercial_partner_id
            progress.attendance_ok = (partner.id, progress.project_id.id, progress.date) in keys \
                if partner and progress.project_id._construction_site() else True

    def _search_attendance_ok(self, operator, value):
        if operator not in ('=', '!='):
            return []
        candidates = self.search([('partner_id', '!=', False), ('state', '!=', 'rejected')])
        ok = candidates.filtered('attendance_ok')
        wanted_ok = (operator == '=') == bool(value)
        return [('id', 'in', (ok if wanted_ok else candidates - ok).ids)]
