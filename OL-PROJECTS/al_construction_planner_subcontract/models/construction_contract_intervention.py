# -*- coding: utf-8 -*-
"""Intervención de una contrata en ejecución (paquete 3 de CREVAL, CR-20, con
I-13 del paquete 1.16).

La intervención deja su preliquidación por partida (sin asiento) y, en las
líneas intervenidas de la orden que sale:

- baja la cantidad a lo ejecutado y la asignación del plan a lo mismo (libera
  el saldo del plan y el comprometido del presupuesto, como «Cerrar orden»
  pero por línea);
- deja la línea del plan sin contrata, con su saldo para «Asignar contrata»;
- rechaza avance nuevo de la contrata que sale; los deductivos siguen.

Las cuotas del fondo de la orden quedan retenidas con el motivo «Contrata
intervenida» hasta la liquidación final (D2). Si sus deductivos superan lo que
queda por pagar, la diferencia va contra el fondo con una nota de crédito del
proveedor conciliada con las cuotas, de la más antigua a la más nueva."""
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .construction_contract_valuation import OPEN_SETTLEMENT_STATES, VALUED_STATES

INTERVENTION_HOLD = 'Contrata intervenida'
CONTRACT_STATUS = [
    ('open', 'En ejecución'),
    ('intervened', 'Intervenida'),
    ('closed', 'Cerrada'),
    ('cancel', 'Anulada'),
]


class ConstructionContractIntervention(models.Model):
    _name = 'construction.contract.intervention'
    _description = 'Intervención de contrata'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', required=True, readonly=True, copy=False)
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Orden de contrata', required=True, readonly=True, index=True,
        check_company=True, ondelete='restrict')
    partner_id = fields.Many2one(related='purchase_order_id.partner_id', string='Contratista',
                                 store=True, index=True)
    project_id = fields.Many2one(related='purchase_order_id.construction_project_id',
                                 string='Obra', store=True, index=True)
    company_id = fields.Many2one(related='purchase_order_id.company_id', string='Compañía',
                                 store=True, index=True)
    currency_id = fields.Many2one(related='purchase_order_id.currency_id', string='Moneda')
    date = fields.Date(string='Fecha', required=True, readonly=True)
    reason = fields.Text(string='Motivo', required=True, readonly=True)
    user_id = fields.Many2one('res.users', string='Intervenida por', readonly=True)
    line_ids = fields.One2many('construction.contract.intervention.line', 'intervention_id',
                               string='Preliquidación', readonly=True)
    amount_valued = fields.Monetary(string='Valorizado', compute='_compute_amounts',
                                    store=True, currency_field='currency_id')
    amount_released = fields.Monetary(string='Comprometido liberado',
                                      compute='_compute_amounts', store=True,
                                      currency_field='currency_id')
    fund_ids = fields.Many2many(
        'construction.guarantee.fund', 'construction_intervention_fund_rel', 'intervention_id',
        'fund_id', string='Cuotas del fondo retenidas', readonly=True)

    @api.depends('line_ids.amount_valued', 'line_ids.amount_released')
    def _compute_amounts(self):
        for intervention in self:
            intervention.amount_valued = sum(intervention.line_ids.mapped('amount_valued'))
            intervention.amount_released = sum(intervention.line_ids.mapped('amount_released'))


