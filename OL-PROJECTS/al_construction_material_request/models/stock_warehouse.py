# -*- coding: utf-8 -*-
"""Consumo interno del almacén (paquete 1.11, M111-10): los requerimientos
internos de las áreas salen a una ubicación de consumo con su propio tipo de
operación, uno por almacén."""
from odoo import _, fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    construction_consumption_location_id = fields.Many2one(
        'stock.location', string='Consumo interno', check_company=True,
        domain="[('usage', '=', 'inventory'), ('company_id', 'in', [company_id, False])]",
        help='Adonde salen los requerimientos internos de las áreas. Su cuenta de '
             'valoración es la del gasto.')
    construction_internal_type_id = fields.Many2one(
        'stock.picking.type', string='Tipo de operación de consumo interno',
        check_company=True,
        domain="[('code', '=', 'internal'), ('warehouse_id', '=', id)]")

    def _construction_ensure_internal_consumption(self):
        """Completa, sin pisar lo configurado, la ubicación «Consumo interno»
        y el tipo de operación «Consumo interno» (secuencia CI)."""
        for warehouse in self:
            vals = {}
            location = warehouse.construction_consumption_location_id
            if not location:
                location = self.env['stock.location'].create({
                    'name': _('Consumo interno'),
                    # Pérdida de inventario, como Desecho: el stock baja y el
                    # costo va a la cuenta de valoración de la ubicación.
                    'usage': 'inventory',
                    'location_id': warehouse.view_location_id.id,
                    'company_id': warehouse.company_id.id,
                })
                vals['construction_consumption_location_id'] = location.id
            if not warehouse.construction_internal_type_id:
                vals['construction_internal_type_id'] = self.env['stock.picking.type'].create({
                    'name': _('Consumo interno'),
                    'code': 'internal',
                    'sequence_code': 'CI',
                    'warehouse_id': warehouse.id,
                    'company_id': warehouse.company_id.id,
                    'default_location_src_id': warehouse.lot_stock_id.id,
                    'default_location_dest_id': location.id,
                }).id
            if vals:
                warehouse.write(vals)
