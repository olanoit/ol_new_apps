# -*- coding: utf-8 -*-
"""El código SUNAT del banco pasa al clearing_number nativo de la cuenta
(el que lee el PLE de Odoo 20): se copia donde está vacío."""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'res_partner_bank' AND column_name = 'l10n_pe_bank_code'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE res_partner_bank
           SET clearing_number = l10n_pe_bank_code
         WHERE COALESCE(l10n_pe_bank_code, '') != ''
           AND COALESCE(clearing_number, '') = ''
    """)
