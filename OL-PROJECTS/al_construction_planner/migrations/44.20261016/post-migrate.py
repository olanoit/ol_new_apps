# -*- coding: utf-8 -*-
"""CREVAL v1.0, capítulo 5 (segunda pasada): los menús, acciones y reglas que
en la base citaban al Planificador anterior o a la jefatura (versiones viejas o
hechos a mano) reciben los grupos nuevos, y las entradas a la ejecución quedan
activas como en una instalación nueva. Repite sin riesgo la de la 43."""
from odoo import SUPERUSER_ID, api

from odoo.addons.al_construction_planner.models.common import migrate_axis_groups


def migrate(cr, version):
    migrate_axis_groups(api.Environment(cr, SUPERUSER_ID, {}))
