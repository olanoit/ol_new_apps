# -*- coding: utf-8 -*-
from odoo import api, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    @api.constrains('config_ids', 'is_online_payment', 'online_payment_provider_ids')
    def _check_pos_config_online_payment(self):
        """La regla nativa admite un solo método en línea por caja; la de este
        módulo (una pasarela en un solo método) está en la caja."""
        self.filtered('is_online_payment').config_ids._check_online_payment_methods()
