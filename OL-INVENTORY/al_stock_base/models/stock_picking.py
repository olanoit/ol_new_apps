# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _sanity_check(self):
        # Planchas enteras (paquete 1.11, M111-12): no se entrega fracción.
        for move in self.move_ids.filtered('picked'):
            if not move._construction_whole_controlled():
                continue
            uom = move.product_id.uom_id
            qty = uom.round(move.product_uom._compute_quantity(move.quantity, uom, round=False))
            if uom.compare(qty, int(qty)) != 0:
                raise UserError(self.env._(
                    '%(product)s se entrega en planchas enteras: %(qty)s no es válido.',
                    product=move.product_id.display_name,
                    qty=formatLang(self.env, qty, digits=2)))
        return super()._sanity_check()
