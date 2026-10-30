# -*- coding: utf-8 -*-
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: Categorías de reglas de la planilla PE que forman el costo del empleador.
COST_CATEGORIES = {'ING': 1, 'DES_AFE': -1, 'APOR_EMP': 1}


class L10nPeMrpLaborRate(models.Model):
    """Costo hora de los empleados en un mes, desde la planilla.

    Costo del empleador = ingresos − descuentos afectos + aportes del
    empleador (EsSalud, SCTR…) + provisiones de CTS, gratificación y
    vacaciones del lote (si está instalado ``al_hr_pe_benefits``), entre las
    horas de los días laborados (``hr.main.parameter.wd_dlab``).

    «Aplicar» lo deja como costo hora del empleado (``hourly_cost``), que
    Odoo usa en los registros de tiempo de las órdenes. El cierre de costos
    toma de aquí el costo hora real de cada mes.
    """
    _name = 'l10n_pe.mrp.labor.rate'
    _description = 'Costo hora desde la planilla'
    _inherit = ['mail.thread']
    _order = 'date_from desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(months=1))
    date_to = fields.Date(
        string='Hasta', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(days=1))
    state = fields.Selection(
        [('draft', 'Borrador'), ('applied', 'Aplicado')],
        string='Estado', default='draft', required=True, readonly=True, tracking=True)
    line_ids = fields.One2many('l10n_pe.mrp.labor.rate.line', 'rate_id', string='Empleados')
    currency_id = fields.Many2one(related='company_id.currency_id')

    _company_period_uniq = models.Constraint(
        'UNIQUE(company_id, date_from)', 'Ya hay un costo hora para ese periodo.')

    @api.depends('date_from', 'date_to')
    def _compute_display_name(self):
        for rate in self:
            rate.display_name = _('Costo hora %(from)s – %(to)s',
                                  **{'from': rate.date_from, 'to': rate.date_to})

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rate in self:
            if rate.date_from > rate.date_to:
                raise UserError(_('La fecha inicial debe ser anterior a la final.'))

    def action_compute(self):
        for rate in self:
            if rate.state != 'draft':
                raise UserError(_('Solo se recalcula un costo hora en borrador.'))
            rate.line_ids.unlink()
            vals_list = [
                {'rate_id': rate.id, **vals}
                for vals in rate._l10n_pe_employee_costs().values() if vals['hours']
            ]
            if not vals_list:
                raise UserError(_('No hay boletas calculadas con horas laboradas en el periodo.'))
            self.env['l10n_pe.mrp.labor.rate.line'].create(vals_list)

    def _l10n_pe_employee_costs(self):
        """``{empleado: {employee_id, payroll_cost, provision_cost, hours}}``."""
        self.ensure_one()
        slips = self.env['hr.payslip'].search([
            ('company_id', '=', self.company_id.id),
            ('state', 'not in', ('draft', 'cancel')),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
        ])
        param = self.env['hr.main.parameter'].get_main_parameter(self.company_id)
        dlab_codes = set(param.wd_dlab.mapped('code'))
        if not dlab_codes:
            raise UserError(_('Indique los tipos de días laborados (W.D. días laborados) en los '
                              'parámetros de la planilla: son las horas del costo hora.'))
        costs = defaultdict(lambda: {'payroll_cost': 0.0, 'provision_cost': 0.0, 'hours': 0.0})
        for slip in slips:
            values = costs[slip.employee_id]
            for line in slip.line_ids:
                # Odoo 20: una regla puede tener varias categorías; cuenta la
                # primera que es de costo.
                code = next((code for code in line.category_ids.mapped('code')
                             if code in COST_CATEGORIES), None)
                if code:
                    values['payroll_cost'] += line.total * COST_CATEGORIES[code]
            values['hours'] += sum(
                wd.number_of_hours for wd in slip.worked_days_line_ids if wd.code in dlab_codes)
        for employee, amount in self._l10n_pe_provisions(slips.payslip_run_id).items():
            costs[employee]['provision_cost'] += amount
        return {employee: {'employee_id': employee.id, **values} for employee, values in costs.items()}

    def _l10n_pe_provisions(self, runs):
        """Provisiones de beneficios sociales de los lotes, por empleado."""
        amounts = defaultdict(float)
        if 'hr.provisiones' not in self.env or not runs:
            return amounts
        provisions = self.env['hr.provisiones'].search([('payslip_run_id', 'in', runs.ids)])
        for line in provisions.cts_lines:
            amounts[line.employee_id] += line.provisiones_cts
        for line in provisions.grati_lines:
            amounts[line.employee_id] += line.total
        for line in provisions.vaca_lines:
            amounts[line.employee_id] += line.provisiones_vaca
        return amounts

    def action_apply(self):
        if not self.env.user.has_group('hr.group_hr_user'):
            raise UserError(_('Aplicar el costo hora requiere el permiso de Empleados.'))
        for rate in self:
            if not rate.line_ids:
                raise UserError(_('Calcule el costo hora antes de aplicarlo.'))
            for line in rate.line_ids:
                line.previous_hourly_cost = line.employee_id.hourly_cost
                line.employee_id.hourly_cost = line.hourly_cost
            rate.state = 'applied'

    def action_draft(self):
        self.state = 'draft'

    @api.model
    def _l10n_pe_real_rates(self, company, date_from, date_to):
        """``{(empleado, primer día del mes): costo hora}`` de los costos hora
        aplicados que tocan el rango."""
        rates = self.search([
            ('company_id', '=', company.id), ('state', '=', 'applied'),
            ('date_from', '<=', date_to), ('date_to', '>=', date_from),
        ])
        result = {}
        for rate in rates:
            for line in rate.line_ids:
                result[line.employee_id, rate.date_from] = line.hourly_cost
        return result


class L10nPeMrpLaborRateLine(models.Model):
    _name = 'l10n_pe.mrp.labor.rate.line'
    _description = 'Costo hora de un empleado'
    _order = 'employee_id'

    rate_id = fields.Many2one('l10n_pe.mrp.labor.rate', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='rate_id.company_id', store=True)
    currency_id = fields.Many2one(related='rate_id.currency_id')
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, check_company=True)
    payroll_cost = fields.Monetary(
        string='Costo de planilla', help='Ingresos − descuentos afectos + aportes del empleador.')
    provision_cost = fields.Monetary(string='Provisiones', help='CTS, gratificación y vacaciones del mes.')
    hours = fields.Float(string='Horas laboradas')
    hourly_cost = fields.Monetary(string='Costo hora', compute='_compute_hourly_cost', store=True)
    previous_hourly_cost = fields.Monetary(string='Costo hora anterior', readonly=True)

    @api.depends('payroll_cost', 'provision_cost', 'hours')
    def _compute_hourly_cost(self):
        for line in self:
            total = line.payroll_cost + line.provision_cost
            line.hourly_cost = line.currency_id.round(total / line.hours) if line.hours else 0.0
