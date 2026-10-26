# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import frozendict


class AccountMove(models.Model):
    _inherit = 'account.move'

    construction_settlement_ids = fields.One2many(
        'construction.contract.settlement', 'invoice_id', string='Liquidaciones de contrata')
    # Adelanto a la contrata (CREVAL v1.0, 3.6): la factura de anticipo de la
    # orden de contrata.
    construction_advance_order_id = fields.Many2one(
        'purchase.order', string='Adelanto de la orden', copy=False, index='btree_not_null',
        check_company=True, readonly=True)
    # Fondo de garantía (3.8): la cuenta por pagar se divide en el neto, con
    # vencimiento el día de pago, y el fondo, con su propio vencimiento. El
    # monto lo fija la valorización: un plazo de pago por porcentaje se
    # aplicaría sobre el total de la factura, ya amortizado el adelanto.
    construction_guarantee_amount = fields.Monetary(
        string='Fondo de garantía', copy=False, readonly=True, currency_field='currency_id')
    construction_guarantee_date = fields.Date(
        string='Vencimiento del fondo', copy=False, readonly=True)
    construction_guarantee_fund_ids = fields.One2many(
        'construction.guarantee.fund', 'move_id', string='Fondos de garantía')
    # Factura corregida o registrada a mano: avisa si no suma lo mismo que su
    # valorización (CR-11).
    construction_valuation_difference = fields.Monetary(
        string='Diferencia con la valorización', compute='_compute_construction_valuation_difference',
        currency_field='currency_id')

    @api.depends('amount_total', 'construction_settlement_ids.amount_total',
                 'construction_settlement_ids.amount_advance')
    def _compute_construction_valuation_difference(self):
        for move in self:
            # sudo: quien registra la factura (contabilidad) no siempre ve las
            # valorizaciones; solo se leen sus totales.
            valuations_sudo = move.sudo().construction_settlement_ids.filtered(
                lambda s: s.uses_terms and s.state != 'cancel')
            if not valuations_sudo:
                move.construction_valuation_difference = 0.0
                continue
            expected = sum(valuations_sudo.mapped('amount_total')) \
                - sum(valuations_sudo.mapped('amount_advance'))
            move.construction_valuation_difference = move.currency_id.round(
                move.amount_total - expected)

    @api.depends('construction_guarantee_amount', 'construction_guarantee_date')
    def _compute_needed_terms(self):
        super()._compute_needed_terms()
        for invoice in self:
            amount = invoice.construction_guarantee_amount
            if not amount or invoice.invoice_payment_term_id \
                    or not invoice.construction_guarantee_date or len(invoice.needed_terms) != 1:
                continue
            key, values = next(iter(invoice.needed_terms.items()))
            sign = -1 if values['balance'] < 0 else 1
            currency = invoice.currency_id
            fund_currency = sign * currency.round(amount)
            rate = values['balance'] / values['amount_currency'] if values['amount_currency'] \
                else 1.0
            fund_balance = invoice.company_currency_id.round(fund_currency * rate)
            fund_key = frozendict(dict(key, date_maturity=invoice.construction_guarantee_date))
            if fund_key == key:
                continue
            invoice.needed_terms = {
                key: dict(values, balance=values['balance'] - fund_balance,
                          amount_currency=values['amount_currency'] - fund_currency),
                fund_key: dict(values, balance=fund_balance, amount_currency=fund_currency),
            }

    def _compute_payment_state(self):
        super()._compute_payment_state()
        # La liquidación pasa a «Pagada» cuando su factura queda pagada. La
        # escribe el sistema: quien concilia el pago (tesorería) no tiene por
        # qué tener acceso al planificador.
        settlements_sudo = self.sudo().construction_settlement_ids.filtered(
            lambda s: s.state in ('approved', 'paid'))
        if settlements_sudo:
            settlements_sudo._sync_paid()

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted._construction_create_guarantee_funds()
        return posted

    def _construction_create_guarantee_funds(self):
        """Una fila de fondo de garantía por cuota de fondo publicada."""
        Fund = self.env['construction.guarantee.fund'].sudo()
        for move in self.filtered(lambda m: m.construction_guarantee_amount
                                  and m.construction_guarantee_date):
            settlement = move.construction_settlement_ids[:1]
            order = settlement.purchase_order_id
            if not order or move.construction_guarantee_fund_ids:
                continue
            line = move.line_ids.filtered(
                lambda l: l.display_type == 'payment_term'
                and l.date_maturity == move.construction_guarantee_date)[:1]
            # sudo: lo publica contabilidad, que no administra contratas; la
            # fila solo resume la cuota de su propia factura.
            Fund.create({
                'purchase_order_id': order.id, 'settlement_id': settlement.id,
                'move_id': move.id, 'move_line_id': line.id,
                'amount': move.construction_guarantee_amount,
                'date_maturity': move.construction_guarantee_date,
            })
