# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_pe_detraction_type_id = fields.Many2one(
        'l10n_pe.detraction.type', string='Tipo de detracción',
        help='Al elegirlo se completan el código del catálogo 54 y el '
             'porcentaje que usa el XML del comprobante.')

    def _l10n_pe_detraction_type(self):
        """Tipo de detracción del producto: el elegido o, si solo tiene el
        código del catálogo 54 de l10n_pe_edi (configurado antes de este
        módulo o importado), el del catálogo con ese código."""
        self.ensure_one()
        if self.l10n_pe_detraction_type_id or not self.l10n_pe_withhold_code:
            return self.l10n_pe_detraction_type_id
        return self.env['l10n_pe.detraction.type'].search(
            [('code', '=', self.l10n_pe_withhold_code)], limit=1)

    @api.onchange('l10n_pe_detraction_type_id')
    def _onchange_l10n_pe_detraction_type_id(self):
        for product in self:
            dtype = product.l10n_pe_detraction_type_id
            product.l10n_pe_withhold_code = dtype.code or False
            product.l10n_pe_withhold_percentage = dtype.percentage or 0.0

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        products._l10n_pe_sync_detraction()
        return products

    def write(self, vals):
        res = super().write(vals)
        if 'l10n_pe_detraction_type_id' in vals:
            self._l10n_pe_sync_detraction()
        return res

    def _l10n_pe_sync_detraction(self):
        """Mantiene alineados los campos nativos con el catálogo."""
        outdated = self.filtered(
            lambda p: p.l10n_pe_detraction_type_id and (
                p.l10n_pe_withhold_code != p.l10n_pe_detraction_type_id.code
                or p.l10n_pe_withhold_percentage
                != p.l10n_pe_detraction_type_id.percentage))
        for dtype, products in outdated.grouped(
                'l10n_pe_detraction_type_id').items():
            products.write({
                'l10n_pe_withhold_code': dtype.code,
                'l10n_pe_withhold_percentage': dtype.percentage,
            })
