# -*- coding: utf-8 -*-
"""Residente de la obra como revisor de los requerimientos (paquete 6,
CR-50).

* «Residente de la obra» es un campo del requerimiento: las reglas de
  aprobación lo eligen como revisor por campo (la validación por niveles de
  OCA acepta un usuario de portal). Qué regla queda con el residente y cuál
  con la jefatura se configura en cada empresa.
* La opción «Requerimiento de obra sin regla de aprobación» agrega «Pasar al
  residente de la obra»: sin residente marcado, pasa al jefe de la obra."""
from odoo import api, fields, models


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    construction_site_resident_id = fields.Many2one(
        'res.users', string='Residente de la obra',
        related='project_id.construction_portal_resident_id', store=True, index='btree_not_null',
        help='El residente aprobador por defecto de la obra en el portal (revisor por campo de '
             'las reglas de aprobación).')
    construction_site_reviewer_id = fields.Many2one(
        'res.users', string='Residente o jefe de la obra',
        compute='_compute_construction_site_reviewer_id', store=True,
        help='El residente de la obra; sin residente, el jefe de la obra.')

    def action_request_approval(self):
        res = super().action_request_approval()
        # Paquete 6, CR-57: el pedido urgente que espera aprobación avisa al
        # celular de quien lo aprueba en el portal de la obra.
        service = self.env['construction.portal.service']
        for request in self.filtered(lambda r: r.priority == '1' and r.state == 'to_approve'
                                     and r.project_id):
            service._portal_notice(request, request.project_id, 'urgent_request', self.env._(
                'Pedido urgente %(name)s por aprobar: %(lines)s.', name=request.name,
                lines=', '.join(request.line_ids.product_id.mapped('display_name')[:3]) or '-'))
        return res

    @api.depends('construction_site_resident_id', 'project_manager_id')
    def _compute_construction_site_reviewer_id(self):
        for request in self:
            request.construction_site_reviewer_id = (
                request.construction_site_resident_id or request.project_manager_id)


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_site_request_without_rule = fields.Selection(
        selection_add=[('resident', 'Pasar al residente de la obra (portal)')],
        ondelete={'resident': 'set default'})

    def _construction_site_fallback_field(self):
        if self.construction_site_request_without_rule == 'resident':
            return 'construction_site_reviewer_id'
        return super()._construction_site_fallback_field()

    def _construction_site_fallback_name(self):
        if self.construction_site_request_without_rule == 'resident':
            return self.env._('Requerimiento de obra sin otra regla: residente de la obra')
        return super()._construction_site_fallback_name()
