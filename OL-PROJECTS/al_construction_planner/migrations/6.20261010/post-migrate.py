# -*- coding: utf-8 -*-
"""Fase 7: el estado de la línea y sus montos de control (comprometido, real,
saldo, % ejecutado) pasan a guardarse; se calculan una vez para todas las
líneas existentes."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['construction.resource.plan.line'].search([])._refresh_control()
