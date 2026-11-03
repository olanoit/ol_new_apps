# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    l10n_pe_consumption_account_id = fields.Many2one(
        'account.account', string='Cuenta de consumo', company_dependent=True,
        ondelete='restrict', check_company=True,
        help='Cuenta del cargo cuando un producto de esta categoría sale a una ubicación de '
             'consumo (por ejemplo 6131 materiales auxiliares, 6133 repuestos). Vacía: la cuenta '
             'de valorización de la ubicación.')
