# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.constrains('payment_method_ids')
    def _check_online_payment_methods(self):
        """Reemplaza la regla nativa de un solo método en línea por caja: puede
        haber uno por pasarela, pero una pasarela no puede estar en dos, porque
        el pago que llega se asigna al método por su pasarela."""
        for config in self:
            seen = self.env['payment.provider']
            for method in config.payment_method_ids.filtered(lambda m: m.type == 'online'):
                if not method._get_online_payment_providers(config.id, error_if_invalid=True):
                    raise ValidationError(_(
                        'El método %(method)s de la caja %(config)s necesita al menos una pasarela '
                        'publicada que acepte la moneda de la caja.',
                        method=method.name, config=config.name))
                repeated = method.online_payment_provider_ids & seen
                if repeated:
                    raise ValidationError(_(
                        'La pasarela %(provider)s está en dos métodos de pago en línea de la caja '
                        '%(config)s: cada pasarela va en un solo método.',
                        provider=repeated[0].name, config=config.name))
                seen |= method.online_payment_provider_ids

    def _al_online_payment_method_for_provider(self, provider):
        """Método de pago en línea de la caja que cobra con esta pasarela."""
        self.ensure_one()
        return self.payment_method_ids.filtered(
            lambda method: (method.type == 'online') and provider in method.online_payment_provider_ids)[:1]
