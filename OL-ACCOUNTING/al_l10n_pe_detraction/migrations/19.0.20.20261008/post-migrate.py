# -*- coding: utf-8 -*-
"""Depósitos de detracción registrados antes de esta versión: se enlazan con
su comprobante para que aparezcan en Perú ▸ Detracciones ▸ Depósitos.

El asistente les pone la glosa «Detracción <constancia> - <comprobante>» y
los concilia con la factura, que guarda esa constancia."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    payments = env['account.payment'].with_context(active_test=False).search([
        ('l10n_pe_detraction_move_id', '=', False), ('memo', '=ilike', 'Detracción %')])
    for payment in payments:
        moves = (payment.reconciled_invoice_ids | payment.reconciled_bill_ids).filtered(
            lambda m: m.l10n_pe_detraction_number
            and m.l10n_pe_detraction_number in (payment.memo or ''))
        if moves:
            payment.l10n_pe_detraction_move_id = moves[:1]
