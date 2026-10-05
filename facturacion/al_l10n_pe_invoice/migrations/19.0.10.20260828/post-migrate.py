# -*- coding: utf-8 -*-
"""«Es Crédito» pasa a decidirse por la fecha de vencimiento.

El campo es almacenado: cambiar su cálculo no recalcula las facturas ya
existentes, que conservarían CRÉDITO en ventas al contado.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env['account.move'].search([('move_type', '!=', 'entry')])
    env.add_to_compute(moves._fields['is_credit'], moves)
    moves._recompute_recordset(['is_credit'])
