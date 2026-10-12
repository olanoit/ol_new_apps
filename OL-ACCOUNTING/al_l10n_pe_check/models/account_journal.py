# -*- coding: utf-8 -*-
from odoo import api, models

from .account_chart_template import ISSUED, METHOD_NAMES


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _default_outbound_payment_methods(self):
        # Cheques propios en los diarios de banco de Perú (el nativo lo hace
        # solo en Argentina).
        res = super()._default_outbound_payment_methods()
        if self.company_id.account_fiscal_country_id.code == 'PE' and self.type == 'bank' \
                and self._is_payment_method_available('own_checks'):
            res |= self.env.ref('l10n_latam_check.account_payment_method_own_checks')
        return res

    @api.depends('type', 'currency_id')
    def _compute_outbound_payment_method_line_ids(self):
        # Los métodos se recrean al crear el diario o cambiar su moneda: el de
        # cheques propios recibe aquí su cuenta.
        super()._compute_outbound_payment_method_line_ids()
        self._l10n_pe_check_set_issued_account()

    def _l10n_pe_check_set_issued_account(self):
        """Cuenta de los cheques girados (1049001) en el método «Cheques propios» de
        los diarios de banco que no la tienen: sin ella el pago no tiene
        asiento y el nativo no deja registrar el cheque."""
        for journal in self.filtered(lambda j: j.type == 'bank'
                                     and j.company_id.account_fiscal_country_id.code == 'PE'):
            own = journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')
            own.filtered(lambda l: l.name == l.payment_method_id.name).name = METHOD_NAMES['own_checks']
            lines = own.filtered(lambda l: not l.payment_account_id)
            account = lines and self.env['account.chart.template'].with_company(
                journal.company_id).ref(ISSUED, raise_if_not_found=False)
            if account:
                lines.payment_account_id = account
