"""Grupo de impuestos para las transferencias gratuitas exoneradas o inafectas.

El plan peruano trae «18% Free Group» para los retiros gravados (IGV sobre el
valor referencial, asumido al gasto) y el «0% Gra» suelto. Este último deja el
ítem en la base y en el total: el cliente debía el valor referencial. El grupo
nuevo suma el «-Base» nativo para que el ítem quede en 0, como el de 18 %.
"""
from odoo import models

from odoo.addons.account.models.chart_template import template

FREE_EXEMPT_TAX_XMLID = 'sale_tax_free_exempt_group'


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pe', 'account.tax')
    def _get_pe_free_account_tax(self):
        return self._parse_csv('pe', 'account.tax', module='al_l10n_pe_edi_free')
