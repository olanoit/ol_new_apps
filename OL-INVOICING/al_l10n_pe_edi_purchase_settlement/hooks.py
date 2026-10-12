# -*- coding: utf-8 -*-
"""Alta de los impuestos de retención y del diario de liquidaciones de compra
en las compañías que ya tienen el plan peruano (las nuevas los reciben con la
plantilla)."""
import logging

from .models.account_chart_template import (
    IGV_TAX_XMLID, IR_GOLD_TAX_XMLID, IR_TAX_XMLID)

_logger = logging.getLogger(__name__)


def _l10n_pe_lce_load_template(env):
    companies = env['res.company'].search([('chart_template', '=', 'pe'), ('parent_id', '=', False)])
    for company in companies:
        ChartTemplate = env['account.chart.template'].with_company(company)
        data = {
            'account.tax.group': ChartTemplate._get_pe_lce_account_tax_group(),
            'account.tax': ChartTemplate._get_pe_lce_account_tax(),
            'account.journal': ChartTemplate._get_pe_lce_account_journal(),
        }
        # Lo que ya existe (reinstalación) no se vuelve a crear.
        for model in ('account.tax.group', 'account.tax'):
            for xmlid in list(data[model]):
                if ChartTemplate.ref(xmlid, raise_if_not_found=False):
                    del data[model][xmlid]
        ChartTemplate._deref_account_tags('pe', data['account.tax'])
        ChartTemplate._pre_reload_data(company, {}, data)
        ChartTemplate._load_data(data)
        company.write({
            'l10n_pe_lce_igv_tax_id': ChartTemplate.ref(IGV_TAX_XMLID).id,
            'l10n_pe_lce_ir_tax_id': ChartTemplate.ref(IR_TAX_XMLID).id,
            'l10n_pe_lce_ir_gold_tax_id': ChartTemplate.ref(IR_GOLD_TAX_XMLID).id,
        })
        _logger.info('al_l10n_pe_edi_purchase_settlement: impuestos y diario creados en %s',
                     company.name)


def post_init_hook(env):
    _l10n_pe_lce_load_template(env)
