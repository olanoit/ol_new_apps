# -*- coding: utf-8 -*-
"""Periodo de nómina (per-compañía).

Cada compañía mantiene su propio calendario de periodos; ``company_id``
es requerido y el código es único por compañía. El año fiscal v18
(``account.fiscal.year``, eliminado en v19) se sustituye por el campo
``year`` derivado de la fecha de inicio.
"""
import calendar
from datetime import date, timedelta

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
    period_type = fields.Selection(
        selection=[('monthly', 'Mensual'), ('weekly', 'Semanal')],
        string='Periodicidad', default='monthly', required=True, index=True,
        help='La PLAME se declara por mes. Los regímenes que pagan por '
             'semana —construcción civil— usan periodos semanales que '
             'cuelgan del mes al que pertenecen.')
    parent_id = fields.Many2one(
        'hr.period', string='Periodo mensual', index='btree_not_null',
        ondelete='cascade', check_company=True,
        domain="[('period_type', '=', 'monthly')]",
        help='Mes en el que se declara este periodo semanal.')
    child_ids = fields.One2many(
        'hr.period', 'parent_id', string='Periodos semanales')
    duration_days = fields.Integer(
        string='Días', compute='_compute_duration_days', store=True,
        help='Sirve para elegir el periodo más ajustado a cada boleta.')

    _unique_code_per_company = models.Constraint(
        'UNIQUE(company_id, code)',
        'No pueden existir dos periodos con el mismo código en la misma '
        'compañía.')

    @api.depends('date_start')
    def _compute_year(self):
        for period in self:
            period.year = period.date_start.year if period.date_start else 0

    @api.depends('date_start', 'date_end')
    def _compute_duration_days(self):
        for period in self:
            if period.date_start and period.date_end:
                period.duration_days = (
                    period.date_end - period.date_start).days + 1
            else:
                period.duration_days = 0

    @api.constrains('parent_id', 'date_start', 'date_end')
    def _check_parent_contains_child(self):
        for period in self.filtered('parent_id'):
            parent = period.parent_id
            if not (parent.date_start <= period.date_start
                    and period.date_end <= parent.date_end):
                raise UserError(self.env._(
                    'El periodo %(name)s no cabe dentro de %(parent)s.',
                    name=period.display_name, parent=parent.display_name))

    @api.model
    def _get_period_for_payslip(self, company, date_from, date_to):
        """Periodo **más ajustado** que contiene la boleta entera.

        Con periodos semanales y mensuales conviviendo, una boleta de una
        semana cabe en los dos; se elige el más corto. Así el cálculo no
        necesita saber qué periodicidad tiene la estructura, y una boleta
        mensual sigue cayendo en el mes porque no cabe en ninguna semana.
        """
        candidates = self.search([
            ('company_id', '=', company.id),
            ('date_start', '<=', date_from),
            ('date_end', '>=', date_to or date_from),
        ])
        if not candidates:
            return self.browse()
        return min(candidates, key=lambda p: p.duration_days)

    def _l10n_pe_plame_period(self):
        """Periodo con el que se declara en la PLAME, que es mensual."""
        self.ensure_one()
        return self.parent_id or self

    def action_view_payslips(self):
        """Boletas del periodo, incluidas las de sus semanas."""
        self.ensure_one()
        periods = self | self.child_ids
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Boletas de %s', self.display_name),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('periodo_id', 'in', periods.ids)],
        }

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
    generate_weekly = fields.Boolean(
        string='Generar también semanas',
        help='Para los regímenes que pagan por semana, como construcción '
             'civil. Cada semana queda colgada de su mes.')

    def _weekly_ranges(self, month_start, month_end):
        """Semanas de lunes a domingo, **cortadas en el fin de mes**.

        Una semana a caballo entre dos meses obligaría a repartir sus
        importes al declarar la PLAME, que va por mes. Cortándola, la suma
        de las semanas de un mes es exactamente el mes y no hay que
        prorratear nada. El precio es que la primera y la última semana
        pueden ser más cortas.
        """
        ranges = []
        start = month_start
        while start <= month_end:
            # Domingo de esa semana (weekday(): lunes=0 … domingo=6).
            sunday = start + timedelta(days=6 - start.weekday())
            end = min(sunday, month_end)
            ranges.append((start, end))
            start = end + timedelta(days=1)
        return ranges

    def _create_weekly_periods(self, monthly):
        """Crea las semanas de un periodo mensual, si no existen ya."""
        Period = self.env['hr.period']
        created = Period.browse()
        ranges = self._weekly_ranges(monthly.date_start, monthly.date_end)
        for index, (start, end) in enumerate(ranges, start=1):
            code = '%s-S%02d' % (monthly.code, index)
            if Period.search_count([('code', '=', code),
                                    ('company_id', '=', monthly.company_id.id)]):
                continue
            created |= Period.create({
                'code': code,
                'name': '%s · semana %d (%s al %s)' % (
                    monthly.name, index, start.strftime('%d/%m'),
                    end.strftime('%d/%m')),
                'date_start': start,
                'date_end': end,
                'period_type': 'weekly',
                'parent_id': monthly.id,
                'company_id': monthly.company_id.id,
            })
        return created

    def action_generate(self):
        self.ensure_one()
        Period = self.env['hr.period']
        created = Period.browse()
        for month in range(1, 13):
            code = '%04d%02d' % (self.year, month)
            monthly = Period.search([
                ('code', '=', code),
                ('company_id', '=', self.company_id.id)], limit=1)
            if not monthly:
                last_day = calendar.monthrange(self.year, month)[1]
                monthly = Period.create({
                    'code': code,
                    'name': '%s %s' % (MONTH_NAMES_ES[month - 1], self.year),
                    'date_start': date(self.year, month, 1),
                    'date_end': date(self.year, month, last_day),
                    'company_id': self.company_id.id,
                })
                created |= monthly
            if self.generate_weekly:
                created |= self._create_weekly_periods(monthly)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Periodos %s', self.year),
            'res_model': 'hr.period',
            'view_mode': 'list,form',
            'domain': [('year', '=', self.year),
                       ('company_id', '=', self.company_id.id)],
        }
