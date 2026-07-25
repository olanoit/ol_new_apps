# -*- coding: utf-8 -*-
"""Periodo de nómina (per-compañía).

Cada compañía mantiene su propio calendario de periodos; ``company_id``
es requerido y el código es único por compañía. El año fiscal v18
(``account.fiscal.year``, eliminado en v19) se sustituye por el campo
``year`` derivado de la fecha de inicio.
"""
import calendar
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError

MONTH_NAMES_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
    'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]


class HrPeriod(models.Model):
    _name = 'hr.period'
    _description = 'Periodo de Nómina'
    _inherit = ['mail.thread']
    _order = 'date_start desc, code'
    _check_company_auto = True

    code = fields.Char(string='Código', required=True, tracking=True)
    name = fields.Char(string='Nombre', tracking=True)
    year = fields.Integer(
        string='Año', compute='_compute_year', store=True, index=True)
    date_start = fields.Date(string='Fecha de inicio', tracking=True, required=True)
    date_end = fields.Date(string='Fecha de fin', tracking=True, required=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company, index=True)

    _unique_code_per_company = models.Constraint(
        'UNIQUE(company_id, code)',
        'No pueden existir dos periodos con el mismo código en la misma '
        'compañía.')

    @api.depends('date_start')
    def _compute_year(self):
        for period in self:
            period.year = period.date_start.year if period.date_start else 0

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for period in self:
            if period.date_start > period.date_end:
                raise UserError(self.env._(
                    'La fecha de inicio no puede ser mayor que la fecha '
                    'de fin.'))


class HrPeriodGenerator(models.TransientModel):
    """Genera los 12 periodos mensuales de un año (código PLAME AAAAMM)."""
    _name = 'hr.period.generator'
    _description = 'Generador de Periodos'

    year = fields.Integer(
        string='Año', required=True, default=lambda self: date.today().year)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)

    def action_generate(self):
        self.ensure_one()
        Period = self.env['hr.period']
        created = Period.browse()
        for month in range(1, 13):
            code = '%04d%02d' % (self.year, month)
            if Period.search_count([
                    ('code', '=', code),
                    ('company_id', '=', self.company_id.id)]):
                continue
            last_day = calendar.monthrange(self.year, month)[1]
            created |= Period.create({
                'code': code,
                'name': '%s %s' % (MONTH_NAMES_ES[month - 1], self.year),
                'date_start': date(self.year, month, 1),
                'date_end': date(self.year, month, last_day),
                'company_id': self.company_id.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Periodos %s', self.year),
            'res_model': 'hr.period',
            'view_mode': 'list,form',
            'domain': [('year', '=', self.year),
                       ('company_id', '=', self.company_id.id)],
        }
