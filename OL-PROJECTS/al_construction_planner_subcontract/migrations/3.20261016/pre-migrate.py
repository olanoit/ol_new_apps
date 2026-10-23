# -*- coding: utf-8 -*-
"""CREVAL v1.0, 3.5: la valorización con condiciones es por orden; el índice
único por contrata, obra y semana pasa a incluir la orden."""
from odoo.tools import SQL


def migrate(cr, version):
    cr.execute(SQL('DROP INDEX IF EXISTS %s', SQL.identifier(
        'construction_contract_settlement_period_unique')))
