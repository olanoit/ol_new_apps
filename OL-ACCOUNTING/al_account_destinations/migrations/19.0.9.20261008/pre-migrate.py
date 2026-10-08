# -*- coding: utf-8 -*-
"""Carga y «Desactivar destinos» pasan a ser por compañía (company_dependent,
jsonb), como el código de la cuenta. El ORM convierte columnas con
``columna::tipo`` y un entero o booleano no pasa a jsonb: se apartan las
columnas antiguas y ``post-migrate`` lleva sus valores a cada compañía raíz.
"""
from odoo.tools import sql

OLD_COLUMNS = ('l10n_pe_load_account_id', 'l10n_pe_no_destiny')


def migrate(cr, version):
    for column in OLD_COLUMNS:
        if sql.column_exists(cr, 'account_account', column) \
                and not sql.column_exists(cr, 'account_account', column + '_v8'):
            sql.rename_column(cr, 'account_account', column, column + '_v8')
