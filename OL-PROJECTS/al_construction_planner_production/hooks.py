# -*- coding: utf-8 -*-
from odoo import Command


def post_init_hook(env):
    """Ruta de partida de los accesorios: Oficina Técnica, con el jefe de
    proyectos como seguidor (se ajusta en la tabla de rutas)."""
    Route = env['construction.approval.route']
    technical = env.ref('al_construction_planner_approvals.group_planner_technical_office')
    for company in env['res.company'].search([]):
        if Route.with_context(active_test=False).search_count([
                ('company_id', '=', company.id), ('document_type', '=', 'accessories')]):
            continue
        Route.create({
            'name': 'Accesorios de armado: oficina técnica',
            'company_id': company.id,
            'category_id': env['approval.category']._construction_category(company).id,
            'document_type': 'accessories',
            'change_type': 'all',
            'notify_project_manager': True,
            'approver_ids': [Command.create({'group_id': technical.id})],
        })
