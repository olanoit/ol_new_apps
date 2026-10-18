# -*- coding: utf-8 -*-
"""Datos DIGEMID del producto: código del Observatorio y régimen del IGV
(medicamentos oncológicos y para VIH/SIDA, Ley 27450; para diabetes, Ley
28553, según las listas aprobadas por decreto supremo)."""
from odoo import api, fields, models

IGV_REGIMES = [
    ('taxed', 'Gravado'),
    ('oncology_hiv', 'Exonerado: oncológico o VIH/SIDA (Ley 27450)'),
    ('diabetes', 'Exonerado: diabetes (Ley 28553)'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pharmacy_digemid_code = fields.Char(
        string='Código DIGEMID', index='btree_not_null',
        help='Código de producto que asigna DIGEMID para el Observatorio Peruano de Productos '
             'Farmacéuticos.')
    pharmacy_igv_regime = fields.Selection(
        IGV_REGIMES, string='Régimen del IGV', default='taxed',
        help='Los medicamentos de las listas de las leyes 27450 y 28553 se venden exonerados del '
             'IGV: el impuesto de venta pasa al de exonerados.')

    @api.onchange('pharmacy_igv_regime')
    def _onchange_pharmacy_igv_regime(self):
        if self.pharmacy_igv_regime and self.pharmacy_igv_regime != 'taxed':
            tax = self._pharmacy_exonerated_sale_tax()
            if tax:
                self.taxes_id = tax

    def _pharmacy_exonerated_sale_tax(self):
        company = self.company_id or self.env.company
        return self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'), ('l10n_pe_edi_tax_code', '=', '9997'),
            *self.env['account.tax']._check_company_domain(company)], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        templates.filtered(lambda t: t.pharmacy_ok and t.pharmacy_digemid_code) \
            ._pharmacy_observatory_register()
        return templates

    def write(self, vals):
        result = super().write(vals)
        if {'list_price', 'pharmacy_digemid_code'} & set(vals):
            self.filtered(lambda t: t.pharmacy_ok and t.pharmacy_digemid_code) \
                ._pharmacy_observatory_register()
        return result

    def _pharmacy_observatory_register(self):
        self.env['pharmacy.observatory.price']._pharmacy_register_prices(self)
