# -*- coding: utf-8 -*-
"""Orden de contrata con condiciones (requerimiento CREVAL v1.0, 3.4 y 3.6):
la copia de las condiciones y su esquema, los saldos de la orden, el adelanto
y los documentos y requisitos de la liquidación."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from .construction_contract_condition import compute_cascade

# Valorizaciones que cuentan como valorizado de la orden.
VALUED_STATES = ('approved', 'paid')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    construction_terms_id = fields.Many2one(
        'construction.contract.condition', string='Condiciones de contrata', copy=False,
        readonly=True, index='btree_not_null', check_company=True,
        help='La copia de las condiciones de la orden, con los porcentajes pactados.')
    construction_uses_terms = fields.Boolean(
        string='Con condiciones', compute='_compute_construction_uses_terms', store=True)
    construction_specialty = fields.Char(
        string='Especialidad', copy=False,
        help='Aparece en el título de cada valorizado («Valorizado 01 - especialidad»).')
    construction_representative_id = fields.Many2one(
        'res.partner', string='Representante del contratista', copy=False,
        help='Firma la conformidad del contratista en los documentos impresos.')
    construction_closed = fields.Boolean(string='Orden cerrada', copy=False, readonly=True,
                                         tracking=True)
    construction_amount_approved = fields.Monetary(
        string='Monto aprobado', copy=False, readonly=True, currency_field='currency_id',
        help='Total de la orden al confirmarla; un adicional que lo supere vuelve a aprobación '
             'por la diferencia.')
    # Copia de las condiciones (editables en la orden con lo pactado).
    construction_advance_pct = fields.Float(
        related='construction_terms_id.advance_pct', readonly=False, string='Adelanto (%)')
    construction_advance_method = fields.Selection(
        related='construction_terms_id.advance_method', readonly=False,
        string='Forma de amortizar')
    construction_advance_fixed_amount = fields.Monetary(
        related='construction_terms_id.advance_fixed_amount', readonly=False,
        string='Amortización fija')
    construction_guarantee_pct = fields.Float(
        related='construction_terms_id.guarantee_pct', readonly=False,
        string='Fondo de garantía (%)')
    construction_guarantee_base = fields.Selection(
        related='construction_terms_id.guarantee_base', readonly=False, string='Base del fondo')
    construction_guarantee_days = fields.Integer(
        related='construction_terms_id.guarantee_days', readonly=False,
        string='Plazo de devolución (días)')
    construction_guarantee_from = fields.Selection(
        related='construction_terms_id.guarantee_from', readonly=False, string='Plazo contado')
    construction_frequency = fields.Selection(
        related='construction_terms_id.frequency', readonly=False, string='Periodicidad')
    construction_cutoff_weekday = fields.Selection(
        related='construction_terms_id.cutoff_weekday', readonly=False,
        string='Día de corte semanal')
    construction_monthly_cutoff = fields.Selection(
        related='construction_terms_id.monthly_cutoff', readonly=False, string='Corte mensual')
    construction_cutoff_day = fields.Integer(
        related='construction_terms_id.cutoff_day', readonly=False, string='Día de corte del mes')
    construction_progress_tolerance_pct = fields.Float(
        related='construction_terms_id.progress_tolerance_pct', readonly=False,
        string='Tolerancia de avance (%)')
    construction_scheme_line_ids = fields.One2many(
        related='construction_terms_id.scheme_line_ids', readonly=False,
        string='Esquema de cálculo')
    construction_next_cutoff = fields.Date(
        string='Próximo corte', compute='_compute_construction_next_cutoff')
    construction_requirement_ids = fields.One2many(
        'construction.contract.order.requirement', 'order_id',
        string='Requisitos de devolución del fondo')
    construction_document_ids = fields.One2many(
        'construction.contract.order.document', 'order_id', string='Documentos requeridos')
    construction_advance_move_ids = fields.One2many(
        'account.move', 'construction_advance_order_id', string='Adelantos')
    construction_deduction_ids = fields.One2many(
        'construction.contract.deduction', 'purchase_order_id', string='Deductivos')
    construction_guarantee_fund_ids = fields.One2many(
        'construction.guarantee.fund', 'purchase_order_id', string='Fondos de garantía')
    # Saldos de la orden (con IGV).
    construction_amount_valued = fields.Monetary(
        string='Valorizado', compute='_compute_construction_balances', currency_field='currency_id')
    construction_amount_invoiced = fields.Monetary(
        string='Facturado', compute='_compute_construction_balances',
        currency_field='currency_id')
    construction_amount_paid = fields.Monetary(
        string='Pagado', compute='_compute_construction_balances', currency_field='currency_id')
    construction_amount_balance = fields.Monetary(
        string='Saldo', compute='_compute_construction_balances', currency_field='currency_id',
        help='Contractual menos valorizado, con IGV.')
    construction_advance_granted = fields.Monetary(
        string='Adelanto otorgado', compute='_compute_construction_balances',
        currency_field='currency_id', help='Facturas de adelanto publicadas, con IGV.')
    construction_advance_amortized = fields.Monetary(
        string='Adelanto amortizado', compute='_compute_construction_balances',
        currency_field='currency_id')
    construction_advance_to_amortize = fields.Monetary(
        string='Adelanto por amortizar', compute='_compute_construction_balances',
        currency_field='currency_id')
    construction_guarantee_retained = fields.Monetary(
        string='Fondo retenido', compute='_compute_construction_balances',
        currency_field='currency_id')
    construction_guarantee_returned = fields.Monetary(
        string='Fondo devuelto', compute='_compute_construction_balances',
        currency_field='currency_id')
    construction_progress_pct = fields.Float(
        string='Avance', compute='_compute_construction_balances',
        help='Costo directo valorizado entre el contractual.')
    construction_deduction_count = fields.Integer(
        string='Nº de deductivos', compute='_compute_construction_counts')
    construction_advance_count = fields.Integer(
        string='Nº de adelantos', compute='_compute_construction_counts')
    construction_can_register_advance = fields.Boolean(
        compute='_compute_construction_can_register_advance')
    # Carga inicial (3.14): lo que la orden traía antes de Odoo.
    construction_opening_valued = fields.Monetary(
        string='Valorizado anterior', copy=False, currency_field='currency_id')
    construction_opening_invoiced = fields.Monetary(
        string='Facturado anterior', copy=False, currency_field='currency_id')
    construction_opening_paid = fields.Monetary(
        string='Pagado anterior', copy=False, currency_field='currency_id')
    construction_opening_advance_granted = fields.Monetary(
        string='Adelanto otorgado anterior', copy=False, currency_field='currency_id')
    construction_opening_advance_amortized = fields.Monetary(
        string='Adelanto amortizado anterior', copy=False, currency_field='currency_id')

    @api.depends('construction_terms_id')
    def _compute_construction_uses_terms(self):
        for order in self:
            order.construction_uses_terms = bool(order.construction_terms_id)

    def _compute_construction_counts(self):
        for order in self:
            order.construction_deduction_count = len(order.construction_deduction_ids)
            order.construction_advance_count = len(order.construction_advance_move_ids)

    @api.depends('state', 'construction_advance_pct', 'construction_advance_move_ids.state')
    def _compute_construction_can_register_advance(self):
        for order in self:
            order.construction_can_register_advance = (
                order.construction_uses_terms and order.state == 'purchase'
                and order.construction_advance_pct > 0
                and not order.construction_advance_move_ids.filtered(
                    lambda m: m.state == 'posted'))

    def _construction_valued_settlements(self):
        return self.construction_settlement_ids.filtered(
            lambda s: s.state in VALUED_STATES or (s.settlement_type == 'opening'
                                                   and s.state != 'cancel'))

    def _compute_construction_balances(self):
        for order in self:
            settlements = order._construction_valued_settlements().filtered(
                lambda s: s.settlement_type != 'opening')
            invoices = settlements.invoice_id.filtered(lambda m: m.state == 'posted')
            advances = order.construction_advance_move_ids.filtered(lambda m: m.state == 'posted')
            granted = order.construction_opening_advance_granted + sum(
                advances.mapped(lambda m: m.amount_total * (-1 if m.move_type == 'in_refund'
                                                            else 1)))
            amortized = order.construction_opening_advance_amortized + sum(
                settlements.mapped('amount_advance'))
            funds = order.construction_guarantee_fund_ids
            order.construction_amount_valued = order.construction_opening_valued + sum(
                settlements.mapped('amount_total'))
            order.construction_amount_invoiced = order.construction_opening_invoiced + sum(
                (invoices | advances).mapped('amount_total'))
            order.construction_amount_paid = order.construction_opening_paid + sum(
                (invoices | advances).mapped(lambda m: m.amount_total - m.amount_residual))
            order.construction_amount_balance = order.amount_total \
                - order.construction_amount_valued
            order.construction_advance_granted = granted
            order.construction_advance_amortized = amortized
            order.construction_advance_to_amortize = max(granted - amortized, 0.0)
            order.construction_guarantee_retained = sum(funds.mapped('amount'))
            order.construction_guarantee_returned = sum(
                funds.mapped(lambda f: f.amount - f.amount_residual))
            direct = sum(order.order_line.filtered(
                lambda l: not l.construction_is_additional).mapped('price_subtotal'))
            valued_direct = sum(order._construction_valued_settlements().mapped('amount_direct'))
            order.construction_progress_pct = valued_direct / direct if direct else 0.0

    def _compute_construction_next_cutoff(self):
        Settlement = self.env['construction.contract.settlement']
        today = fields.Date.context_today(self)
        for order in self:
            if not order.construction_uses_terms or order.construction_frequency == 'end':
                order.construction_next_cutoff = False
                continue
            start = Settlement._terms_next_start(order) or today
            order.construction_next_cutoff = Settlement._terms_period_end(order, start)

    # ------------------------------------------------------------------
    # Condiciones
    # ------------------------------------------------------------------
    def _construction_apply_terms(self, condition, overrides=None):
        """Copia ``condition`` a la orden (una sola vez) con lo pactado, y
        crea sus requisitos de devolución y documentos requeridos."""
        self.ensure_one()
        if self.construction_terms_id:
            if overrides:
                self.construction_terms_id.write(overrides)
            return self.construction_terms_id
        terms = condition._copy_for_order(self, overrides)
        self.write({
            'construction_terms_id': terms.id,
            'construction_requirement_ids': [
                Command.create({'requirement_id': req.id}) for req in terms.requirement_ids],
            'construction_document_ids': [
                Command.create({'document_type_id': doc.id}) for doc in terms.document_type_ids],
        })
        return terms

    def _construction_progress_domain(self):
        """Avances validados de la contrata en la obra de la orden."""
        self.ensure_one()
        return [('project_id', '=', self.construction_project_id.id),
                ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
                ('state', '=', 'validated')]

    def construction_contract_cascade(self):
        """Resumen contractual de la orden con su esquema: costo directo,
        adicionales, ajustes, IGV, total, adelanto y fondo."""
        self.ensure_one()
        direct = sum(self.order_line.filtered(
            lambda l: not l.construction_is_additional).mapped('price_subtotal'))
        additional = sum(self.order_line.filtered('construction_is_additional').mapped(
            'price_subtotal'))
        return compute_cascade(self.construction_terms_id, self.currency_id, direct, additional,
                               0.0)

    def button_confirm(self):
        res = super().button_confirm()
        for order in self.filtered(lambda o: o.construction_is_service_order
                                   and o.state in ('purchase', 'done')):
            order.construction_amount_approved = order.amount_total
        return res

    # ------------------------------------------------------------------
    # Adelanto (3.6)
    # ------------------------------------------------------------------
    def action_construction_register_advance(self):
        """Factura de adelanto en borrador: el producto de anticipo, base =
        adelanto (%) × subtotal sin IGV de la orden y la analítica de la
        obra."""
        self.ensure_one()
        if not self.construction_can_register_advance:
            raise UserError(self.env._(
                'La orden %s no tiene adelanto por registrar: necesita condiciones con adelanto, '
                'estar confirmada y no tener un adelanto publicado.', self.name))
        product = self.company_id.construction_advance_product_id
        if not product:
            raise UserError(self.env._(
                'Configure el producto de anticipo a contratistas en Ajustes › Planificación de '
                'obra.'))
        # El subtotal contractual sin IGV: costo directo y adicionales con sus
        # ajustes de precio, según el esquema de la orden.
        _rows, totals = self.construction_contract_cascade()
        amount = self.currency_id.round(totals['subtotal'] * self.construction_advance_pct / 100.0)
        account = self.construction_project_id.account_id
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.name,
            'ref': self.env._('Adelanto %s', self.name),
            'construction_advance_order_id': self.id,
            'invoice_line_ids': [Command.create({
                'product_id': product.id,
                'name': self.env._('Adelanto de la orden %(order)s (%(pct)s %%)', order=self.name,
                                   pct=round(self.construction_advance_pct, 2)),
                'quantity': 1.0,
                'price_unit': amount,
                'tax_ids': [Command.set(product.supplier_taxes_id.filtered(
                    lambda t: t.company_id in self.company_id.parent_ids | self.company_id).ids)],
                'analytic_distribution': {str(account.id): 100.0} if account else False,
            })],
        })
        self._construction_set_advance_detraction(move)
        self.message_post(body=self.env._('Adelanto registrado en borrador: %s.', move.display_name))
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': move.id,
                'view_mode': 'form'}

    def _construction_set_advance_detraction(self, move):
        """Con detracciones (al_l10n_pe_detraction), el adelanto lleva el
        código del servicio de la orden (3.6): el producto de anticipo es el
        mismo para todos los servicios y no tiene código propio."""
        if 'l10n_pe_detraction_type_id' not in move._fields or move.l10n_pe_detraction_type_id:
            return
        types = self.env['l10n_pe.detraction.type']
        for template in self.order_line.product_id.product_tmpl_id:
            types |= template._l10n_pe_detraction_type()
        if types:
            move.l10n_pe_detraction_type_id = max(types, key=lambda t: t.percentage)

    def action_view_construction_advances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Adelantos de %s', self.name),
            'res_model': 'account.move', 'view_mode': 'list,form',
            'domain': [('construction_advance_order_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_view_construction_deductions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Deductivos de %s', self.name),
            'res_model': 'construction.contract.deduction', 'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id},
        }

    def action_view_construction_payments(self):
        """Pagos de la orden: el adelanto y cada valorizado con su factura."""
        self.ensure_one()
        moves = self.construction_advance_move_ids | self.construction_settlement_ids.invoice_id
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Pagos de %s', self.name),
            'res_model': 'account.move', 'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
            'context': {'create': False},
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    construction_task_id = fields.Many2one(
        'project.task', string='Partida', copy=False, index='btree_not_null', check_company=True)
    construction_is_additional = fields.Boolean(
        string='Adicional', copy=False,
        help='Ampliación del alcance por un cambio de obra aprobado.')
    construction_plan_balance = fields.Float(
        string='Saldo del plan', compute='_compute_construction_plan_balance',
        digits='Product Unit',
        help='Planificado menos lo asignado de las líneas del plan de la partida.')

    def _compute_construction_plan_balance(self):
        for line in self:
            # sudo: quien aprueba la orden no siempre lee el plan.
            plan_lines = line.sudo().construction_allocation_ids.plan_line_id
            line.construction_plan_balance = sum(
                l.qty_planned - l.qty_requested for l in plan_lines)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    construction_condition_id = fields.Many2one(
        'construction.contract.condition', string='Condiciones de contrata',
        company_dependent=True, domain=[('order_id', '=', False)],
        help='Las que propone «Asignar contrata» para este contratista.')


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_default_condition_id = fields.Many2one(
        'construction.contract.condition', string='Condiciones de contrata por defecto',
        domain=[('order_id', '=', False)], check_company=True)
    construction_advance_product_id = fields.Many2one(
        'product.product', string='Producto de anticipo a contratistas', check_company=True,
        help='Servicio con la cuenta de anticipos otorgados: la factura de adelanto y la línea de '
             'regularización de cada valorizado.')
    construction_deduction_account_id = fields.Many2one(
        'account.account', string='Cuenta de deductivos a contratas', check_company=True,
        help='Deductivo en la factura (línea propia) o descontado al pago. Vacía: la cuenta del '
             'servicio.')
    construction_deduction_journal_id = fields.Many2one(
        'account.journal', string='Diario del descuento al pago', check_company=True,
        domain="[('type', '=', 'general')]",
        help='Asiento de los deductivos que se descuentan al pago de la factura.')
