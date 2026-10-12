# -*- coding: utf-8 -*-
"""Diarios y cuentas de cheques en el plan peruano.

El módulo nativo los crea solo para Argentina (con sus códigos de cuenta).
En Perú:

* «Cheques de terceros» (caja): los cheques recibidos en cartera, en la
  cuenta 1033001 (PCGE 103, efectivo en tránsito) hasta que se depositan o
  se endosan.
* «Cheques rechazados» (caja): los devueltos por el banco, en 1689001 (otras
  cuentas por cobrar diversas) hasta que se devuelven al cliente.
* Cheques propios girados, desde los diarios de banco: 1049001 hasta que el
  banco los paga (conciliación con el extracto).
"""
from odoo import Command, models

from odoo.addons.account.models.chart_template import template

# Nombres de los métodos en las líneas de los diarios (los del nativo no
# tienen traducción).
METHOD_NAMES = {
    'own_checks': 'Cheques propios',
    'new_third_party_checks': 'Nuevos cheques de terceros',
    'in_third_party_checks': 'Cheques de terceros existentes',
    'out_third_party_checks': 'Cheques de terceros existentes',
    'return_third_party_checks': 'Devolver cheques de terceros',
}
PORTFOLIO = 'l10n_pe_check_portfolio'
REJECTED = 'l10n_pe_check_rejected'
ISSUED = 'l10n_pe_check_issued'
THIRD_PARTY_JOURNAL = 'l10n_pe_third_party_check'
REJECTED_JOURNAL = 'l10n_pe_rejected_check'


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pe', 'account.account')
    def _get_pe_check_account_account(self):
        return {
            PORTFOLIO: {
                'name': 'Cheques de terceros en cartera', 'code': '1033001',
                'account_type': 'asset_cash',
            },
            REJECTED: {
                'name': 'Cheques de terceros rechazados', 'code': '1689001',
                'account_type': 'asset_current', 'reconcile': True,
            },
            ISSUED: {
                'name': 'Cheques girados en circulación', 'code': '1049001',
                'account_type': 'asset_current', 'reconcile': True,
            },
        }

    @template('pe', 'account.journal')
    def _get_pe_check_account_journal(self):
        def methods(account, codes):
            return [Command.create({
                'name': METHOD_NAMES[code],
                'payment_method_id': self.env.ref('l10n_latam_check.account_payment_method_%s' % code).id,
                'payment_account_id': account,
            }) for code in codes]

        def journal(name, code, account):
            return {
                'name': name, 'code': code, 'type': 'cash', 'default_account_id': account,
                'inbound_payment_method_line_ids': methods(
                    account, ('new_third_party_checks', 'in_third_party_checks')),
                'outbound_payment_method_line_ids': methods(
                    account, ('out_third_party_checks', 'return_third_party_checks')),
            }

        return {
            THIRD_PARTY_JOURNAL: journal('Cheques de terceros', 'CHQT', PORTFOLIO),
            REJECTED_JOURNAL: journal('Cheques rechazados', 'CHQR', REJECTED),
        }

    def _post_load_data(self, template_code, company, template_data):
        super()._post_load_data(template_code, company, template_data)
        if template_code == 'pe':
            # Los diarios de banco nacen con el método «Cheques propios» después de
            # crearse (cálculo de sus métodos): aquí ya tienen la línea.
            company._l10n_pe_check_setup()
