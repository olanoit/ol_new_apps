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

    def _is_write_forbidden(self, fields):
        """La imagen no cambia cómo se cobra ni se contabiliza: se puede poner
        con cajas abiertas (lo necesita la migración que pone los logos)."""
        return super()._is_write_forbidden(fields - {'image'})

    def _al_set_provider_logo(self, force=False):
        """Un método en línea sin imagen lleva el logo de su pasarela: en la
        pantalla de pago del TPV el cajero reconoce Niubiz, Culqi o Izipay."""
        for method in self.filtered(lambda m: (m.type == 'online') and (force or not m.image)):
            for provider in method.online_payment_provider_ids:
                logo = provider._al_pos_payment_logo()
                if logo:
                    method.image = logo
                    break

    @api.constrains('config_ids', 'type', 'online_payment_provider_ids')
    def _check_pos_config_online_payment(self):
        """La regla nativa admite un solo método en línea por caja; la de este
        módulo (una pasarela en un solo método) está en la caja."""
        self.filtered(lambda m: m.type == 'online').config_ids._check_online_payment_methods()
