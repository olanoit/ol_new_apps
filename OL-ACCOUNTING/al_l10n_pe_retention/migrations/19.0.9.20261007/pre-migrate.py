# -*- coding: utf-8 -*-
"""Versión 9: el número del comprobante de retención toma el nombre del
campo oficial de Odoo (``l10n_pe_edi_retention_number``)."""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'account_payment' AND column_name = 'l10n_pe_retention_number'
    """)
    if cr.fetchone():
        cr.execute('ALTER TABLE account_payment RENAME COLUMN l10n_pe_retention_number '
                   'TO l10n_pe_edi_retention_number')
        cr.execute("""
            UPDATE ir_model_fields SET name = 'l10n_pe_edi_retention_number'
             WHERE model = 'account.payment' AND name = 'l10n_pe_retention_number'
        """)
