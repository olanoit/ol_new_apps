# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    pe_payment_method_id = fields.Many2one(
        comodel_name='pe.catalog.payment', string='Medio pago')
    bank_operation_number = fields.Char(string='Número de operación banco')
