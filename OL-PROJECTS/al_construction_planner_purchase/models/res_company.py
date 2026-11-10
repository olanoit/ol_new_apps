# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Paquete 1.18, M118-04, punto 4.
    construction_price_review_pct = fields.Float(
        string='Variación que pide revisión (%)', default=10.0,
        help='«Aplicar costo» por grupo deja sin marcar los productos cuyo costo de la base se '
             'aleja del costo de referencia más que este porcentaje.')
    construction_price_alert_pct = fields.Float(
        string='Alerta de precio sobre el plan (%)', default=5.0,
        help='El abastecimiento de la obra marca el producto cuyo último precio de compra '
             'supera el costo del plan en este porcentaje o más.')
    # Paquete 1.16, M116-03 (M114-02): sin plan vigente, cada línea del
    # requerimiento de obra es material fuera del plan y sigue su tramo.
    construction_site_request_without_rule = fields.Selection(
        selection_add=[('out_of_plan', 'Material fuera del plan si la obra no tiene plan')],
        ondelete={'out_of_plan': 'set default'})

    def write(self, vals):
        res = super().write(vals)
        if 'construction_site_request_without_rule' in vals:
            self._construction_sync_no_plan_rule()
        return res

    def _construction_sync_no_plan_rule(self):
        """Regla de validación por niveles «obra sin plan → jefatura del
        planificador», activa solo con «Material fuera del plan» (M116-03).
        Con la aplicación Aprobaciones manda la tabla de rutas."""
        # Configuración técnica, como la regla 7.4: la mantiene la compañía
        # aunque quien guarda los Ajustes no administre las reglas.
        Definition_sudo = self.env['tier.definition'].sudo().with_context(active_test=False)
        model = self.env['ir.model']._get('construction.material.request')
        group = self.env.ref('al_construction_planner.group_planner_exec_approver')
        for company in self:
            rule = Definition_sudo.search([
                ('construction_no_plan', '=', True), ('company_id', '=', company.id)], limit=1)
            if company.construction_site_request_without_rule != 'out_of_plan':
                rule.active = False
                continue
            vals = {
                'name': self.env._('Obra sin plan: material fuera del plan, jefatura del planificador'),
                'model_id': model.id,
                'review_type': 'group',
                'reviewer_group_id': group.id,
                'definition_domain': repr([
                    ('request_type', '=', 'site'),
                    ('construction_exceed_state', '=', 'no_plan'),
                    ('company_id', '=', company.id)]),
                'company_id': company.id,
                'sequence': 6,
                'approve_sequence': True,
                'active': True,
            }
            if rule:
                rule.write(vals)
            else:
                Definition_sudo.create(dict(vals, construction_no_plan=True))
