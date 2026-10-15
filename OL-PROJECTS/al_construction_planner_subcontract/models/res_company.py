# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_retention_account_id = fields.Many2one(
        'account.account', string='Cuenta de retención de contratas', check_company=True,
        domain="[('account_type', 'in', ('liability_current', 'liability_payable'))]",
        help='Si se indica, la factura de cada liquidación lleva una línea negativa con la '
             'retención a esta cuenta y su total es el neto a pagar. Sin cuenta, la factura '
             'va por el bruto y la retención queda solo en la liquidación.')
    construction_discount_account_id = fields.Many2one(
        'account.account', string='Cuenta del descuento de material a contratas',
        check_company=True,
        help='Material extra descontado a una contrata (v1.6, M16-08): la factura de su '
             'liquidación lleva una línea negativa a esta cuenta. Sin cuenta, no se puede '
             'aprobar una liquidación con descuento.')
