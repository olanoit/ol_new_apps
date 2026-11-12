# -*- coding: utf-8 -*-
"""Paquete 1.20, M120-07: seis funciones más del perfil de vertical.

* Sin configurar, todo se ve como hoy (P4): los grupos nuevos quedan activos
  para los usuarios internos. El registro de «Usuario interno» del módulo es
  noupdate y no los suma solo.
* Los perfiles estándar (también noupdate) reciben los valores de la tabla
  del requerimiento. Los campos son nuevos: no hay nada del cliente que pisar.
  La compañía no cambia hasta que aplica su perfil o mueve Ajustes."""
from odoo import SUPERUSER_ID, Command, api

REF = 'al_construction_planner.'
NEW = ('milestones', 'valuation', 'deductions', 'daily_report', 'recipes', 'installation_board')
OFF = {
    'profile_furniture': ('valuation', 'deductions', 'daily_report', 'recipes'),
    'profile_construction': ('milestones', 'installation_board'),
    'profile_construction_prof4': ('milestones', 'installation_board'),
    'profile_construction_prof5': ('milestones', 'installation_board'),
    'profile_construction_prof6': ('milestones', 'installation_board'),
}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    internal = env.ref('base.group_user')
    groups = [env.ref(REF + 'group_planner_feature_%s' % feature, raise_if_not_found=False)
              for feature in NEW]
    internal.write({'implied_ids': [Command.link(group.id) for group in groups if group]})
    for xmlid, off in OFF.items():
        profile = env.ref(REF + xmlid, raise_if_not_found=False)
        if profile:
            profile.write({'feature_%s' % feature: False for feature in off})
