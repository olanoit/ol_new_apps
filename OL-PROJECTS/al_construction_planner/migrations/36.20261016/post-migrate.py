# -*- coding: utf-8 -*-
"""v1.8, M18-03: el panel de recursos agrupa por tipo de recurso en el orden
del catálogo: materiales, contratas, mano de obra propia, equipo, servicios y
producción. Los tipos del módulo pasan a ese orden si siguen con el de
fábrica (un cliente que ya los reordenó no se toca)."""
from odoo import SUPERUSER_ID, api

REF = 'al_construction_planner.resource_type_'
FACTORY = {'material': 10, 'service': 20, 'equipment': 30, 'contract': 40, 'labor': 50,
           'production': 60}
ORDER = {'material': 10, 'contract': 20, 'labor': 30, 'equipment': 40, 'service': 50,
         'production': 60}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    types = {code: env.ref(REF + code, raise_if_not_found=False) for code in FACTORY}
    if all(rtype and rtype.sequence == FACTORY[code] for code, rtype in types.items()):
        for code, rtype in types.items():
            rtype.sequence = ORDER[code]
