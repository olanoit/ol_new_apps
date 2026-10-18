# -*- coding: utf-8 -*-
"""Las reglas de aprobación de ejemplo ya no llevan el prefijo «[DEMO]». Las
de este módulo se reescriben al actualizar; las bases que instalaron la demo
cuando estaba en al_construction_planner conservan esas copias con su xmlid."""
from odoo import SUPERUSER_ID, api

PREFIX = '[DEMO] '
XMLIDS = [
    '%s.%s' % (module, name)
    for module in ('al_construction_planner', 'al_construction_planner_suite')
    for name in ('demo_tier_plan_manager', 'demo_tier_plan_operations')
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in XMLIDS:
        tier = env.ref(xmlid, raise_if_not_found=False)
        if tier and tier.name.startswith(PREFIX):
            tier.name = tier.name[len(PREFIX):]
