# -*- coding: utf-8 -*-
"""CR-15: las líneas con una decisión del validador tomada antes de esta
versión guardan el avance de hoy como el de la decisión, para que avisen si
cambia al actualizar."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Line = env['construction.contract.settlement.line']
    lines = Line.search([('settlement_id.state', 'in', ('draft', 'submitted'))]).filtered(
        lambda l: l._construction_has_decision())
    for line in lines:
        line.write({'decision_qty': line.qty_period, 'decision_date': line.write_date})
