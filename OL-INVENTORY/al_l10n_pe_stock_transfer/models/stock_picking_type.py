# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    l10n_pe_edi_default_reason = fields.Selection(
        selection='_l10n_pe_edi_reason_selection', string='Motivo de traslado (guía)',
        help='Motivo del catálogo 20 de SUNAT que se propone en la guía de remisión de este tipo '
             'de operación (p. ej. «05 Consignación» en un tipo de envío en consignación). Vacío: '
             'se propone según la operación (04 entre establecimientos, 06 devolución, 02 compra '
             'en recepciones, 01 venta en salidas).')

    def _l10n_pe_edi_reason_selection(self):
        return self.env['stock.picking']._fields['l10n_pe_edi_reason_for_transfer']._description_selection(self.env)
