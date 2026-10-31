# -*- coding: utf-8 -*-
"""Básico, bruto, neto y coste del empleador de las boletas PE cerradas:
el nativo solo los calcula en borrador, y antes de sumar BAS/TINGR/NETO
quedaron en 0 (tablero, total del lote, reparto bancario)."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    slips = env['hr.payslip'].with_context(active_test=False).search([
        ('state', '!=', 'draft'),
        ('struct_id.country_id.code', '=', 'PE'),
    ])
    for start in range(0, len(slips), 1000):
        slips[start:start + 1000]._l10n_pe_store_wage_totals()
