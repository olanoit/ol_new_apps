# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _sanity_check(self, separate_pickings=True):
        # Planchas enteras (paquete 1.11, M111-12): no se entrega fracción.
        # Se revisan las líneas que se van a entregar, como lo hace Odoo: las
        # marcadas «Recogido» o, si no hay ninguna, todas las que tienen
        # cantidad (M111-13: antes de que Odoo las marque).
        for picking in self:
            moves = picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            if any(moves.mapped('picked')):
                moves = moves.filtered('picked')
            for move in moves.filtered(lambda m: m.quantity):
                if not move._construction_whole_controlled():
                    continue
                uom = move.product_id.uom_id
                qty = uom.round(move.product_uom._compute_quantity(move.quantity, uom, round=False))
                if uom.compare(qty, int(qty)) != 0:
                    raise UserError(self.env._(
                        '%(product)s se entrega en planchas enteras: %(qty)s no es válido.',
                        product=move.product_id.display_name,
                        qty=formatLang(self.env, qty, digits=2)))
        return super()._sanity_check(separate_pickings=separate_pickings)
