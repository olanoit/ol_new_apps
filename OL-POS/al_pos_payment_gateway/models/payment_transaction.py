# -*- coding: utf-8 -*-
from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _process_pos_online_payment(self):
        """El pago se registra con el método de la caja que tiene la pasarela de
        la transacción (ver pos.order._compute_online_payment_method_id)."""
        for tx in self:
            super(PaymentTransaction, tx.with_context(
                al_pos_online_provider_id=tx.provider_id.id))._process_pos_online_payment()
