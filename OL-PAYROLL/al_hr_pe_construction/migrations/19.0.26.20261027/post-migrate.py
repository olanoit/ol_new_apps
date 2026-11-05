# -*- coding: utf-8 -*-
"""La búsqueda de la tabla salarial pasa de mensual a diaria (la acción decide si
toca) y la tabla 2026 cargada con el módulo registra su fuente.

La acción es noupdate: la actualización no le cambia el intervalo. Si el usuario
la desactivó, sigue desactivada.
"""
from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref('al_hr_pe_construction.ir_cron_construction_wage_tables',
                   raise_if_not_found=False)
    if cron:
        # Sin nextcall, la primera corrida diaria esperaría a la fecha mensual.
        cron.write({'interval_number': 1, 'interval_type': 'days',
                    'nextcall': fields.Datetime.now()})
    table = env.ref('al_hr_pe_construction.wage_table_2026', raise_if_not_found=False)
    if table and not table.source_url:
        table.source_url = ('https://www.capeco.org/descargas/CC2026/'
                            'CAPECO_FTCCP_Remuneraciones%202026_%20FV.pdf')
