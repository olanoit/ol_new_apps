# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, formatLang

BASES = [
    ('weighted_6m', 'Ponderado de 6 meses'),
    ('weighted_3m', 'Ponderado de 3 meses'),
    ('moving_4w', 'Media móvil de 4 semanas'),
    ('last', 'Último precio de compra'),
    ('manual', 'Manual'),
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
    price_moving_4w = fields.Monetary(
        string='Media móvil 4 semanas', compute='_compute_suggestions',
        currency_field='currency_id',
        help='Ponderado de la semana de la base y las 3 anteriores (semanas de la obra).')
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

    @api.depends('product_id', 'basis_date', 'line_ids')
    def _compute_suggestions(self):
        Report = self.env['construction.purchase.price.report']
        for wizard in self:
            wizard.price_current = wizard.line_ids[:1].price_unit_planned
            if not wizard.product_id or not wizard.basis_date:
                wizard.price_last = wizard.price_weighted_3m = wizard.price_weighted_6m = 0.0
                wizard.price_moving_4w = 0.0
                wizard.purchase_count = 0
                continue
            # Las mismas cifras que «Precios de compra del producto» (P-16).
            prices = Report._get_basis_prices(
                wizard.product_id, wizard.plan_id.company_id, wizard.basis_date,
                wizard.plan_id.project_id.construction_week_start_day or '3')
            wizard.price_last = prices['last']
            wizard.price_weighted_6m = prices['weighted_6m']
            wizard.price_weighted_3m = prices['weighted_3m']
            wizard.price_moving_4w = prices['moving_4w']
            wizard.purchase_count = prices['count_6m']

    @api.depends('basis', 'price_last', 'price_weighted_3m', 'price_weighted_6m',
                 'price_moving_4w', 'price_current')
    def _compute_price_unit(self):
        for wizard in self:
            suggestion = {
                'last': wizard.price_last,
                'weighted_3m': wizard.price_weighted_3m,
                'weighted_6m': wizard.price_weighted_6m,
                'moving_4w': wizard.price_moving_4w,
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

    def action_open_purchase_prices(self):
        """P-16 del producto, con las mismas líneas destino para volver aquí
        con la base elegida."""
        self.ensure_one()
        return self.env['construction.purchase.price.analysis']._action_open(
            self.product_id, plan=self.plan_id, lines=self.line_ids)
