# -*- coding: utf-8 -*-
"""Paquete 1.17, M117-15: los parámetros iniciales de cada compañía."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env['res.company'].search([]):
        env['construction.sheet.parameter']._construction_ensure(company)
