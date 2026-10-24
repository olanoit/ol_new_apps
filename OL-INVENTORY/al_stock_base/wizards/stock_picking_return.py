# -*- coding: utf-8 -*-
"""Devolución de transferencias sin la trampa de mrp_subcontracting.

``mrp_subcontracting`` cambia el destino de la devolución por la ubicación de
subcontratista del contacto cuando *todas* las líneas son de subcontratación;
con el asistente sin líneas ``all([])`` es verdadero y el destino queda vacío,
y la copia de la transferencia falla en la base («Falta el valor requerido
para el campo Ubicación de destino») en lugar del aviso de Odoo."""
from odoo import models
from odoo.exceptions import UserError


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _prepare_picking_default_values(self):
        vals = super()._prepare_picking_default_values()
        if self.picking_id and not vals.get('location_dest_id'):
            vals['location_dest_id'] = self._prepare_picking_default_values_based_on(
                self.picking_id)['location_dest_id']
        return vals

    def _create_return(self):
        if not any(not line.uom_id.is_zero(line.quantity) for line in self.product_return_moves):
            raise UserError(self.env._(
                'Indique la cantidad a devolver de al menos un producto.'))
        return super()._create_return()