class ConstructionContractInterventionLine(models.Model):
    _name = 'construction.contract.intervention.line'
    _description = 'Partida de la preliquidación de la intervención'
    _order = 'intervention_id, sequence, id'

    intervention_id = fields.Many2one('construction.contract.intervention', string='Intervención',
                                      required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='intervention_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='intervention_id.currency_id', string='Moneda')
    sequence = fields.Integer(default=10)
    purchase_line_id = fields.Many2one('purchase.order.line', string='Línea de la orden',
                                       required=True, index=True, ondelete='restrict')
    task_label = fields.Char(string='Partida')
    activity_id = fields.Many2one('construction.labor.activity', string='Actividad')
    uom_id = fields.Many2one('uom.uom', string='Unidad')
    price_unit = fields.Float(string='Precio', digits='Product Price')
    qty_contracted = fields.Float(string='Contratado', digits='Product Unit')
    qty_validated = fields.Float(string='Ejecutado validado', digits='Product Unit')
    qty_valued = fields.Float(string='Valorizado', digits='Product Unit')
    qty_new = fields.Float(string='Cantidad nueva', digits='Product Unit')
    qty_released = fields.Float(string='Saldo liberado', digits='Product Unit')
    amount_valued = fields.Monetary(string='Importe valorizado', currency_field='currency_id')
    amount_released = fields.Monetary(string='Comprometido liberado',
                                      currency_field='currency_id')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    construction_intervention_ids = fields.One2many(
        'construction.contract.intervention', 'purchase_order_id', string='Intervenciones')
    construction_intervened = fields.Boolean(
        string='Intervenida', compute='_compute_construction_intervened', store=True,
        help='Una o más partidas de la orden se intervinieron: no admiten avance nuevo; la '
             'orden sigue abierta para los deductivos, la liquidación final y el fondo.')
    construction_can_intervene = fields.Boolean(compute='_compute_construction_can_intervene')

    @api.depends('construction_intervention_ids')
    def _compute_construction_intervened(self):
        for order in self:
            order.construction_intervened = bool(order.construction_intervention_ids)

    @api.depends('state', 'construction_closed', 'construction_is_service_order')
    def _compute_construction_can_intervene(self):
        for order in self:
            order.construction_can_intervene = (
                order.construction_is_service_order and order.state == 'purchase'
                and not order.construction_closed)

    def action_construction_intervene(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Intervenir contrata'),
            'res_model': 'construction.contract.intervention.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_order_id': self.id},
        }

    def action_view_construction_interventions(self):
        self.ensure_one()
        interventions = self.construction_intervention_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': self.env._('Intervenciones de %s', self.name),
            'res_model': 'construction.contract.intervention',
            'view_mode': 'list,form',
            'domain': [('id', 'in', interventions.ids)],
            'context': {'create': False},
        }
        if len(interventions) == 1:
            action.update(view_mode='form', res_id=interventions.id)
        return action


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    construction_intervention_line_id = fields.Many2one(
        'construction.contract.intervention.line', string='Intervención', copy=False,
        readonly=True, index='btree_not_null')
    construction_intervention_date = fields.Date(
        related='construction_intervention_line_id.intervention_id.date',
        string='Intervenida el')


class ConstructionTaskProgress(models.Model):
    _inherit = 'construction.task.progress'

    @api.constrains('partner_id', 'plan_line_id', 'date')
    def _check_intervened_contract(self):
        """La contrata que sale no registra avance nuevo en sus partidas
        intervenidas (D1); el anterior a la intervención sigue."""
        Settlement = self.env['construction.contract.settlement']
        for progress in self.filtered('partner_id'):
            po_line = Settlement._get_service_line(progress)
            intervened = po_line.construction_intervention_date
            if not intervened or not progress.date or progress.date < intervened:
                continue
            if progress.date > intervened:
                raise ValidationError(self.env._(
                    '%(task)s · %(activity)s: la contrata %(partner)s se intervino el %(date)s en '
                    'esta partida y no registra avance nuevo.',
                    task=progress.task_id.display_name,
                    activity=progress.activity_id.display_name,
                    partner=progress.partner_id.display_name, date=intervened))
            # CR-36 (paquete 4 de CREVAL): del día de la intervención vale solo
            # lo reportado antes de confirmarla.
            intervention = po_line.construction_intervention_line_id.intervention_id
            confirmed = intervention.create_date
            reported = progress.create_date or fields.Datetime.now()
            if confirmed and reported > confirmed:
                hour = fields.Datetime.context_timestamp(
                    progress.with_context(tz=self.env.user.tz or 'America/Lima'), confirmed)
                raise ValidationError(self.env._(
                    '%(task)s · %(activity)s: la contrata %(partner)s se intervino el %(date)s a '
                    'las %(hour)s (%(name)s); el avance de ese día reportado después no se '
                    'registra.',
                    task=progress.task_id.display_name,
                    activity=progress.activity_id.display_name,
                    partner=progress.partner_id.display_name, date=intervened,
                    hour=hour.strftime('%H:%M'), name=intervention.name))


