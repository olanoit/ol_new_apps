# -*- coding: utf-8 -*-
from odoo import fields, models

# Cuentas que van a «Resultados por función» en la hoja de trabajo: costo de
# ventas, ingresos, impuesto a la renta y las cuentas analíticas (clase 9).
# Las cuentas de la clase 6 que no tienen destino se añaden aquí.
L10N_PE_WS_FUNCTION_PREFIXES = '69,70,71,72,73,74,75,76,77,78,88,9'


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_ws_function_prefixes = fields.Char(
        string='Cuentas por función (hoja de trabajo)',
        default=L10N_PE_WS_FUNCTION_PREFIXES,
        help='Prefijos de las cuentas de resultados que van a la columna '
             '«Resultados por función» de la hoja de trabajo, separados por '
             'comas. Añada las cuentas de la clase 6 sin destino (por ejemplo '
             '66 o 67) para que el resultado por función cuadre con el de '
             'naturaleza.')

    def _get_company_root_delegated_field_names(self):
        # Depende del plan de cuentas, que es del RUC.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_ws_function_prefixes',
        ]
