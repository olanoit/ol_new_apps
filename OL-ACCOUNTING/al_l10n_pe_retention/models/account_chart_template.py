# -*- coding: utf-8 -*-
"""Impuesto de retención del IGV y secuencia del CRE en el plan peruano.

Mismos xmlids que el módulo oficial de Odoo ``l10n_pe_edi_withholding``
(Enterprise 19.4/20): ``purchase_tax_withholding_3`` y
``l10n_pe_edi_withholding_sunat_sequence``. Al migrar a esa versión, la carga
del plan encuentra estos registros y no los duplica. Los campos son los del
marco nativo de 19.0 (``is_withholding_tax_on_payment``; en 20 se llama
``is_withholding_tax``).
"""
from odoo import models

from odoo.addons.account.models.chart_template import template

TAX_XMLID = 'purchase_tax_withholding_3'
SEQUENCE_XMLID = 'l10n_pe_edi_withholding_sunat_sequence'


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pe', 'account.tax')
    def _get_pe_retention_account_tax(self):
        return self._parse_csv('pe', 'account.tax', module='al_l10n_pe_retention')

    @template('pe', 'ir.sequence')
    def _get_pe_retention_ir_sequence(self):
        return {
            SEQUENCE_XMLID: {
                'name': 'Comprobante de retención (SUNAT)',
                # Serie del CRE: empieza por R y tiene 4 caracteres.
                'prefix': 'R001-',
                'padding': 8,
                'number_next': 1,
            },
        }

    @template('pe', 'res.company')
    def _get_pe_retention_res_company(self):
        return {
            self.env.company.id: {
                'l10n_pe_retention_tax_id': TAX_XMLID,
            },
        }
