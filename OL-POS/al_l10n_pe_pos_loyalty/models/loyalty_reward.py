# -*- coding: utf-8 -*-
from odoo import models
from odoo.fields import Command

from .product_product import PAYMENT_PROGRAM_TYPES


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    def _create_missing_discount_line_products(self):
        """El canje de una tarjeta de regalo o del monedero es una forma de
        pago: su producto de descuento no lleva los impuestos de venta que Odoo
        pone por defecto (de cada compañía, porque el producto es compartido).
        Se quitan los de las compañías peruanas."""
        missing = self.filtered(lambda reward: not reward.discount_line_product_id)
        super()._create_missing_discount_line_products()
        payment_rewards = missing.filtered(
            lambda reward: reward.program_id.program_type in PAYMENT_PROGRAM_TYPES)
        # sudo: el producto es compartido y lleva impuestos de compañías que el
        # usuario puede no ver.
        for product_sudo in payment_rewards.discount_line_product_id.sudo():
            taxes = product_sudo.taxes_id.filtered(
                lambda tax: 'PE' in (tax.country_code, tax.company_id.country_code))
            if taxes:
                product_sudo.taxes_id = [Command.unlink(tax.id) for tax in taxes]
