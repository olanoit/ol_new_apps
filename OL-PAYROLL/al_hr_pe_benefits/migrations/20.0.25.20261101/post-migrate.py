# -*- coding: utf-8 -*-
"""Tipos de día de los beneficios (laborados, faltas y descanso médico) que
quedaron vacíos en las compañías existentes: reciben los valores por defecto
de las compañías nuevas (``_l10n_pe_set_benefit_wd_defaults``). Lo ya
configurado no se toca."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    params = env['hr.main.parameter'].search([])
    if params:
        params._l10n_pe_set_benefit_wd_defaults()
