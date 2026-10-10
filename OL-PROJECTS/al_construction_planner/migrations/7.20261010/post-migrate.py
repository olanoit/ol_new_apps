# -*- coding: utf-8 -*-
"""Fase 8: las etapas de cada ambiente (barras del cronograma, P-15) se crean
al generar el plan; para los planes ya generados se crean aquí, desde el plan
vigente (o en preparación) de cada obra."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Stage = env['construction.space.stage']
    for project in env['construction.resource.plan'].search([]).project_id:
        plan = project._construction_current_plan()
        if plan:
            Stage._sync_from_plan(plan)
