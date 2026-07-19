# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    # Etiquetas en español del marco nativo de retenciones
    is_withholding_tax_on_payment = fields.Boolean(
        string='Retención en el pago')
    withholding_sequence_id = fields.Many2one(
        string='Secuencia del comprobante de retención')
