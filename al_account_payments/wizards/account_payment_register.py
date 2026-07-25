# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    pe_payment_method_id = fields.Many2one(
        comodel_name='pe.catalog.payment', string='Medio pago')
    bank_operation_number = fields.Char(string='Número de operación banco')

    def _create_payment_vals_from_wizard(self, batch_result):
        # Traslada el medio de pago y el nro. de operación al pago creado.
        vals = super()._create_payment_vals_from_wizard(batch_result)
        vals['bank_operation_number'] = self.bank_operation_number
        if self.pe_payment_method_id:
            vals['pe_payment_method_id'] = self.pe_payment_method_id.id
        return vals

    def _create_payment_vals_from_batch(self, batch_result):
        # Idem para pagos creados por lote (sin edición en el asistente).
        vals = super()._create_payment_vals_from_batch(batch_result)
        vals['bank_operation_number'] = self.bank_operation_number
        if self.pe_payment_method_id:
            vals['pe_payment_method_id'] = self.pe_payment_method_id.id
        return vals
