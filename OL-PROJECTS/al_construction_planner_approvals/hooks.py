# -*- coding: utf-8 -*-
from odoo import Command


def post_init_hook(env):
    """Tipo de aprobación de obra y rutas de partida por compañía (la tabla
    se ajusta luego en Configuración)."""
    Route = env['construction.approval.route']
    project_head = env.ref('al_construction_planner.group_planner_project_head')
    technical = env.ref('al_construction_planner_approvals.group_planner_technical_office')
    for company in env['res.company'].search([]):
        category = env['approval.category']._construction_category(company)
        if Route.with_context(active_test=False).search_count([('company_id', '=', company.id)]):
            continue
        base = {'company_id': company.id, 'category_id': category.id, 'threshold': 0.0,
                'approval_rule': 'any'}
        Route.create([
            dict(base, name='Plan de recursos: jefatura de proyectos', document_type='plan',
                 change_type='all', basis='amount',
                 approver_ids=[Command.create({'group_id': project_head.id})]),
            dict(base, name='Cambio de material: oficina técnica',
                 document_type='material_request', change_type='material',
                 approver_ids=[Command.create({'group_id': technical.id})]),
            dict(base, name='Cambio de cantidad: oficina técnica o jefatura de proyectos',
                 document_type='material_request', change_type='quantity',
                 approver_ids=[Command.create({'group_id': technical.id}),
                               Command.create({'group_id': project_head.id})]),
        ])
