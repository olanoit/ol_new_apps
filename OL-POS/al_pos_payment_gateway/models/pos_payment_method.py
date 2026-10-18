# -*- coding: utf-8 -*-
from odoo import api, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    @api.model_create_multi
    def create(self, vals_list):
        methods = super().create(vals_list)
        methods._al_set_provider_logo()
        return methods

    def write(self, vals):
        res = super().write(vals)
        if 'online_payment_provider_ids' in vals:
            self._al_set_provider_logo()
        return res

    def _al_set_provider_logo(self):
        """Un método en línea sin imagen lleva el logo de su pasarela: en la
        pantalla de pago del TPV el cajero reconoce Niubiz, Culqi o Izipay."""
        for method in self.filtered(lambda m: m.is_online_payment and not m.image):
            logo = method.online_payment_provider_ids.filtered('image_128')[:1].image_128
            if logo:
                method.image = logo

    @api.constrains('config_ids', 'is_online_payment', 'online_payment_provider_ids')
    def _check_pos_config_online_payment(self):
        """La regla nativa admite un solo método en línea por caja; la de este
        módulo (una pasarela en un solo método) está en la caja."""
        self.filtered('is_online_payment').config_ids._check_online_payment_methods()
