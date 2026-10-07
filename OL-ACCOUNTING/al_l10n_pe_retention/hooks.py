# -*- coding: utf-8 -*-
"""Alta del impuesto de retención y de la secuencia del CRE en las compañías
que ya tienen el plan peruano (las nuevas los reciben con la plantilla)."""
import logging

from .models.account_chart_template import SEQUENCE_XMLID, TAX_XMLID

_logger = logging.getLogger(__name__)


def _l10n_pe_retention_load_template(env):
    companies = env['res.company'].search([('chart_template', '=', 'pe'), ('parent_id', '=', False)])
    for company in companies:
        ChartTemplate = env['account.chart.template'].with_company(company)
        tax = company.l10n_pe_retention_tax_id
        if tax:
            # Configurado a mano: se le da el xmlid oficial (y a su secuencia)
            # en vez de crear otro impuesto.
            _bind_xmlid(env, company, TAX_XMLID, tax)
            if tax.withholding_sequence_id:
                _bind_xmlid(env, company, SEQUENCE_XMLID, tax.withholding_sequence_id)
            continue
        if ChartTemplate.ref(TAX_XMLID, raise_if_not_found=False):
            continue
        data = {
            'ir.sequence': ChartTemplate._get_pe_retention_ir_sequence(),
            'account.tax': ChartTemplate._parse_csv('pe', 'account.tax', module='al_l10n_pe_retention'),
        }
        ChartTemplate._deref_account_tags('pe', data['account.tax'])
        ChartTemplate._pre_reload_data(company, {}, data)
        ChartTemplate._load_data(data)
        company.l10n_pe_retention_tax_id = ChartTemplate.ref(TAX_XMLID)
        _logger.info('al_l10n_pe_retention: impuesto de retención creado en %s', company.name)


def _bind_xmlid(env, company, name, record):
    full_name = '%s_%s' % (company.id, name)
    if env['ir.model.data'].search_count([('module', '=', 'account'), ('name', '=', full_name)]):
        return
    env['ir.model.data'].create({
        'module': 'account', 'name': full_name, 'model': record._name,
        'res_id': record.id, 'noupdate': True})


def post_init_hook(env):
    _l10n_pe_retention_load_template(env)