class ConstructionGuaranteeFund(models.Model):
    _inherit = 'construction.guarantee.fund'

    hold_by_intervention = fields.Boolean(
        string='Retenida por intervención', readonly=True, copy=False,
        help='La retuvo la intervención de la contrata: la liquidación final aplica los '
             'deductivos y la libera.')
    amount_charged = fields.Monetary(
        string='Cobrado por deductivos', readonly=True, copy=False, currency_field='currency_id',
        help='Lo descontado del fondo por los deductivos que superaron lo que quedaba por pagar '
             'en la liquidación final de la orden intervenida.')

    def _construction_release_intervention_hold(self, settlement):
        """El resto del fondo vuelve a sus requisitos de devolución."""
        funds = self.filtered('hold_by_intervention')
        if not funds:
            return
        funds.write({'hold': False, 'hold_reason': False, 'hold_by_intervention': False})
        for fund in funds:
            fund.message_post(body=self.env._(
                'Liquidación final %s: la retención por la intervención se levanta; la cuota '
                'sigue sus requisitos de devolución.', settlement.display_name))


class ConstructionResourcePlanAllocation(models.Model):
    _inherit = 'construction.resource.plan.allocation'

    contract_partner_id = fields.Many2one(
        related='purchase_line_id.partner_id', string='Contrata')
    contract_date_from = fields.Date(string='Desde', compute='_compute_contract_history')
    contract_date_to = fields.Date(string='Hasta', compute='_compute_contract_history')
    contract_status = fields.Selection(CONTRACT_STATUS, string='Estado de la contrata',
                                       compute='_compute_contract_history')

    def _compute_contract_history(self):
        for allocation in self:
            line = allocation.purchase_line_id
            order = line.order_id
            allocation.contract_date_from = line.date_planned and line.date_planned.date() \
                or (order.date_approve and order.date_approve.date())
            intervened = line.construction_intervention_date
            if order.state == 'cancel':
                status, end = 'cancel', False
            elif intervened:
                status, end = 'intervened', intervened
            elif order.construction_closed:
                liquidation = order.construction_liquidation_id
                status, end = 'closed', liquidation.settlement_date or liquidation.date_cutoff
            else:
                status, end = 'open', False
            allocation.contract_status = status
            allocation.contract_date_to = end


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_contract_history_ids = fields.Many2many(
        'construction.resource.plan.allocation', string='Contratas de la partida',
        compute='_compute_construction_contract_history_ids')

    def _compute_construction_contract_history_ids(self):
        """CR-20, punto 7: cada contrata que tuvo la partida (nodo con APU),
        con su orden, desde, hasta, cantidad y estado."""
        Allocation = self.env['construction.resource.plan.allocation']
        for task in self:
            if not task.id:
                task.construction_contract_history_ids = Allocation
                continue
            # sudo: el historial lee las órdenes de contrata aunque quien abre
            # la partida no administre compras; solo se muestran datos de la
            # asignación.
            allocations_sudo = Allocation.sudo().search([
                ('kind', '=', 'service_order'),
                '|', ('plan_line_id.task_id', '=', task.id),
                ('plan_line_id.space_task_id', '=', task.id)], order='id')
            task.construction_contract_history_ids = allocations_sudo.sudo(False)


