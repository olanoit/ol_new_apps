# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    pharmacy_presentation_id = fields.Many2one(
        'pharmacy.presentation', string='Presentación', readonly=True, index='btree_not_null',
        help='Presentación vendida (caja, blíster…). La cantidad de la línea va en unidades '
             'del producto y el precio unitario es el de la presentación entre sus unidades.')

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['pharmacy_presentation_id']


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _get_invoice_lines_values(self, line_values, pos_line, move_type):
        """La factura o boleta lleva la línea en la unidad de la presentación
        (1 Blíster x 7 a S/ 1,00) y no en unidades: el precio unitario de la
        línea del TPV (1,00 / 7) no cabe en los 2 decimales del precio de la
        factura y el comprobante no cuadraría con el ticket."""
        values = super()._get_invoice_lines_values(line_values, pos_line, move_type)
        presentation = pos_line.pharmacy_presentation_id
        if not presentation or 'product_id' not in values or not values.get('quantity'):
            return values
        count = presentation._get_quantity_in_presentations(abs(values['quantity']))
        if not count:
            # Cantidad suelta (no es un número entero de presentaciones): queda
            # en unidades, como cualquier línea del TPV.
            return values
        sign = -1 if values['quantity'] < 0 else 1
        values.update({
            'quantity': sign * count,
            'product_uom_id': presentation.uom_id.id,
            'price_unit': line_values['price_unit'] * presentation.factor,
        })
        extra = values.get('extra_tax_data')
        if extra and 'quantity' in extra:
            # Importes fijados a mano: se conservan con la nueva base.
            extra.update({
                'quantity': extra['quantity'] / presentation.factor,
                'price_unit': extra['price_unit'] * presentation.factor,
            })
        return values

    def _get_pharmacy_fraction_labels(self):
        """Rótulos de la venta fraccionada (DS 020-2024-SA, art. 48): una
        etiqueta por producto y lote vendidos por unidad suelta de un producto
        farmacéutico que tiene presentaciones (caja, blíster). Lleva el
        establecimiento, el producto, el laboratorio, la concentración, la vía,
        el lote y el vencimiento."""
        self.ensure_one()
        warehouse = self.config_id.picking_type_id.warehouse_id
        labels = []
        for line in self.lines:
            template = line.product_id.product_tmpl_id
            if (line.qty <= 0 or line.pharmacy_presentation_id or not template.pharmacy_ok
                    or not template.pharmacy_presentation_ids):
                continue
            lots = self.env['stock.lot']
            lot_names = line.pack_lot_ids.mapped('lot_name')
            if lot_names:
                lots = self.env['stock.lot'].search([
                    ('name', 'in', lot_names), ('product_id', '=', line.product_id.id),
                    '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)])
            for lot in lots or [False]:
                labels.append({
                    'product': line.product_id,
                    'quantity': line.qty,
                    'lot': lot,
                    'warehouse': warehouse,
                })
        return labels
