# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, formatLang

BASES = [
    ('manual', 'Manual'),
    ('last', 'Último precio de compra'),
    ('weighted_3m', 'Ponderado de 3 meses'),
    ('weighted_6m', 'Ponderado de 6 meses'),
]


class ConstructionPlanPriceWizard(models.TransientModel):
    """Aplicar costo (W-12): el planificador fija el costo de un producto en
    las líneas en borrador del plan y deja anotada la base que usó."""
    _name = 'construction.plan.price.wizard'
    _description = 'Aplicar costo a las líneas del plan'
    _check_company_auto = True

    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', required=True, readonly=True,
        check_company=True)
    company_id = fields.Many2one(related='plan_id.company_id', string='Compañía')
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Moneda')
    allowed_product_ids = fields.Many2many(
        'product.product', string='Productos del plan', compute='_compute_allowed_product_ids',
        check_company=True)
    product_id = fields.Many2one(
        'product.product', string='Producto', required=True, check_company=True,
        domain="[('id', 'in', allowed_product_ids)]")
    basis = fields.Selection(BASES, string='Base', required=True, default='weighted_6m')
    basis_date = fields.Date(
        string='Fecha de la base', required=True, default=fields.Date.context_today,
        help='Las compras confirmadas hasta esta fecha forman la base.')
    price_last = fields.Monetary(
        string='Último precio', compute='_compute_suggestions', currency_field='currency_id')
    price_weighted_3m = fields.Monetary(
        string='Ponderado 3 meses', compute='_compute_suggestions', currency_field='currency_id')
    price_weighted_6m = fields.Monetary(
        string='Ponderado 6 meses', compute='_compute_suggestions', currency_field='currency_id')
    purchase_count = fields.Integer(
        string='Compras en 6 meses', compute='_compute_suggestions')
    price_current = fields.Monetary(
        string='Costo actual', compute='_compute_suggestions', currency_field='currency_id',
        help='Costo que tienen hoy las líneas destino (el primero si difieren).')
    price_unit = fields.Monetary(
        string='Costo que se aplica', required=True, currency_field='currency_id',
        compute='_compute_price_unit', store=True, readonly=False, precompute=True,
        help='Lo escribe el planificador; la base solo lo sugiere.')
    line_ids = fields.Many2many(
        'construction.resource.plan.line', 'construction_plan_price_wizard_line_rel',
        'wizard_id', 'line_id', string='Líneas destino', check_company=True,
        compute='_compute_line_ids', store=True, readonly=False, precompute=True,
        domain="[('plan_id', '=', plan_id), ('product_id', '=', product_id)]")

    @api.depends('plan_id')
    def _compute_allowed_product_ids(self):
        for wizard in self:
            wizard.allowed_product_ids = wizard.plan_id.line_ids.product_id

    @api.depends('plan_id', 'product_id')
    def _compute_line_ids(self):
        for wizard in self:
            wizard.line_ids = wizard.plan_id.line_ids.filtered(
                lambda l: l.product_id == wizard.product_id)

    def _get_purchase_prices(self, date_from):
        """[(fecha, cantidad, precio)] de las compras confirmadas del producto
        entre ``date_from`` y la fecha de la base, en la unidad del producto y
        en la moneda de la compañía (al tipo de cambio de cada compra)."""
        self.ensure_one()
        company = self.plan_id.company_id
        date_to = fields.Datetime.to_datetime(self.basis_date) + relativedelta(days=1)
        domain = [
            ('product_id', '=', self.product_id.id), ('state', '=', 'purchase'),
            ('company_id', '=', company.id), ('display_type', '=', False),
            ('order_id.date_approve', '<', date_to),
        ]
        if date_from:
            domain.append(('order_id.date_approve', '>=', fields.Datetime.to_datetime(date_from)))
        prices = []
        for line in self.env['purchase.order.line'].search(domain, order='date_approve, id'):
            date = line.order_id.date_approve.date()
            qty = line.product_uom_id._compute_quantity(line.product_qty, line.product_id.uom_id)
            price = line.product_uom_id._compute_price(
                line.price_unit_discounted, line.product_id.uom_id)
            price = line.currency_id._convert(price, company.currency_id, company, date)
            prices.append((date, qty, price))
        return prices

    @staticmethod
    def _weighted(prices):
        qty = sum(q for _d, q, _p in prices)
        return sum(q * p for _d, q, p in prices) / qty if qty else 0.0

    @api.depends('product_id', 'basis_date', 'line_ids')
    def _compute_suggestions(self):
        for wizard in self:
            wizard.price_current = wizard.line_ids[:1].price_unit_planned
            if not wizard.product_id or not wizard.basis_date:
                wizard.price_last = wizard.price_weighted_3m = wizard.price_weighted_6m = 0.0
                wizard.purchase_count = 0
                continue
            prices = wizard._get_purchase_prices(False)
            last = prices[-1][2] if prices else 0.0
            since_6m = wizard.basis_date - relativedelta(months=6)
            since_3m = wizard.basis_date - relativedelta(months=3)
            last_6m = [p for p in prices if p[0] >= since_6m]
            wizard.price_last = last
            wizard.price_weighted_6m = self._weighted(last_6m)
            wizard.price_weighted_3m = self._weighted([p for p in prices if p[0] >= since_3m])
            wizard.purchase_count = len(last_6m)

    @api.depends('basis', 'price_last', 'price_weighted_3m', 'price_weighted_6m',
                 'price_current')
    def _compute_price_unit(self):
        for wizard in self:
            suggestion = {
                'last': wizard.price_last,
                'weighted_3m': wizard.price_weighted_3m,
                'weighted_6m': wizard.price_weighted_6m,
            }.get(wizard.basis)
            wizard.price_unit = suggestion if suggestion else (
                wizard.price_unit or wizard.price_current)

    def _get_basis_text(self):
        self.ensure_one()
        label = dict(BASES)[self.basis]
        return self.env._('%(basis)s al %(date)s: %(price)s', basis=label,
                          date=format_date(self.env, self.basis_date),
                          price=formatLang(self.env, self.price_unit, digits=2))

    def action_apply(self):
        self.ensure_one()
        self.plan_id._check_draft()
        if self.currency_id.compare_amounts(self.price_unit, 0) <= 0:
            raise UserError(self.env._('Escriba un costo mayor que cero.'))
        lines = self.line_ids.filtered(lambda l: l.product_id == self.product_id)
        if not lines:
            raise UserError(self.env._('Elija las líneas del plan a las que se aplica el costo.'))
        lines.write({
            'price_unit_planned': self.price_unit,
            'price_basis': self._get_basis_text(),
            'price_basis_date': self.basis_date,
        })
        self.plan_id.message_post(body=self.env._(
            'Costo de %(product)s: %(basis)s (%(count)s líneas).',
            product=self.product_id.display_name, basis=self._get_basis_text(),
            count=len(lines)))
        return {'type': 'ir.actions.act_window_close'}
