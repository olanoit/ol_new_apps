# -*- coding: utf-8 -*-
"""v1.8, M18-10: el grupo «Planificación de obra: ve montos» es nuevo. Para
que nadie pierda lo que ya veía, lo reciben los usuarios internos que hoy
tienen el planificador (nivel Usuario o superior); la jefatura retira el grupo
a quien no deba ver montos (por ejemplo, los supervisores)."""
from odoo import SUPERUSER_ID, Command, api

REF = 'al_construction_planner.'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    amounts = env.ref(REF + 'group_planner_amounts')
    users = env.ref(REF + 'group_planner_user').all_user_ids.filtered(
        lambda user: not user.share)
    missing = users - amounts.all_user_ids
    if missing:
        amounts.user_ids = [Command.link(user.id) for user in missing]
