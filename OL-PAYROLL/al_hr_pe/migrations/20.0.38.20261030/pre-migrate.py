# -*- coding: utf-8 -*-
"""UIT y RMV pasan a parámetros de reglas nativos: se guardan los valores
de los catálogos propios antes de que Odoo borre sus tablas."""


def migrate(cr, version):
    for table in ('l10n_pe_hr_uit', 'l10n_pe_hr_rmv'):
        cr.execute("SELECT to_regclass(%s)", [table])
        if cr.fetchone()[0]:
            cr.execute(f'DROP TABLE IF EXISTS "{table}_bak"')
            cr.execute(f'CREATE TABLE "{table}_bak" AS TABLE "{table}"')
