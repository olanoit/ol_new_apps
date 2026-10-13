# -*- coding: utf-8 -*-
"""Versión 8: la conformidad y la anotación en CAVALI pasan de la factura
cedida (línea de la operación) a la factura. Se guardan las columnas viejas
para copiarlas después de crear las nuevas."""
from odoo.tools.sql import column_exists, rename_column

LEGACY = ('cavali_number', 'cavali_date', 'conformity_state', 'conformity_date')


def migrate(cr, version):
    for column in LEGACY:
        if column_exists(cr, 'l10n_pe_factoring_line', column) \
                and not column_exists(cr, 'l10n_pe_factoring_line', 'legacy_%s' % column):
            rename_column(cr, 'l10n_pe_factoring_line', column, 'legacy_%s' % column)
