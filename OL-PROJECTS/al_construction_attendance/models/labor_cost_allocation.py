# -*- coding: utf-8 -*-
"""Cierre de costo de personal por sede (v1.5, fase 18, P-29).

Cada mes, las horas de marcación del personal propio en cada sede por su
costo por hora dan el costo de personal de la sede. Al publicar el cierre se
crean los apuntes analíticos con la cuenta de la obra (o del área), la etapa
de la sede y la partida de mano de obra fija (MODF) de la compañía, y el
cierre los contrasta con lo planificado de personal propio en el plan vigente
de la obra.

Si la planilla ya reparte su costo por sede (distribución analítica de la
boleta), el cierre sirve para contrastar y no se publica: los apuntes se
duplicarían.
"""
from datetime import datetime, time

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError


class ConstructionLaborCostAllocation(models.Model):
    _name = 'construction.labor.cost.allocation'
    _description = 'Cierre de costo de personal por sede'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Cierre', compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    date_from = fields.Date(
        string='Mes', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1)
        - relativedelta(months=1))
    date_to = fields.Date(string='Hasta', compute='_compute_date_to', store=True)
    state = fields.Selection([('draft', 'Borrador'), ('posted', 'Publicado')], string='Estado',
                             default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('construction.labor.cost.allocation.line', 'allocation_id',
                               string='Líneas', copy=False)
    analytic_line_ids = fields.One2many(
        'account.analytic.line', 'construction_labor_allocation_id', string='Apuntes analíticos',
        readonly=True)
    amount_total = fields.Monetary(string='Costo del mes', compute='_compute_amount_total',
                                   store=True)
    summary_html = fields.Html(string='Contra el presupuesto', compute='_compute_summary_html',
                               sanitize=False)

    _period_company_uniq = models.Constraint(
        'UNIQUE(company_id, date_from)', 'Ya hay un cierre de ese mes en la compañía.')

    @api.depends('date_from')
    def _compute_date_to(self):
        for allocation in self:
            allocation.date_to = allocation.date_from and (
                allocation.date_from + relativedelta(day=31))

    @api.depends('date_from')
    def _compute_name(self):
        for allocation in self:
            allocation.name = allocation.date_from and self.env._(
                'Personal %s', allocation.date_from.strftime('%m/%Y')) or '/'

    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        for allocation in self:
            allocation.amount_total = sum(allocation.line_ids.mapped('amount'))

    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from:
            self.date_from = self.date_from.replace(day=1)

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def action_compute(self):
        """Horas de marcación del mes por trabajador y sede, por su costo
        por hora."""
        for allocation in self:
            if allocation.state != 'draft':
                raise UserError(self.env._('%s ya está publicado.', allocation.name))
            start = datetime.combine(allocation.date_from, time.min)
            end = datetime.combine(allocation.date_to, time.max)
            groups = self.env['hr.attendance']._read_group(
                [('check_in', '>=', start), ('check_in', '<=', end),
                 ('l10n_pe_construction_site_id', '!=', False),
                 ('employee_id.company_id', '=', allocation.company_id.id)],
                groupby=['employee_id', 'l10n_pe_construction_site_id'],
                aggregates=['worked_hours:sum'])
            # sudo: el costo por hora es un dato de RR. HH.; el cierre lo
            # usa solo para valorizar las horas.
            employees_sudo = self.env['hr.employee'].sudo().browse(
                {employee.id for employee, _site, _hours in groups})
            costs = {employee.id: employee.hourly_cost for employee in employees_sudo}
            allocation.line_ids.unlink()
            allocation.write({'line_ids': [fields.Command.create({
                'employee_id': employee.id, 'site_id': site.id,
                'hours': round(hours, 2), 'hourly_cost': costs.get(employee.id, 0.0),
            }) for employee, site, hours in groups if hours]})
        return True

    def _site_budget(self, site):
        """Planificado de personal propio en el plan vigente de la obra de la
        sede y publicado hasta este cierre."""
        project = site.project_id
        planned = 0.0
        if project:
            plan = project._construction_current_plan()
            planned = sum(plan.line_ids.filtered(
                lambda l: l.resource_type == 'labor' and l.line_state != 'cancel'
            ).mapped('amount_planned'))
        posted = sum(self.search([
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            ('date_from', '<=', self.date_from)]).line_ids.filtered(
                lambda l: l.site_id == site).mapped('amount'))
        if self.state == 'draft':
            posted += sum(self.line_ids.filtered(lambda l: l.site_id == site).mapped('amount'))
        return planned, posted

    @api.depends('line_ids.amount', 'line_ids.site_id', 'state')
    def _compute_summary_html(self):
        for allocation in self:
            if not allocation.line_ids:
                allocation.summary_html = False
                continue
            currency = allocation.currency_id
            rows = []
            for site, lines in allocation.line_ids.grouped('site_id').items():
                planned, posted = allocation._site_budget(site)
                rows.append(Markup(
                    '<tr><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                    '<td class="text-end">%s</td><td class="text-end">%s</td>'
                    '<td class="text-end %s">%s</td></tr>') % (
                    site.display_name, '{:,.2f}'.format(sum(lines.mapped('hours'))),
                    currency.format(sum(lines.mapped('amount'))), currency.format(posted),
                    currency.format(planned), 'text-danger' if planned and posted > planned else '',
                    currency.format(planned - posted) if planned else '—'))
            allocation.summary_html = Markup(
                '<table class="table table-sm o_main_table"><thead><tr><th>%s</th>'
                '<th class="text-end">%s</th><th class="text-end">%s</th>'
                '<th class="text-end">%s</th><th class="text-end">%s</th>'
                '<th class="text-end">%s</th></tr></thead><tbody>%s</tbody></table>') % (
                self.env._('Sede'), self.env._('Horas'), self.env._('Costo del mes'),
                self.env._('Acumulado'), self.env._('Planificado (personal propio)'),
                self.env._('Saldo'), Markup('').join(rows))

    # ------------------------------------------------------------------
    # Publicación
    # ------------------------------------------------------------------
    def _analytic_vals(self, line):
        """Apunte de una línea: la cuenta de la obra (o de la sede), la etapa
        de la sede y la partida MODF, cada una en la columna de su plan."""
        site = line.site_id
        accounts = (site.project_id.account_id or site.analytic_account_id) \
            | site.default_stage_account_id | self.company_id.construction_labor_cost_account_id
        if not accounts:
            raise UserError(self.env._(
                'La sede %s no tiene cuenta analítica ni obra con cuenta.', site.display_name))
        vals = {
            'name': self.env._('%(closing)s · %(employee)s', closing=self.name,
                               employee=line.employee_id.name),
            'date': self.date_to,
            'amount': -line.amount,
            'unit_amount': line.hours,
            'company_id': self.company_id.id,
            'construction_labor_allocation_id': self.id,
        }
        for account in accounts:
            vals[account.plan_id._column_name()] = account.id
        return vals

    def _analytic_vals_list(self, line):
        """Paquete 1.16, D2: el costo de la persona se reparte entre las
        líneas del plan donde trabajó en el periodo, por sus horas ejecutadas
        de cuadrilla, cada parte con la distribución completa de su línea
        (obra, etapa, MODF, nivel, rubro). Lo que no tiene turno asignado
        queda como antes: obra, etapa de la sede y MODF."""
        base = self._analytic_vals(line)
        shares = line._construction_plan_shares()
        if not shares:
            return [base]
        currency = self.currency_id
        modf = self.company_id.construction_labor_cost_account_id
        result, assigned = [], 0.0
        for plan_line, fraction in shares.items():
            amount = currency.round(line.amount * fraction)
            assigned += amount
            vals = dict(base, amount=-amount, unit_amount=round(line.hours * fraction, 2))
            Account = self.env['account.analytic.account']
            for key in (plan_line.analytic_distribution or {}):
                accounts = Account.browse(int(a) for a in key.split(',') if a).exists()
                for account in accounts | modf.filtered(
                        lambda m: m.root_plan_id not in accounts.root_plan_id):
                    vals[account.root_plan_id._column_name()] = account.id
                break
            result.append(vals)
        rest = currency.round(line.amount - assigned)
        if not currency.is_zero(rest):
            result.append(dict(base, amount=-rest, unit_amount=round(
                line.hours * (1 - sum(shares.values())), 2)))
        return result

    def action_post(self):
        for allocation in self:
            if allocation.state != 'draft':
                continue
            lines = allocation.line_ids.filtered('amount')
            if not lines:
                raise UserError(self.env._('%s no tiene costo que publicar.', allocation.name))
            self.env['account.analytic.line'].create(
                [vals for line in lines for vals in allocation._analytic_vals_list(line)])
            allocation.state = 'posted'
        return True

    def action_draft(self):
        for allocation in self.filtered(lambda a: a.state == 'posted'):
            allocation.analytic_line_ids.unlink()
            allocation.state = 'draft'
        return True


class ConstructionLaborCostAllocationLine(models.Model):
    _name = 'construction.labor.cost.allocation.line'
    _description = 'Línea del cierre de costo de personal'
    _order = 'site_id, employee_id'
    _check_company_auto = True

    allocation_id = fields.Many2one('construction.labor.cost.allocation', required=True,
                                    ondelete='cascade', index=True,
                                    check_company=True)
    company_id = fields.Many2one(related='allocation_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='allocation_id.currency_id')
    employee_id = fields.Many2one('hr.employee', string='Trabajador', required=True,
                                  check_company=True)
    site_id = fields.Many2one('l10n_pe.hr.construction.site', string='Sede', required=True,
                              check_company=True)
    hours = fields.Float(string='Horas', digits=(12, 2))
    hourly_cost = fields.Monetary(string='Costo por hora', currency_field='currency_id')
    amount = fields.Monetary(string='Monto', compute='_compute_amount', store=True,
                             currency_field='currency_id')

    plan_share_note = fields.Char(
        string='Reparto', compute='_compute_plan_share_note',
        help='Paquete 1.16, D2: cómo se reparte el costo entre las líneas del plan, según los '
             'jornales ejecutados de cuadrilla del periodo; el resto queda en la sede.')

    @api.depends('hours', 'hourly_cost')
    def _compute_amount(self):
        for line in self:
            line.amount = line.currency_id.round(line.hours * line.hourly_cost) \
                if line.currency_id else line.hours * line.hourly_cost

    def _construction_plan_shares(self):
        """{línea del plan: fracción de las horas de la persona} según sus
        jornales ejecutados de cuadrilla con línea del plan en el periodo y en
        la obra de la sede. La suma no pasa de 1."""
        self.ensure_one()
        project = self.site_id.project_id
        allocation = self.allocation_id
        if not project or not self.hours or 'construction.crew.day' not in self.env:
            return {}
        # Los jornales los lee el sistema: quien cierra el mes es de RR. HH.
        days = self.env['construction.crew.day'].sudo()._read_group([
            ('kind', '=', 'executed'), ('employee_id', '=', self.employee_id.id),
            ('project_id', '=', project.id), ('plan_line_id', '!=', False),
            ('date', '>=', allocation.date_from), ('date', '<=', allocation.date_to)],
            ['plan_line_id'], ['hours:sum'])
        hours = {plan_line: total for plan_line, total in days if total}
        executed = sum(hours.values())
        if not executed:
            return {}
        base = max(self.hours, executed)
        return {plan_line: total / base for plan_line, total in hours.items()}

    @api.depends('hours', 'employee_id', 'site_id', 'allocation_id.date_from',
                 'allocation_id.date_to')
    def _compute_plan_share_note(self):
        for line in self:
            shares = line._construction_plan_shares() if line._origin.id else {}
            if not shares:
                line.plan_share_note = False
                continue
            parts = ['%s %s %%' % (plan_line.task_id.display_name or plan_line.display_name,
                                   round(fraction * 100, 1))
                     for plan_line, fraction in shares.items()]
            rest = 1 - sum(shares.values())
            if rest > 0.0001:
                parts.append(self.env._('sede %s %%', round(rest * 100, 1)))
            line.plan_share_note = ' · '.join(parts)


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    construction_labor_allocation_id = fields.Many2one(
        'construction.labor.cost.allocation', string='Cierre de costo de personal',
        index='btree_not_null', ondelete='cascade', readonly=True)
