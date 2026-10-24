# -*- coding: utf-8 -*-
"""El jefe de producción pasa a solo consultar el planificador: el XML
enlaza «Plan: consulta», pero la actualización no quita el enlace anterior
a «Ejecución: ejecuta»."""
from odoo import Command, SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    head = env.ref('al_construction_planner_approvals_mrp.group_planner_production_head',
                   raise_if_not_found=False)
    exec_user = env.ref('al_construction_planner.group_planner_user', raise_if_not_found=False)
    if head and exec_user and exec_user in head.implied_ids:
        head.implied_ids = [Command.unlink(exec_user.id)]
