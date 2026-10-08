# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # El asistente «Registrar depósito» lo rellena: así los depósitos de
    # detracción se listan en Perú ▸ Detracciones ▸ Depósitos con su factura.
    l10n_pe_detraction_move_id = fields.Many2one(
        'account.move', string='Comprobante con detracción', readonly=True,
        copy=False, index='btree_not_null', check_company=True,
        help='Factura cuya detracción se depositó con este pago.')
