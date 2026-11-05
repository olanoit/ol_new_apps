# -*- coding: utf-8 -*-
from odoo import fields, models

APPROVAL_ENGINES = [
    ('tier', 'Validación por niveles'),
    ('approvals', 'Aplicación Aprobaciones'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Paquete 1.17, M117-13: Aprobaciones puede filtrar los pedidos de oficina.
    construction_internal_approval_category_id = fields.Many2one(
        'approval.category', string='Categoría del requerimiento interno',
        domain="[('company_id', '=', id)]", check_company=True,
        help='Vacía: se crea «Aprobación de requerimiento interno» la primera vez.')

    def _construction_internal_approval_category(self):
        """La categoría del interno; se crea la primera vez."""
        self.ensure_one()
        if self.construction_internal_approval_category_id:
            return self.construction_internal_approval_category_id
        # Quien envía no administra Aprobaciones: la categoría la crea el sistema.
        base_sudo = self.env['approval.category']._construction_category(self).sudo()
        category_sudo = base_sudo.copy({'name': self.env._('Aprobación de requerimiento interno')})
        self.sudo().construction_internal_approval_category_id = category_sudo
        return category_sudo.sudo(False)

    # Se pasa a Aprobaciones en Ajustes, por compañía: instalar el puente no
    # cambia el flujo de quien ya aprueba por niveles.
    construction_approval_engine = fields.Selection(
        APPROVAL_ENGINES, string='Motor de aprobación', required=True, default='tier',
        help='Dónde se aprueban el plan de recursos y el requerimiento de obra. Lo enviado con '
             'el otro motor termina con su flujo.')
