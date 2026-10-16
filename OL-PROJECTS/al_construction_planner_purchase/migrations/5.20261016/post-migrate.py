# -*- coding: utf-8 -*-
"""La regla «Exceso sobre el plan» miraba la política general del plan y no
la de materiales: con materiales en «Solo alerta» seguía pidiendo aprobación.
Ahora mira la política aplicada al requerimiento. La regla es noupdate: se
corrige solo si conserva el dominio de fábrica. Los requerimientos ya
excedidos toman la política de materiales de su plan."""
from odoo import SUPERUSER_ID, api

OLD = ("[('construction_exceed_state', '=', 'exceeded'), "
       "('construction_plan_id.exceed_policy', '=', 'approval')]")
NEW = ("[('construction_exceed_state', '=', 'exceeded'), "
       "('construction_exceed_policy', '=', 'approval')]")


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref('al_construction_planner_purchase.tier_material_request_exceed',
                   raise_if_not_found=False)
    if rule and rule.definition_domain == OLD:
        rule.definition_domain = NEW
    requests = env['construction.material.request'].search([
        ('construction_exceed_state', 'in', ('exceeded', 'approved')),
        ('construction_plan_id', '!=', False)])
    for request in requests:
        request.construction_exceed_policy = request._construction_policy()
