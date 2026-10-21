"""Diario de aplicaciones y cuentas de anticipos en las compañías que ya tienen
el plan peruano (las nuevas los reciben con la plantilla)."""
import logging

from .models.account_chart_template import (
    CUSTOMER_ADVANCE_XMLID, JOURNAL_XMLID, SUPPLIER_ADVANCE_XMLID,
)

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    companies = env['res.company'].search([('chart_template', '=', 'pe'), ('parent_id', '=', False)])
    for company in companies:
        ChartTemplate = env['account.chart.template'].with_company(company)
        journal = ChartTemplate.ref(JOURNAL_XMLID, raise_if_not_found=False)
        if not journal:
            data = {'account.journal': ChartTemplate._get_pe_application_account_journal()}
            ChartTemplate._pre_reload_data(company, {}, data)
            ChartTemplate._load_data(data)
            journal = ChartTemplate.ref(JOURNAL_XMLID)
        vals = {}
        if not company.l10n_pe_application_journal_id:
            vals['l10n_pe_application_journal_id'] = journal.id
        if not company.l10n_pe_advance_customer_account_id:
            vals['l10n_pe_advance_customer_account_id'] = ChartTemplate.ref(
                CUSTOMER_ADVANCE_XMLID, raise_if_not_found=False).id
        if not company.l10n_pe_advance_supplier_account_id:
            vals['l10n_pe_advance_supplier_account_id'] = ChartTemplate.ref(
                SUPPLIER_ADVANCE_XMLID, raise_if_not_found=False).id
        company.write(vals)
        _logger.info('al_l10n_pe_payment_application: configurado en %s', company.name)
