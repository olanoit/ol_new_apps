# -*- coding: utf-8 -*-
from odoo import fields, models

BATCH_FORMATS = [
    ('bcp', 'BCP (Telecrédito)'),
    ('bbva', 'BBVA (net cash)'),
    ('interbank', 'Interbank'),
    ('scotiabank', 'Scotiabank'),
    ('bn', 'Banco de la Nación'),
]


class ResBank(models.Model):
    _inherit = 'res.bank'

    l10n_pe_batch_format = fields.Selection(
        BATCH_FORMATS, string='Formato de pago masivo',
        help='Archivo TXT de pago a proveedores que genera un lote de pagos cuyo diario '
             'es una cuenta de este banco.')
