# -*- coding: utf-8 -*-
"""La reversión del CRE pasa de al_ose_factory_hka a este módulo, común a
todos los operadores: la secuencia nueva del resumen RR continúa la de Factory
HKA para no repetir un correlativo del mismo día (SUNAT lo rechaza)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Sequence = env['ir.sequence']
    old = Sequence.search([('code', '=', 'al_ose_factory_hka.reversal_sequence')], limit=1)
    new = env.ref('al_l10n_pe_retention.reversal_sequence', raise_if_not_found=False)
    if old and new and old.number_next_actual > new.number_next_actual:
        new.number_next_actual = old.number_next_actual
