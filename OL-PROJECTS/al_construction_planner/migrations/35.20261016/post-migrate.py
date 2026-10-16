# -*- coding: utf-8 -*-
"""v1.8, M18-01: la función «Avance y metrados» se separa en «Avance» y
«Metrado». Las bases que la tenían activa quedan con las dos (el grupo del
metrado es nuevo y la carga no toca «Usuario interno», que es de base), y el
perfil Construcción por partidas apaga el metrado."""
from odoo import SUPERUSER_ID, Command, api

REF = 'al_construction_planner.'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    internal = env.ref('base.group_user')
    progress = env.ref(REF + 'group_planner_feature_progress')
    measurement = env.ref(REF + 'group_planner_feature_measurement')
    if progress in internal.implied_ids and measurement not in internal.implied_ids:
        internal.implied_ids = [Command.link(measurement.id)]
    construction = env.ref(REF + 'profile_construction', raise_if_not_found=False)
    if construction:
        construction.feature_measurement = False
