# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _name = 'stock.location'
    _inherit = ['stock.location', 'analytic.mixin']

    l10n_pe_is_consumption = fields.Boolean(
        string='Ubicación de consumo',
        help='Las salidas a esta ubicación son consumo interno: el cargo va a la cuenta de consumo '
             'de la categoría del producto o, si no tiene, a la cuenta de esta ubicación, y lleva '
             'centro de costo.')

    @api.constrains('l10n_pe_is_consumption', 'usage', 'valuation_account_id')
    def _check_l10n_pe_consumption(self):
        for location in self.filtered('l10n_pe_is_consumption'):
            if location.usage != 'inventory':
                raise ValidationError(self.env._(
                    'La ubicación de consumo %(location)s debe ser de tipo «Ajuste de inventario».',
                    location=location.display_name))
            if not location.valuation_account_id:
                raise ValidationError(self.env._(
                    'La ubicación de consumo %(location)s necesita su cuenta de valorización.',
                    location=location.display_name))
