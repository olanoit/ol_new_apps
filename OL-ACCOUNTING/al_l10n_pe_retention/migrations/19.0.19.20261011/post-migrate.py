# -*- coding: utf-8 -*-
"""Retenciones sufridas con cabecera y líneas: cada registro anterior (una
factura y un monto en la cabecera) pasa a tener su línea, y su número se
separa en serie y número."""
from odoo import SUPERUSER_ID, api
from odoo.tools import SQL


def migrate(cr, version):
    cr.execute(SQL(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        'l10n_pe_retention_received', 'move_id'))
    if not cr.fetchone():
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(SQL(
        "SELECT r.id, r.move_id, r.amount FROM l10n_pe_retention_received r "
        "WHERE r.move_id IS NOT NULL AND NOT EXISTS ("
        "  SELECT 1 FROM l10n_pe_retention_received_line l WHERE l.retention_id = r.id)"))
    rows = cr.fetchall()
    Line = env['l10n_pe.retention.received.line'].with_context(tracking_disable=True)
    Line.create([{'retention_id': rid, 'move_id': move_id, 'amount': amount or 0.0}
                 for rid, move_id, amount in rows])
    received = env['l10n_pe.retention.received'].search([('l10n_pe_series', '=', False)])
    received._inverse_name()
