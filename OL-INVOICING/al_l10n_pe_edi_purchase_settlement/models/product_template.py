# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_pe_lce_gold = fields.Boolean(
        string='Oro (retención de renta del 4 %)',
        help='Minerales de oro y sus concentrados (2616.90.10.00), amalgama (2843.90.00.00), '
             'oro en polvo y en bruto (7108.11.00.00 y 7108.12.00.00) y desperdicios de oro '
             '(7112.91.00.00): en la liquidación de compra se retiene el 4 % del impuesto a '
             'la renta (R.S. 028-2013/SUNAT).')