class ConstructionContractSettlement(models.Model):
    _inherit = 'construction.contract.settlement'

    amount_fund_charge = fields.Monetary(
        string='Deductivos contra el fondo', readonly=True, copy=False,
        currency_field='currency_id',
        help='Liquidación final de una orden intervenida: los deductivos (sin IGV) que superan '
             'lo que queda por pagar y se descuentan del fondo de garantía.')
    fund_charge_move_id = fields.Many2one(
        'account.move', string='Nota de crédito del fondo', readonly=True, copy=False,
        index='btree_not_null', check_company=True)

    def _construction_charges_fund(self):
        self.ensure_one()
        return self.settlement_type == 'settlement' and self.uses_terms \
            and self.purchase_order_id.construction_intervened

    def _terms_amounts(self):
        """Liquidación final de una orden intervenida (D2): los deductivos que
        dejarían el pago en negativo no entran a la factura; van contra el
        fondo. Los deductivos que entran son los mayores que dejan el pago en
        cero o más."""
        rows, totals = super()._terms_amounts()
        totals['fund_charge'] = 0.0
        if not self._construction_charges_fund():
            return rows, totals
        currency = self.currency_id
        if currency.compare_amounts(totals['to_pay'], 0.0) >= 0:
            return rows, totals
        from .construction_contract_condition import compute_cascade
        lines = self.line_ids
        direct = currency.round(sum(lines.filtered(lambda l: not l.is_additional).mapped('amount')))
        additional = currency.round(sum(lines.filtered('is_additional').mapped('amount')))
        advance = totals['advance']
        deductions = totals['deductions']
        if currency.compare_amounts(deductions, 0.0) <= 0:
            return rows, totals

        def cascade(cents):
            return compute_cascade(self.terms_id, currency, direct, additional, cents / 100.0,
                                   advance=advance)

        def pays(cents):
            return currency.compare_amounts(cascade(cents)[1]['to_pay'], 0.0) >= 0

        low, high = 0, int(round(deductions * 100))
        if not pays(low):
            return rows, totals
        # Búsqueda por céntimos: el mayor deductivo que deja el pago en cero o
        # más (la cascada redondea por concepto, no es una fórmula cerrada).
        while low < high:
            middle = (low + high + 1) // 2
            if pays(middle):
                low = middle
            else:
                high = middle - 1
        rows, totals = cascade(low)
        totals['fund_charge'] = currency.round(deductions - low / 100.0)
        return rows, totals

    def _terms_recompute(self):
        res = super()._terms_recompute()
        for settlement in self.filtered('uses_terms'):
            if settlement.state not in OPEN_SETTLEMENT_STATES \
                    or settlement.settlement_type != 'settlement':
                continue
            charge = settlement._terms_amounts()[1].get('fund_charge', 0.0)
            if settlement.currency_id.compare_amounts(charge, settlement.amount_fund_charge):
                settlement.sudo().with_context(skip_validation_check=True).amount_fund_charge = \
                    charge
        return res

    def _construction_split_deductions(self):
        """[(deductivo, monto en la factura, monto contra el fondo)]: la
        factura toma los deductivos en su orden hasta lo que puede descontar;
        el resto va contra el fondo."""
        self.ensure_one()
        currency = self.currency_id
        remaining = currency.round(sum(self.deduction_ids.mapped('signed_amount'))
                                   - self.amount_fund_charge)
        result = []
        # En el orden de las líneas de la factura (_invoice_deduction_values).
        for deduction in self.deduction_ids:
            amount = deduction.signed_amount
            in_invoice = amount if amount < 0 else min(amount, max(remaining, 0.0))
            remaining = currency.round(remaining - in_invoice)
            result.append((deduction, currency.round(in_invoice),
                           currency.round(amount - in_invoice)))
        return result

    def _invoice_deduction_values(self, main):
        values = super()._invoice_deduction_values(main)
        if not values or self.currency_id.is_zero(self.amount_fund_charge):
            return values
        result = []
        for vals, (deduction, in_invoice, _charged) in zip(
                values, self._construction_split_deductions()):
            if self.currency_id.is_zero(in_invoice):
                continue
            result.append(dict(vals, price_unit=-in_invoice))
        return result

    def _create_payment_discount_entry(self, invoice):
        if self._deduction_mode() == 'payment_discount' \
                and not self.currency_id.is_zero(self.amount_fund_charge):
            raise UserError(self.env._(
                'Los deductivos de %s superan lo que queda por pagar: con deductivos descontados '
                'al pago, regístrelos en su propia línea de la factura para descontar la '
                'diferencia del fondo.', self.display_name))
        return super()._create_payment_discount_entry(invoice)

    def _create_invoice(self):
        invoice = super()._create_invoice()
        if self.uses_terms and not self.currency_id.is_zero(self.amount_fund_charge):
            self._construction_create_fund_charge(invoice)
        return invoice

    def _construction_create_fund_charge(self, invoice):
        """Nota de crédito del proveedor por los deductivos que van contra el
        fondo (CR-20, punto 6). Contabilidad la publica; al publicarla se
        concilia con las cuotas del fondo."""
        self.ensure_one()
        main = invoice.invoice_line_ids.filtered('purchase_line_id').sorted(
            lambda l: -abs(l.price_subtotal))[:1]
        po_main = self.purchase_order_id.order_line.filtered(lambda l: not l.display_type)[:1]
        taxes = main.tax_ids if main else po_main.tax_ids
        account = self.company_id.construction_deduction_account_id or main.account_id \
            or po_main.product_id.product_tmpl_id.with_company(
                self.company_id).get_product_accounts()['expense']
        lines = []
        for deduction, _in_invoice, charged in self._construction_split_deductions():
            if self.currency_id.is_zero(charged):
                continue
            lines.append(Command.create({
                'display_type': 'product',
                'name': self.env._('Deductivo %(name)s contra el fondo de garantía: %(text)s',
                                   name=deduction.name, text=deduction.description),
                'account_id': account.id,
                'quantity': 1.0,
                'price_unit': charged,
                'tax_ids': [Command.set(taxes.ids)],
                'analytic_distribution': deduction._analytic_distribution(),
            }))
        order = self.purchase_order_id
        refund = self.env['account.move'].with_company(self.company_id).with_context(
            default_move_type='in_refund').create({
                'move_type': 'in_refund',
                'partner_id': order.partner_id.id,
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'invoice_date': self.settlement_date or fields.Date.context_today(self),
                'ref': self.env._('Deductivos contra el fondo · %s', self.title or self.name),
                'invoice_origin': '%s, %s' % (order.name, self.name),
                'construction_fund_charge_settlement_id': self.id,
                'invoice_line_ids': lines,
            })
        self.sudo().with_context(skip_validation_check=True).fund_charge_move_id = refund
        self.message_post(body=self.env._(
            'Los deductivos superan lo que queda por pagar en %(amount)s (sin IGV): nota de '
            'crédito %(refund)s contra el fondo de garantía, por publicar.',
            amount=self.currency_id.format(self.amount_fund_charge),
            refund=refund.display_name))
        return refund

    def _action_approve(self):
        res = super()._action_approve()
        for settlement in self.filtered(lambda s: s.settlement_type == 'settlement'
                                        and s.state in VALUED_STATES):
            order = settlement.purchase_order_id
            if not order.construction_intervened or settlement.fund_charge_move_id:
                continue
            # Sin cobro contra el fondo, el fondo vuelve a sus requisitos.
            # sudo: quien aprueba la liquidación no administra el fondo.
            order.sudo().construction_guarantee_fund_ids._construction_release_intervention_hold(
                settlement)
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    construction_fund_charge_settlement_id = fields.Many2one(
        'construction.contract.settlement', string='Liquidación (cobro contra el fondo)',
        copy=False, readonly=True, index='btree_not_null')

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.filtered('construction_fund_charge_settlement_id')._construction_apply_fund_charge()
        return posted

    def _construction_apply_fund_charge(self):
        """Concilia la nota de crédito con las cuotas del fondo de la orden,
        de la más antigua a la más nueva; deja el cobro en cada cuota y levanta
        la retención de la intervención."""
        for refund in self:
            settlement = refund.construction_fund_charge_settlement_id
            order = settlement.purchase_order_id
            # sudo: lo publica contabilidad; el fondo y la liquidación son de
            # la contrata.
            funds_sudo = order.sudo().construction_guarantee_fund_ids.filtered(
                lambda f: f.move_line_id and not f.move_line_id.reconciled
                and f.move_line_id.parent_state == 'posted').sorted(
                lambda f: (f.date_maturity, f.id))
            refund_line = refund.line_ids.filtered(
                lambda l: l.display_type == 'payment_term' and not l.reconciled)
            charged = defaultdict(float)
            for fund in funds_sudo:
                if not refund_line or refund_line.reconciled:
                    break
                if fund.move_line_id.account_id != refund_line.account_id:
                    continue
                before = abs(fund.move_line_id.amount_residual_currency)
                (refund_line | fund.move_line_id).reconcile()
                charged[fund] += before - abs(fund.move_line_id.amount_residual_currency)
            for fund, amount in charged.items():
                fund.amount_charged += amount
                fund.message_post(body=self.env._(
                    'Cobro por deductivos de la liquidación final %(settlement)s: %(amount)s con '
                    'la nota de crédito %(refund)s.', settlement=settlement.display_name,
                    amount=fund.currency_id.format(amount), refund=refund.display_name))
            if refund_line and not refund_line.reconciled:
                settlement.sudo().message_post(body=self.env._(
                    'La nota de crédito %(refund)s supera el fondo por devolver: queda un saldo '
                    'de %(amount)s a favor de la empresa.', refund=refund.display_name,
                    amount=refund.currency_id.format(abs(refund_line.amount_residual_currency))))
            order.sudo().construction_guarantee_fund_ids._construction_release_intervention_hold(
                settlement)
