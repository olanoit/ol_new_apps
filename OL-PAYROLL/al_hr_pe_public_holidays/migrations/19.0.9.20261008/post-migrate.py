# -*- coding: utf-8 -*-
"""El cron se carga con noupdate: su nombre en español se fija aquí."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('al_hr_pe_public_holidays.ir_cron_apply_yearly_holidays', raise_if_not_found=False)
    if cron:
        cron.name = 'Feriados de Perú: aplicación anual'
