# -*- coding: utf-8 -*-
"""Bonificaciones de compra («12+1»): la línea bonificada se agrega como una
línea hermana a precio cero. Así la factura del proveedor cuadra (la
bonificación va a 0) y el costo se prorratea solo: el costo promedio (o la
capa FIFO) suma las unidades bonificadas sin costo."""
from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    pharmacy_bonus_qty = fields.Float(
        string='Bonificación', digits='Product Unit', default=0.0,
        help='Unidades que el proveedor entrega sin costo por esta línea (p. ej. 1 por cada 12).')
    pharmacy_bonus_of_id = fields.Many2one(
        'purchase.order.line', string='Bonificación de', ondelete='cascade', index='btree_not_null',
        readonly=True, copy=False)
    pharmacy_bonus_line_ids = fields.One2many('purchase.order.line', 'pharmacy_bonus_of_id',
                                              string='Líneas de bonificación')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered('pharmacy_bonus_qty')._pharmacy_sync_bonus_line()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'pharmacy_bonus_qty' in vals or 'product_id' in vals:
            self.filtered(lambda line: not line.pharmacy_bonus_of_id)._pharmacy_sync_bonus_line()
        return res

    def _pharmacy_sync_bonus_line(self):
        for line in self:
            bonus = line.pharmacy_bonus_line_ids[:1]
            if not line.pharmacy_bonus_qty:
                if bonus and bonus.state == 'draft':
                    bonus.unlink()
                continue
            values = {
                'product_qty': line.pharmacy_bonus_qty,
                'price_unit': 0.0,
                'name': self.env._('Bonificación: %s', line.name),
            }
            if bonus:
                bonus.write(values)
            else:
                self.create({
                    **values,
                    'order_id': line.order_id.id,
                    'product_id': line.product_id.id,
                    'uom_id': line.uom_id.id,  # Odoo 20: UdM de la línea de compra
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                    'date_planned': line.date_planned,
                    'pharmacy_bonus_of_id': line.id,
                    'sequence': line.sequence,
                })
