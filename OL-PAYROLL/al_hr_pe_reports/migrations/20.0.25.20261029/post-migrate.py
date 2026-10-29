# -*- coding: utf-8 -*-
"""Odoo 20 retiró res.bank: el dato que este módulo guardaba por banco
(format_bank) pasa al catálogo l10n_pe.bank (al_account_base lo creó a partir
de res_bank, con su id de origen)."""
from odoo.tools import sql


def migrate(cr, version):
    if not sql.column_exists(cr, 'res_bank', 'format_bank'):
        return
    cr.execute("""
        UPDATE l10n_pe_bank pb SET format_bank = b.format_bank
          FROM res_bank b
         WHERE pb.legacy_res_bank_id = b.id AND pb.format_bank IS NULL
    """)
