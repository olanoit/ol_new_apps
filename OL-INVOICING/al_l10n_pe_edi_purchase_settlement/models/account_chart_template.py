# -*- coding: utf-8 -*-
"""Impuestos de retención, grupos y diario de la liquidación de compra en el
plan peruano.

La liquidación de compra retiene el IGV (se paga con el formulario 1662) y el
impuesto a la renta (PDT 617, tributo 3039). Son impuestos negativos de
compra: la factura de proveedor queda por el importe total neto que recibe el
vendedor y el asiento abona las cuentas de tributos por pagar.

Cuentas por defecto (se cambian en el impuesto): 40189 «Otros impuestos» para
el IGV retenido y 40175 «Impuesto a la renta – Otras retenciones» para la
renta, la cuenta que pide el art. 9 de la R.S. 234-2005/SUNAT.
"""
from odoo import models

from odoo.addons.account.models.chart_template import template

IGV_TAX_XMLID = 'purchase_tax_lce_igv_withholding'
IR_TAX_XMLID = 'purchase_tax_lce_ir_withholding_1_5'
IR_GOLD_TAX_XMLID = 'purchase_tax_lce_ir_withholding_4'
JOURNAL_XMLID = 'purchase_settlement_journal'


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pe', 'account.tax.group')
    def _get_pe_lce_account_tax_group(self):
        return self._parse_csv('pe', 'account.tax.group', module='al_l10n_pe_edi_purchase_settlement')

    @template('pe', 'account.tax')
    def _get_pe_lce_account_tax(self):
        return self._parse_csv('pe', 'account.tax', module='al_l10n_pe_edi_purchase_settlement')

    @template('pe', 'account.journal')
    def _get_pe_lce_account_journal(self):
        return {
            JOURNAL_XMLID: {
                'name': 'Liquidaciones de compra',
                'code': 'LCE',
                'type': 'purchase',
                'l10n_latam_use_documents': True,
                'l10n_pe_lce_journal': True,
                'l10n_pe_lce_serie': 'L001',
                'show_on_dashboard': False,
                'sequence': 20,
            },
        }

    @template('pe', 'res.company')
    def _get_pe_lce_res_company(self):
        return {
            self.env.company.id: {
                'l10n_pe_lce_igv_tax_id': IGV_TAX_XMLID,
                'l10n_pe_lce_ir_tax_id': IR_TAX_XMLID,
                'l10n_pe_lce_ir_gold_tax_id': IR_GOLD_TAX_XMLID,
            },
        }
