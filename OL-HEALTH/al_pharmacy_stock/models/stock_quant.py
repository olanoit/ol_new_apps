# -*- coding: utf-8 -*-
from odoo import models
from odoo.fields import Domain


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _get_gather_domain(self, product_id, location_id, lot_id=None, package_id=None,
                           owner_id=None, strict=False):
        """Las reservas automáticas no toman lotes en cuarentena, bloqueados ni
        vencidos. Elegir el lote a mano (strict, p. ej. para darlo de baja)
        sigue funcionando."""
        domain = super()._get_gather_domain(product_id, location_id, lot_id=lot_id,
                                            package_id=package_id, owner_id=owner_id,
                                            strict=strict)
        if strict or self.env.context.get('pharmacy_any_lot_state'):
            return domain
        return domain & (Domain('lot_id', '=', False)
                         | Domain('lot_id.pharmacy_state', '=', 'available'))
