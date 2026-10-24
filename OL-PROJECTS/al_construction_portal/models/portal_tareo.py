# -*- coding: utf-8 -*-
"""Cuadrilla y tareo desde la tablet (requerimiento CREVAL v1.0, 4.11,
pantalla 7): la asistencia de la cuadrilla queda como marcación en la sede de
la obra y las horas de cada persona por partida como tareo. Al rehacer los
jornales ejecutados desde la marcación, el día de cada persona se reparte
entre las partidas en la proporción del tareo: es el costo de personal propio
de cada partida."""
from collections import defaultdict

from odoo import api, fields, models


class ConstructionPortalTareo(models.Model):
    _name = 'construction.portal.tareo'
    _description = 'Tareo de la cuadrilla'
    _order = 'date desc, employee_id, id'
    _check_company_auto = True

    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 check_company=True)
    # La obra puede no tener compañía (v19): la de la partida.
    company_id = fields.Many2one('res.company', string='Compañía', compute='_compute_company_id',
                                 store=True, index=True)
    date = fields.Date(string='Fecha', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Persona', required=True, index=True)
    plan_line_id = fields.Many2one('construction.resource.plan.line', string='Partida',
                                   required=True, ondelete='cascade', check_company=True)
    hours = fields.Float(string='Horas', digits=(16, 2), required=True)
    user_id = fields.Many2one('res.users', string='Registrado por', readonly=True,
                              default=lambda self: self.env.user)

    @api.depends('project_id.company_id', 'plan_line_id.company_id')
    def _compute_company_id(self):
        for tareo in self:
            tareo.company_id = tareo.project_id.company_id or tareo.plan_line_id.company_id \
                or self.env.company

    _hours_positive = models.Constraint('CHECK(hours > 0)', 'Las horas del tareo son mayores que cero.')


class ConstructionCrewDay(models.Model):
    _inherit = 'construction.crew.day'

    @api.model
    def _refresh_executed(self, projects, date_from, date_to):
        days = super()._refresh_executed(projects, date_from, date_to)
        if not days:
            return days
        # sudo: el tareo y los jornales los rehace el sistema.
        Tareo = self.env['construction.portal.tareo'].sudo()
        tareos = Tareo.search([('project_id', 'in', days.project_id.ids),
                               ('date', '>=', date_from), ('date', '<=', date_to)])
        by_key = defaultdict(lambda: Tareo)
        for tareo in tareos:
            by_key[(tareo.project_id.id, tareo.employee_id.id, tareo.date)] |= tareo
        result = self.browse()
        for day in days.sudo():
            parts = by_key.get((day.project_id.id, day.employee_id.id, day.date))
            if not parts:
                result |= day
                continue
            total = sum(parts.mapped('hours'))
            values = []
            for part in parts:
                share = part.hours / total
                line = part.plan_line_id
                values.append({
                    'kind': 'executed', 'project_id': day.project_id.id,
                    'company_id': day.company_id.id, 'plan_line_id': line.id,
                    'task_id': line.task_id.id, 'role_id': day.role_id.id,
                    'employee_id': day.employee_id.id, 'date': day.date,
                    'days': day.days * share, 'hours': day.hours * share,
                    'amount': day.currency_id.round(day.amount * share), 'source': 'attendance',
                    'attendance_ids': [(6, 0, day.attendance_ids.ids)],
                })
            day.unlink()
            result |= self.sudo().create(values)
        return result
