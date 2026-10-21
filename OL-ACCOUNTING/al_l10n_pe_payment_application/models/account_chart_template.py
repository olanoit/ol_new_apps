"""Diario de aplicaciones y cuentas de anticipos por defecto del plan peruano.

El plan trae la 122 «Anticipos de clientes» (por cobrar) y la 422 «Anticipos a
proveedores» (por pagar), ambas conciliables: un anticipo es un pago normal
con otra cuenta destino.
"""
from odoo import models

from odoo.addons.account.models.chart_template import template

JOURNAL_XMLID = 'l10n_pe_application_journal'
CUSTOMER_ADVANCE_XMLID = 'chart122'
SUPPLIER_ADVANCE_XMLID = 'chart422'


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pe', 'account.journal')
    def _get_pe_application_account_journal(self):
        return {
            JOURNAL_XMLID: {
                'name': 'Aplicación de documentos',
                'code': 'APLI',
                'type': 'general',
                'show_on_dashboard': False,
                'sequence': 30,
            },
        }

    @template('pe', 'res.company')
    def _get_pe_application_res_company(self):
        return {
            self.env.company.id: {
                'l10n_pe_application_journal_id': JOURNAL_XMLID,
                'l10n_pe_advance_customer_account_id': CUSTOMER_ADVANCE_XMLID,
                'l10n_pe_advance_supplier_account_id': SUPPLIER_ADVANCE_XMLID,
            },
        }
