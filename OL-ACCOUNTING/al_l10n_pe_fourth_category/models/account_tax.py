# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_pe_fourth_category = fields.Boolean(
        string='Retención de 4.ª categoría', copy=False,
        help='Impuesto que este módulo pone y quita solo en los recibos por honorarios '
             'según el tope, la suspensión del proveedor y si la compañía es agente de '
             'retención.')
