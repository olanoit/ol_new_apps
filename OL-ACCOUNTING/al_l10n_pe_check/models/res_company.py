# -*- coding: utf-8 -*-
import logging

from odoo import Command, models

from .account_chart_template import (
    ISSUED, METHOD_NAMES, REJECTED, REJECTED_JOURNAL, THIRD_PARTY_JOURNAL,
)

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _l10n_pe_check_setup(self):
        """Carga las cuentas y los diarios de cheques de la plantilla y el
        método «Cheques propios» en los diarios de banco, en compañías con el plan
        peruano (el que llama lo comprueba: durante la carga del plan la
        compañía aún no lo tiene marcado). Idempotente: no duplica lo que ya
        existe."""
        own_checks = self.env.ref('l10n_latam_check.account_payment_method_own_checks')
        for company in self:
            ChartTemplate = self.env['account.chart.template'].with_company(company)
            if not ChartTemplate.ref(THIRD_PARTY_JOURNAL, raise_if_not_found=False):
                data = {
                    'account.account': ChartTemplate._get_pe_check_account_account(),
                    'account.journal': ChartTemplate._get_pe_check_account_journal(),
                }
                ChartTemplate._pre_reload_data(company, {}, data)
                ChartTemplate._load_data(data)
                _logger.info('al_l10n_pe_check: diarios de cheques creados en %s', company.name)
            # La recarga de la plantilla no fija «Permitir conciliación» (para
            # no tocar cuentas ya usadas): las de cheques lo necesitan.
            for xmlid in (REJECTED, ISSUED):
                account = ChartTemplate.ref(xmlid, raise_if_not_found=False)
                if account and not account.reconcile:
                    account.reconcile = True
            Journal = self.env['account.journal'].with_company(company)
            banks = Journal.search([*Journal._check_company_domain(company), ('type', '=', 'bank')])
            for journal in banks.filtered(
                    lambda j: own_checks not in j.outbound_payment_method_line_ids.payment_method_id):
                journal.outbound_payment_method_line_ids = [Command.create({
                    'name': METHOD_NAMES['own_checks'], 'payment_method_id': own_checks.id})]
            banks._l10n_pe_check_set_issued_account()
            # Nombre en español en las líneas que conservan el del nativo.
            journals = banks | ChartTemplate.ref(THIRD_PARTY_JOURNAL, raise_if_not_found=False) \
                | ChartTemplate.ref(REJECTED_JOURNAL, raise_if_not_found=False)
            for line in (journals.inbound_payment_method_line_ids | journals.outbound_payment_method_line_ids):
                native = line.payment_method_id.with_context(lang='en_US').name
                if line.code in METHOD_NAMES and line.with_context(lang='en_US').name == native:
                    line.name = METHOD_NAMES[line.code]
