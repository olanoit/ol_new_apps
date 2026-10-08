# -*- coding: utf-8 -*-
"""Una configuración principal de planillas por compañía peruana: Ajustes ▸
Nómina ▸ Perú la edita y ningún flujo la busca en vano."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Param = env['hr.main.parameter']
    for company in env['res.company'].search([('partner_id.country_id.code', '=', 'PE')]):
        Param.get_main_parameter(company)
