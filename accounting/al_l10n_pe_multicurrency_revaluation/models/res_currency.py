# -*- coding: utf-8 -*-
from odoo import models


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def _l10n_pe_revaluation_rates(self, company, date, rate_type):
        """Tipo de cambio SUNAT (soles por unidad) de cada moneda a ``date``.

        Elige el registro de tasa igual que ``_get_rates``: primero los de la
        compañía raíz y después los globales, el más reciente de cada grupo.
        Devuelve ``{currency_id: valor}`` y omite las monedas sin compra o
        venta registrada, que se quedan con el tipo de cambio genérico.
        """
        field = 'rate_purchase' if rate_type == 'purchase' else 'rate_sale'
        Rate = self.env['res.currency.rate']
        values = {}
        for currency in self:
            rate = Rate.search([
                ('currency_id', '=', currency.id),
                ('company_id', 'in', (False, company.root_id.id)),
                ('name', '<=', date),
            ], order='company_id.id, name DESC', limit=1)
            if rate[field]:
                values[currency.id] = rate[field]
        return values
