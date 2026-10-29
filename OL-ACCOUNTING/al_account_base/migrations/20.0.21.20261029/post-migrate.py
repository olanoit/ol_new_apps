# -*- coding: utf-8 -*-
"""Odoo 20 retiró res.bank: cada banco usado en una cuenta pasa al catálogo
l10n_pe.bank (guardando su id de origen) y la cuenta queda enlazada a él.
Los módulos que guardaban datos por banco los traducen con
``legacy_res_bank_id``."""
from odoo.tools import sql


def migrate(cr, version):
    if not (sql.table_exists(cr, 'res_bank') and sql.column_exists(cr, 'res_partner_bank', 'bank_id')):
        return
    cr.execute("""
        INSERT INTO l10n_pe_bank (name, bic, sequence, active, legacy_res_bank_id,
                                  create_uid, write_uid, create_date, write_date)
        SELECT COALESCE(b.name, 'Banco ' || b.id), b.bic, 10, true, b.id, 1, 1, now(), now()
          FROM res_bank b
         WHERE NOT EXISTS (SELECT 1 FROM l10n_pe_bank pb WHERE pb.legacy_res_bank_id = b.id)
    """)
    cr.execute("""
        UPDATE res_partner_bank a
           SET l10n_pe_bank_id = pb.id
          FROM l10n_pe_bank pb
         WHERE pb.legacy_res_bank_id = a.bank_id AND a.l10n_pe_bank_id IS NULL
    """)

    # Modelos propios de la suite con un Many2one a res.bank: pasan a
    # l10n_pe.bank. Se suelta la clave foránea a res_bank; el módulo dueño la
    # vuelve a crear hacia l10n_pe_bank al actualizarse.
    for table in ('l10n_pe_check_layout', 'l10n_pe_bank_collection_layout',
                  'l10n_pe_treasury_position_line', 'l10n_pe_letter', 'l10n_pe_letter_line'):
        if not sql.column_exists(cr, table, 'bank_id'):
            continue
        cr.execute("""
            SELECT conname FROM pg_constraint
             WHERE conrelid = %s::regclass AND contype = 'f'
               AND confrelid = 'res_bank'::regclass
        """, [table])
        for (name,) in cr.fetchall():
            cr.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{name}"')
        cr.execute(f"""
            UPDATE {table} t SET bank_id = pb.id
              FROM l10n_pe_bank pb WHERE pb.legacy_res_bank_id = t.bank_id
        """)
