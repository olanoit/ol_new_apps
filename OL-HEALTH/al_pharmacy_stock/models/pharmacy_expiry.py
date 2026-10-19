# -*- coding: utf-8 -*-
"""Precio por vencer: escalas de descuento por días al vencimiento. La caja
aplica el descuento al vender un lote cercano al vencimiento; un lote vencido
nunca se vende (ver el estado sanitario del lote)."""
from odoo import api, fields, models


class PharmacyExpiryDiscount(models.Model):
    _name = 'pharmacy.expiry.discount'
    _description = 'Escala de descuento por vencer'
    _order = 'company_id, categ_id, days, id'
    _check_company_auto = True

    days = fields.Integer(
        string='Hasta días al vencimiento', required=True,
        help='Se aplica a los lotes que vencen en este número de días o menos. Si un lote '
             'entra en varias escalas, vale la de menos días.')
    discount = fields.Float(string='Descuento (%)', required=True, digits='Discount')
    categ_id = fields.Many2one(
        'product.category', string='Categoría',
        help='Opcional: solo para los productos de esta categoría y sus subcategorías. Una '
             'escala con categoría tiene prioridad sobre las generales.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)

    _check_days = models.Constraint('CHECK(days > 0)', 'Los días deben ser mayores que cero.')
    _check_discount = models.Constraint(
        'CHECK(discount > 0 AND discount <= 100)', 'El descuento debe estar entre 0 y 100 %.')

    @api.depends('days', 'discount', 'categ_id')
    def _compute_display_name(self):
        for scale in self:
            name = self.env._('Hasta %(days)s días: -%(discount)s %%', days=scale.days,
                              discount=scale.discount)
            scale.display_name = f'{name} ({scale.categ_id.display_name})' if scale.categ_id else name

    @api.model
    def _pharmacy_discount_for(self, product, days_left, company):
        """Descuento (%) para un lote del producto que vence en ``days_left``
        días; 0 si no entra en ninguna escala."""
        if days_left is None or days_left < 0:
            return 0.0
        scales = self.search([('company_id', '=', company.id), ('days', '>=', days_left)])
        categ_path = product.categ_id.parent_path or ''
        specific = scales.filtered(
            lambda s: s.categ_id and categ_path.startswith(s.categ_id.parent_path))
        candidates = specific or scales.filtered(lambda s: not s.categ_id)
        if not candidates:
            return 0.0
        return candidates.sorted(lambda s: (s.days, -s.discount))[0].discount


class StockLot(models.Model):
    _inherit = 'stock.lot'

    pharmacy_days_to_expiry = fields.Integer(
        string='Días al vencimiento', compute='_compute_pharmacy_expiry_price')
    pharmacy_expiry_discount = fields.Float(
        string='Descuento por vencer (%)', compute='_compute_pharmacy_expiry_price',
        digits='Discount')
    pharmacy_suggested_price = fields.Float(
        string='Precio sugerido', compute='_compute_pharmacy_expiry_price',
        digits='Product Price', help='Precio de venta con el descuento por vencer.')

    @api.depends('expiration_date', 'product_id.lst_price', 'company_id')
    @api.depends_context('company')
    def _compute_pharmacy_expiry_price(self):
        Scale = self.env['pharmacy.expiry.discount']
        today = fields.Date.context_today(self)
        for lot in self:
            days_left = (fields.Date.to_date(lot.expiration_date) - today).days \
                if lot.expiration_date else None
            discount = Scale._pharmacy_discount_for(
                lot.product_id, days_left, lot.company_id or self.env.company)
            lot.pharmacy_days_to_expiry = days_left or 0
            lot.pharmacy_expiry_discount = discount
            lot.pharmacy_suggested_price = lot.product_id.lst_price * (1 - discount / 100)

    def _pharmacy_is_expired(self):
        self.ensure_one()
        return self.pharmacy_state == 'expired' or bool(
            self.expiration_date and self.expiration_date < fields.Datetime.now())
