# -*- coding: utf-8 -*-
"""Consumo de productos con valorización periódica.

El cierre de valorización de Odoo lleva a la cuenta de cada ubicación lo que
salió en el periodo, agrupado por ubicación y categoría y sin analítica. Las
ubicaciones de consumo se retiran de ese cálculo y se suman aquí por cuenta y
centro de costo. Como las líneas vuelven por el mismo método, el cierre las
descuenta de la variación de existencias igual que las nativas.
"""
from collections import defaultdict
import json

from odoo import models
from odoo.fields import Domain


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_location_valuation_vals(self, at_date=None, location_domain=False):
        native_domain = Domain.AND([location_domain or [], [('l10n_pe_is_consumption', '=', False)]])
        return (super()._get_location_valuation_vals(at_date, location_domain=native_domain)
                + self._l10n_pe_consumption_valuation_vals(at_date, location_domain))

    def _l10n_pe_consumption_valuation_vals(self, at_date=None, location_domain=False):
        self.ensure_one()
        locations = self.env['stock.location'].search(Domain.AND([
            location_domain or [],
            [('l10n_pe_is_consumption', '=', True), ('company_id', '=', self.id)],
        ]))
        if not locations:
            return []
        domain = Domain([
            ('company_id', '=', self.id),
            ('state', '=', 'done'),
            ('product_id.is_storable', '=', True),
            ('product_id.valuation', '=', 'periodic'),
        ]) & (
            Domain([('is_out', '=', True), ('location_dest_id', 'in', locations.ids)])
            | Domain([('is_in', '=', True), ('location_id', 'in', locations.ids)])
        )
        last_closing_date = self._get_last_closing_date()
        if last_closing_date:
            domain &= Domain([('date', '>', last_closing_date)])
        if at_date:
            domain &= Domain([('date', '<=', at_date)])

        balances = defaultdict(float)
        for move in self.env['stock.move'].search(domain):
            location = move._l10n_pe_consumption_location()
            category = move.product_id.categ_id
            stock_account = category.property_stock_valuation_account_id or self.account_stock_valuation_id
            distribution = move._l10n_pe_consumption_distribution(location)
            key = (move._l10n_pe_consumption_account(location), stock_account,
                   json.dumps(distribution, sort_keys=True) if distribution else '')
            balances[key] += move.value if move.is_out else -move.value

        vals_list = []
        for (account, stock_account, distribution), balance in balances.items():
            balance = self.currency_id.round(balance)
            if self.currency_id.is_zero(balance):
                continue
            lines = self._prepare_inventory_aml_vals(
                account, stock_account, balance,
                self.env._('Cierre: consumo a costo - [%(account)s]', account=account.display_name))
            if distribution:
                for vals in lines:
                    if vals['account_id'] == account.id:
                        vals['analytic_distribution'] = json.loads(distribution)
            vals_list += lines
        return vals_list
