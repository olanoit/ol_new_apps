# -*- coding: utf-8 -*-
"""Plan peruano: el impuesto de retención del IGV y la secuencia del CRE son
los del módulo nativo ``l10n_pe_edi_withholding`` (mismos xmlids); aquí solo
se cambia la serie del CRE y se marca el impuesto como el del régimen.
"""
from odoo import models

from odoo.addons.account.models.chart_template import template

TAX_XMLID = 'purchase_tax_withholding_3'
SEQUENCE_XMLID = 'l10n_pe_edi_withholding_sunat_sequence'


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pe', 'ir.sequence')
    def _get_pe_retention_ir_sequence(self):
        # Serie del CRE: empieza por R y tiene 4 caracteres (el nativo usa RRR1-).
        return {SEQUENCE_XMLID: {'name': 'Comprobante de retención (SUNAT)', 'prefix': 'R001-'}}

    @template('pe', 'res.company')
    def _get_pe_retention_res_company(self):
        return {
            self.env.company.id: {
                'l10n_pe_retention_tax_id': TAX_XMLID,
            },
        }
