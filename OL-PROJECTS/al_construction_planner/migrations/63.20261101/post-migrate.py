# -*- coding: utf-8 -*-
"""Paquete 1.15, M115-04: la etapa actual de los ambientes que ya tienen
etapas se calcula al actualizar (después se mueve con el avance)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    stages = env['construction.space.stage'].search([])
    stages.space_task_id._construction_refresh_current_stage()
