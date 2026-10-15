# -*- coding: utf-8 -*-
"""v1.7, M17-06: las funciones control y avance y metrados quedan activas en las
bases que ya usan el planificador (los grupos son nuevos: la carga no toca
el grupo «Usuario interno», que es de base)."""
from odoo import SUPERUSER_ID, Command, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    internal = env.ref('base.group_user')
    internal.implied_ids = [
        Command.link(env.ref('al_construction_planner.group_planner_feature_control').id),
        Command.link(env.ref('al_construction_planner.group_planner_feature_progress').id),
    ]
