# -*- coding: utf-8 -*-
"""Odoo 20 retiró res.bank: el dato que este módulo guardaba por banco
(l10n_pe_batch_format) pasa al catálogo l10n_pe.bank (al_account_base lo creó a partir
de res_bank, con su id de origen)."""
from odoo.tools import sql


def migrate(cr, version):
    if not sql.column_exists(cr, 'res_bank', 'l10n_pe_batch_format'):
        return
    cr.execute("""
        UPDATE l10n_pe_bank pb SET l10n_pe_batch_format = b.l10n_pe_batch_format
          FROM res_bank b
         WHERE pb.legacy_res_bank_id = b.id AND pb.l10n_pe_batch_format IS NULL
    """)
