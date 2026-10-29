# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time

import pytz
from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

PE_TZ = pytz.timezone('America/Lima')


def _utc(day, end=False):
    moment = datetime.combine(day, time.max if end else time.min)
    return PE_TZ.localize(moment).astimezone(pytz.utc).replace(tzinfo=None)


class L10nPeMrpCostClose(models.Model):
    """Cierre de costos de fabricación del mes.

    Calcula, para las órdenes terminadas en el mes:

    * el ajuste de mano de obra: horas de cada registro de tiempo × (costo
      hora real del mes del empleado − costo hora con que se cargó);
    * el reparto de cada bolsa de CIF según su base.

    Al validar, todo se carga con un costo en destino sobre las órdenes
    (``mrp_landed_costs``): sube el valor del producto terminado (y el costo
    de lo ya vendido) contra la contrapartida de cada concepto.
    """
    _name = 'l10n_pe.mrp.cost.close'
    _description = 'Cierre de costos de fabricación'
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
        [('draft', 'Borrador'), ('done', 'Validado')],
        string='Estado', default='draft', required=True, readonly=True, tracking=True)
    line_ids = fields.One2many('l10n_pe.mrp.cost.close.line', 'close_id', string='Cargos')
    landed_cost_id = fields.Many2one('stock.landed.cost', string='Costo en destino', readonly=True, copy=False)
    currency_id = fields.Many2one(related='company_id.currency_id')
    amount_total = fields.Monetary(string='Total', compute='_compute_amount_total')
    warning = fields.Text(string='Avisos', readonly=True)

    _company_period_uniq = models.Constraint(
        'UNIQUE(company_id, date_from)', 'Ya hay un cierre de costos para ese periodo.')

    @api.depends('date_from', 'date_to')
    def _compute_display_name(self):
        for close in self:
            close.display_name = _('Cierre de costos %(from)s – %(to)s',
                                   **{'from': close.date_from, 'to': close.date_to})

    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        for close in self:
            close.amount_total = sum(close.line_ids.mapped('amount'))

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def _l10n_pe_productions(self):
        self.ensure_one()
        return self.env['mrp.production'].search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'done'),
            ('date_finished', '>=', _utc(self.date_from)),
            ('date_finished', '<=', _utc(self.date_to, end=True)),
        ])

    def action_compute(self):
        for close in self:
            if close.state != 'draft':
                raise UserError(_('Solo se recalcula un cierre en borrador.'))
            close.line_ids.unlink()
            productions = close._l10n_pe_productions()
            warnings = []
            vals_list = close._l10n_pe_labor_lines(productions, warnings)
            for pool in self.env['l10n_pe.mrp.cost.pool'].search([('company_id', '=', close.company_id.id)]):
                vals_list += close._l10n_pe_pool_lines(pool, productions, warnings)
            self.env['l10n_pe.mrp.cost.close.line'].create(
                [{'close_id': close.id, **vals} for vals in vals_list])
            close.warning = '\n'.join(warnings) or False

    def _l10n_pe_labor_lines(self, productions, warnings):
        """Ajuste de la mano de obra al costo hora real de cada mes."""
        times = productions.workorder_ids.time_ids.filtered(lambda t: t.employee_id and t.date_end)
        if not times:
            return []
        first = min(times.mapped('date_start')).date().replace(day=1)
        rates = self.env['l10n_pe.mrp.labor.rate']._l10n_pe_real_rates(
            self.company_id, first, self.date_to)
        adjustment = defaultdict(float)
        hours = defaultdict(float)
        missing = set()
        for log in times:
            month = pytz.utc.localize(log.date_start).astimezone(PE_TZ).date().replace(day=1)
            real = rates.get((log.employee_id, month))
            if real is None:
                missing.add((log.employee_id.name, month.strftime('%m/%Y')))
                continue
            log_hours = log.duration / 60.0
            adjustment[log.production_id] += log_hours * (real - log.employee_cost)
            hours[log.production_id] += log_hours
        if missing:
            warnings.append(_('Sin costo hora aplicado (no se ajustan): %s.',
                              ', '.join(f'{name} {month}' for name, month in sorted(missing))))
        currency = self.company_id.currency_id
        return [{
            'production_id': production.id,
            'element': 'labor',
            'basis': hours[production],
            'amount': currency.round(amount),
        } for production, amount in adjustment.items() if not currency.is_zero(amount)]

    def _l10n_pe_pool_lines(self, pool, productions, warnings):
        """Reparto de una bolsa de CIF entre las órdenes del mes."""
        currency = self.company_id.currency_id
        amount = currency.round(pool._l10n_pe_amount(self.date_from, self.date_to))
        if currency.is_zero(amount):
            return []
        if pool.workcenter_ids:
            productions = productions.filtered(
                lambda p: p.workorder_ids.workcenter_id & pool.workcenter_ids)
        bases = {production: self._l10n_pe_basis(pool, production) for production in productions}
        total = sum(bases.values())
        if not total:
            warnings.append(_('La bolsa «%s» no tiene órdenes con base de reparto en el periodo: '
                              'no se reparte.', pool.name))
            return []
        lines = []
        allocated = 0.0
        for production, basis in bases.items():
            if not basis:
                continue
            share = currency.round(amount * basis / total)
            allocated += share
            lines.append({'production_id': production.id, 'element': 'overhead',
                          'pool_id': pool.id, 'basis': basis, 'amount': share})
        # El redondeo, a la orden con más base.
        biggest = max(lines, key=lambda vals: vals['basis'])
        biggest['amount'] = currency.round(biggest['amount'] + amount - allocated)
        return lines

    @api.model
    def _l10n_pe_basis(self, pool, production):
        if pool.split_basis == 'hours':
            workorders = production.workorder_ids
            if pool.workcenter_ids:
                workorders = workorders.filtered(lambda w: w.workcenter_id in pool.workcenter_ids)
            return sum(workorders.mapped('duration')) / 60.0
        finished = production.move_finished_ids.filtered(
            lambda m: m.state == 'done' and m.product_id == production.product_id)
        qty = sum(finished.mapped('product_qty'))
        if pool.split_basis == 'quantity':
            return qty
        if pool.split_basis == 'weight':
            return qty * production.product_id.weight
        if pool.split_basis == 'volume':
            return qty * production.product_id.volume
        return sum(production.move_raw_ids.filtered(lambda m: m.state == 'done').mapped('value')) \
            + sum(production.workorder_ids.mapped(lambda w: w._cal_cost()))

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------
    def action_validate(self):
        for close in self:
            if close.state != 'draft':
                continue
            if not close.line_ids:
                raise UserError(_('Calcule el cierre antes de validarlo.'))
            close.landed_cost_id = close._l10n_pe_create_landed_cost()
            close.state = 'done'

    def _l10n_pe_create_landed_cost(self):
        self.ensure_one()
        company = self.company_id
        product = self.env.ref('al_l10n_pe_mrp_cost.product_production_cost_adjustment')
        groups = defaultdict(lambda: self.env['l10n_pe.mrp.cost.close.line'])
        for line in self.line_ids:
            groups[line.element, line.pool_id] |= line
        cost_lines = []
        for (element, pool), lines in groups.items():
            account = pool.counterpart_account_id if pool else company.l10n_pe_mrp_labor_account_id
            if not account:
                raise UserError(_('Indique la contrapartida del ajuste de mano de obra en los ajustes '
                                  'de Fabricación.'))
            cost_lines.append(Command.create({
                'name': pool.name if pool else _('Ajuste de mano de obra'),
                'product_id': product.id,
                'price_unit': sum(lines.mapped('amount')),
                'split_method': 'equal',
                'account_id': account.id,
            }))
        landed = self.env['stock.landed.cost'].create({
            'company_id': company.id,
            'date': self.date_to,
            'target_model': 'manufacturing',
            'mrp_production_ids': [Command.set(self.line_ids.production_id.ids)],
            'account_journal_id': company.account_stock_journal_id.id,
            'description': self.display_name,
            'cost_lines': cost_lines,
        })
        landed.compute_landed_cost()
        self._l10n_pe_set_adjustments(landed, groups)
        landed.button_validate()
        return landed

    def _l10n_pe_set_adjustments(self, landed, groups):
        """Reemplaza el reparto de Odoo por el del cierre: el cargo de cada
        orden se reparte entre sus productos terminados por cantidad."""
        currency = self.company_id.currency_id
        for cost_line, lines in zip(landed.cost_lines, groups.values()):
            adjustments = landed.valuation_adjustment_lines.filtered(lambda a: a.cost_line_id == cost_line)
            for line in lines:
                own = adjustments.filtered(lambda a: a.move_id.production_id == line.production_id)
                if not own:
                    raise UserError(_(
                        'La orden %s no admite costo en destino: su producto debe usar costo '
                        'promedio o PEPS.', line.production_id.display_name))
                total_qty = sum(own.mapped('quantity'))
                allocated = 0.0
                for adjustment in own:
                    value = currency.round(line.amount * adjustment.quantity / total_qty) if total_qty else 0.0
                    adjustment.additional_landed_cost = value
                    allocated += value
                own[-1:].additional_landed_cost += currency.round(line.amount - allocated)
            # Las líneas de órdenes sin cargo en este concepto quedan en cero.
            (adjustments.filtered(lambda a: a.move_id.production_id not in lines.production_id)
             ).additional_landed_cost = 0.0


class L10nPeMrpCostCloseLine(models.Model):
    _name = 'l10n_pe.mrp.cost.close.line'
    _description = 'Cargo del cierre de costos'
    _order = 'element, pool_id, production_id'

    close_id = fields.Many2one('l10n_pe.mrp.cost.close', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='close_id.company_id', store=True)
    currency_id = fields.Many2one(related='close_id.currency_id')
    production_id = fields.Many2one('mrp.production', string='Orden', required=True, index=True)
    product_id = fields.Many2one(related='production_id.product_id', store=True, string='Producto')
    element = fields.Selection(
        [('labor', 'Ajuste de mano de obra'), ('overhead', 'CIF')],
        string='Concepto', required=True)
    pool_id = fields.Many2one('l10n_pe.mrp.cost.pool', string='Bolsa')
    basis = fields.Float(string='Base', digits=(16, 4))
    amount = fields.Monetary(string='Importe')
