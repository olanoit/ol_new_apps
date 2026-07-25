# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_print_guia_remision(self):
        return self.env.ref(
            'al_l10n_pe_delivery_guide_report.action_report_guia_remision'
        ).report_action(self)

    def _get_grouped_move_lines(self):
        """Agrupa los ``move_ids`` por producto/UdM para el detalle de
        bienes de la guía, con las series/lotes movidos de cada uno."""
        self.ensure_one()
        grouped_data = defaultdict(lambda: {
            'product': None, 'uom': None, 'quantity': 0, 'lots': set()})

        for move in self.move_ids.filtered(lambda m: m.quantity > 0):
            key = (move.product_id.id, move.product_uom.id)
            grouped_data[key]['product'] = move.product_id
            grouped_data[key]['uom'] = move.product_uom
            grouped_data[key]['quantity'] += move.quantity
            for move_line in move.move_line_ids:
                if move_line.lot_id:
                    grouped_data[key]['lots'].add(move_line.lot_id.name)

        return list(grouped_data.values())

    @api.depends('move_ids.weight', 'shipping_weight')
    def _cal_weight(self):
        # EXTENDS stock_delivery: si la suma de pesos de línea es 0 (p. ej.
        # productos sin peso configurado), usa el peso de envío estimado
        # en vez de reportar 0 KGM en la guía.
        super()._cal_weight()
        for picking in self:
            if not picking.weight:
                picking.weight = picking.shipping_weight

    def _l10n_pe_edi_get_delivery_guide_values(self):
        # EXTENDS l10n_pe_edi_stock: fuerza el recálculo del peso antes de
        # armar el XML, para no depender del orden de escritura de los
        # movimientos relacionados.
        self._cal_weight()
        return super()._l10n_pe_edi_get_delivery_guide_values()
