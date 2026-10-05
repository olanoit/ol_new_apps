# -*- coding: utf-8 -*-
"""El menú «Gantt» del sitio pasa a ser visible solo para el grupo del Gantt.

El registro del menú es ``noupdate``, y ``website.menu`` además se copia a cada
sitio web al crearse: actualizar el XML no llega a las instalaciones
existentes. Se ajustan aquí todas las copias que no tengan ya grupos (si
alguien los configuró a mano desde el editor, se respetan).
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref('al_project_gantt_base.group_gantt_user', raise_if_not_found=False)
    if not group:
        return
    menus = env['website.menu'].with_context(active_test=False).search([
        ('url', '=', '/gantt'),
        ('group_ids', '=', False),
    ])
    if menus:
        menus.write({'group_ids': [(4, group.id)]})
