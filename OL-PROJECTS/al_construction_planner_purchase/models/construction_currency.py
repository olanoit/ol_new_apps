# -*- coding: utf-8 -*-
"""Partidas en otra moneda (requerimiento CREVAL v1.0, 6.5): la compra masiva de
una línea del plan en dólares lleva su moneda y su costo al requerimiento de
compra, la orden se crea en dólares y el control se lleva en la moneda de la
obra con el tipo de cambio de la fecha de cada orden, con la diferencia de
cambio frente a lo planificado aparte del desvío de precio."""
from odoo import fields, models

PURCHASE_ORDER_STATES = ('purchase', 'done')


class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    construction_currency_id = fields.Many2one(
        'res.currency', string='Moneda del plan', readonly=True, copy=False)
    construction_price_unit_currency = fields.Float(
        string='Costo del plan en su moneda', digits='Product Price', readonly=True, copy=False)


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _inherit = 'purchase.request.line.make.purchase.order'

    def _construction_currency(self):
        currencies = self.item_ids.line_id.construction_currency_id
        return currencies if len(currencies) == 1 else self.env['res.currency']

    def _prepare_purchase_order(self, picking_type, company, origin):
        data = super()._prepare_purchase_order(picking_type, company, origin)
        currency = self._construction_currency()
        if currency and currency != company.currency_id:
            data['currency_id'] = currency.id
        return data

    def make_purchase_order(self):
        res = super().make_purchase_order()
        # Sin precio del proveedor, la línea de la orden en la moneda del plan
        # toma el costo planificado en esa moneda.
        for item in self.item_ids:
            line = item.line_id
            if not line.construction_currency_id or not line.construction_price_unit_currency:
                continue
            for po_line in line.purchase_lines.filtered(
                    lambda p: p.state == 'draft'
                    and p.currency_id == line.construction_currency_id
                    and not p.product_id._select_seller(partner_id=p.partner_id,
                                                        quantity=p.product_qty)):
                po_line.price_unit = line.construction_price_unit_currency
        return res


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    amount_fx_diff = fields.Monetary(
        string='Diferencia de cambio', compute='_compute_construction_fx',
        currency_field='currency_id',
        help='Lo comprado en la moneda del costo al tipo de cambio de cada orden frente al del '
             'plan (aparte del desvío de precio).')
    amount_price_diff = fields.Monetary(
        string='Desvío de precio', compute='_compute_construction_fx',
        currency_field='currency_id',
        help='Precio de la orden frente al costo del plan, en la moneda del costo, convertido al '
             'tipo de cambio de la orden.')

    def _construction_fx_rows(self):
        """[(cantidad, línea de la OC)] de lo comprado de la línea."""
        self.ensure_one()
        rows = []
        for allocation in self.allocation_ids.filtered(
                lambda a: a.kind == 'purchase_request' and a.state != 'cancel'):
            # sudo: el control lo ve quien planifica aunque no lea compras.
            po_lines = allocation.sudo().purchase_request_line_id.purchase_lines.filtered(
                lambda p: p.state in PURCHASE_ORDER_STATES)
            if po_lines:
                rows.append((allocation.qty_allocated, po_lines[0]))
        return rows

    def _compute_construction_fx(self):
        for line in self:
            fx = price_diff = 0.0
            if line.is_foreign_currency:
                company = line.plan_id.company_id or self.env.company
                currency = line.price_currency_id
                plan_rate = currency._get_conversion_rate(
                    currency, company.currency_id, company, line._construction_plan_rate_date())
                for qty, po_line in line._construction_fx_rows():
                    date = po_line.order_id.date_approve or po_line.order_id.date_order
                    rate = currency._get_conversion_rate(
                        currency, company.currency_id, company, fields.Date.to_date(date))
                    fx += qty * line.price_unit_currency * (rate - plan_rate)
                    if po_line.currency_id == currency:
                        price_diff += qty * (po_line.price_unit - line.price_unit_currency) * rate
            line.amount_fx_diff = line.currency_id.round(fx)
            line.amount_price_diff = line.currency_id.round(price_diff)

    def _get_line_execution(self):
        """Con un costo en otra moneda, el comprometido lleva el tipo de cambio
        de cada orden (el planificado, el del plan)."""
        result = super()._get_line_execution()
        for line in self.filtered('is_foreign_currency'):
            committed, actual = result[line]
            result[line] = (committed + line.amount_fx_diff, actual)
        return result
