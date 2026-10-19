# -*- coding: utf-8 -*-
from odoo import api, fields, models

PAYMENT_PROGRAM_TYPES = ('gift_card', 'ewallet')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    l10n_pe_pos_is_voucher = fields.Boolean(
        string='Tarjeta de regalo o recarga', compute='_compute_l10n_pe_pos_is_voucher',
        help='Producto con el que se vende una tarjeta de regalo o se recarga el monedero: '
             'no entra en el comprobante.')

    @api.model
    def _l10n_pe_pos_voucher_products(self):
        """Productos que venden tarjetas de regalo o recargan el monedero: los
        que disparan un programa de pago (aunque esté archivado) y los dos de
        Odoo, que el TPV vende aunque no haya programa."""
        # sudo: los programas son configuración compartida que el cajero no
        # siempre puede leer; solo se devuelven productos.
        programs_sudo = self.env['loyalty.program'].sudo().with_context(active_test=False).search(
            [('program_type', 'in', PAYMENT_PROGRAM_TYPES)])
        products = programs_sudo.trigger_product_ids
        for xmlid in ('loyalty.gift_card_product_50', 'loyalty.ewallet_product_50'):
            products |= self.env.ref(xmlid, raise_if_not_found=False) or self.browse()
        return self.browse(products.ids)

    def _compute_l10n_pe_pos_is_voucher(self):
        vouchers = self._l10n_pe_pos_voucher_products()
        for product in self:
            product.l10n_pe_pos_is_voucher = product in vouchers

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['l10n_pe_pos_is_voucher']
