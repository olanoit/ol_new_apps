# -*- coding: utf-8 -*-
"""Odoo 20 retiró account.group (los grupos son cuentas padre): el grupo de
la configuración de cuentas de letras pasa a ser la cuenta padre de su
cuenta."""
from odoo.tools import sql


def migrate(cr, version):
    table = 'l10n_pe_letter_account_config'
    if not sql.column_exists(cr, table, 'group_id'):
        return
    cr.execute(f"""
        SELECT conname FROM pg_constraint
         WHERE conrelid = '{table}'::regclass AND contype = 'f'
           AND conkey = ARRAY[(SELECT attnum FROM pg_attribute
                                WHERE attrelid = '{table}'::regclass AND attname = 'group_id')]
    """)
    for (name,) in cr.fetchall():
        cr.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{name}"')
    cr.execute(f"""
        UPDATE {table} c SET group_id = a.parent_id
          FROM account_account a WHERE a.id = c.account_id
    """)
