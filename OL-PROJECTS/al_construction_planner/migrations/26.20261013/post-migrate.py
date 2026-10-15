# -*- coding: utf-8 -*-
"""v1.6, M16-09: las reglas de validación del planificador las aprueba el
grupo de jefatura de proyectos y no el administrador. Las reglas del módulo
son noupdate: se pasan aquí las que siguen en el administrador (también las
creadas a mano o por los scripts demo sobre los mismos documentos). Quienes
eran administradores entran a la jefatura para que las revisiones pendientes
no se queden sin revisor; se les puede quitar después."""
from odoo import SUPERUSER_ID, Command, api

MODELS = ('construction.resource.plan', 'construction.material.request',
          'construction.contract.settlement', 'construction.measurement')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    manager = env.ref('al_construction_planner.group_planner_manager')
    head = env.ref('al_construction_planner.group_planner_project_head')
    definitions = env['tier.definition'].with_context(active_test=False).search([
        ('model', 'in', MODELS), ('review_type', '=', 'group'),
        ('reviewer_group_id', '=', manager.id)])
    definitions.reviewer_group_id = head
    users = manager.user_ids.filtered(lambda u: u.id != SUPERUSER_ID and not u.share)
    head.user_ids = [Command.link(user.id) for user in users]
