# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Tipos de cuenta que el informe de revaluación nunca toma.
NOT_REVALUED_TYPES = (
    'income', 'income_other', 'expense', 'expense_depreciation',
    'expense_direct_cost', 'off_balance',
)


class AccountAccount(models.Model):
    _inherit = 'account.account'

    l10n_pe_revaluation_rate_type = fields.Selection(
        selection=[
            ('purchase', 'Compra'),
            ('sale', 'Venta'),
        ],
        string='T.C. en ganancias/pérdidas no realizadas',
        help='Tipo de cambio SUNAT con el que el informe de ganancias/pérdidas '
             'de moneda no realizadas revalúa esta cuenta. Si no hay tipo de '
             'cambio de compra o venta para la fecha, se usa el genérico del '
             'informe. Solo aplica a compañías peruanas.')
    l10n_pe_revaluation_rate_visible = fields.Boolean(
        compute='_compute_l10n_pe_revaluation_rate_visible',
        help='Técnico: la cuenta puede tener saldos en moneda extranjera que '
             'el informe revalúa y pertenece a una compañía peruana.')

    @api.depends('currency_id', 'account_type', 'company_ids.currency_id',
                 'company_ids.account_fiscal_country_id')
    def _compute_l10n_pe_revaluation_rate_visible(self):
        for account in self:
            # Mismo criterio que el informe: las cuentas por cobrar y por pagar
            # admiten cualquier moneda por apunte aunque no tengan una fija;
            # las demás solo si su moneda es extranjera.
            foreign = (
                account.account_type in ('asset_receivable', 'liability_payable')
                or (account.currency_id
                    and account.currency_id not in account.company_ids.currency_id)
            )
            peruvian = any(company.account_fiscal_country_id.code == 'PE'
                           for company in account.company_ids)
            account.l10n_pe_revaluation_rate_visible = bool(
                foreign and peruvian
                and account.account_type not in NOT_REVALUED_TYPES)
