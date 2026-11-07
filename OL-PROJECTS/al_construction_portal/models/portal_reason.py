# -*- coding: utf-8 -*-
"""Motivos que elige el residente en el portal (paquete 6, CR-49 y CR-50,
U8): rechazo de un avance, corrección de su cantidad a la baja y rechazo de
un requerimiento. Cada empresa los configura; el comentario es aparte."""
from odoo import fields, models

REASON_KINDS = [
    ('progress_reject', 'Rechazo de un avance'),
    ('progress_correct', 'Corrección de la cantidad de un avance'),
    ('request_reject', 'Rechazo de un requerimiento'),
]


class ConstructionPortalReason(models.Model):
    _name = 'construction.portal.reason'
    _description = 'Motivo del residente en el portal de obra'
    _order = 'kind, sequence, id'
    _check_company_auto = True

    name = fields.Char(string='Motivo', required=True, translate=True)
    kind = fields.Selection(REASON_KINDS, string='Para', required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string='Compañía', index=True,
                                 help='Vacío: para todas las compañías.')
    active = fields.Boolean(default=True)

    def _portal_list(self, company):
        """{kind: [[id, nombre], …]} de la compañía, para el celular."""
        reasons = self.sudo().search([('company_id', 'in', (company.id, False))])
        result = {kind: [] for kind, _label in REASON_KINDS}
        for reason in reasons:
            result[reason.kind].append([reason.id, reason.name])
        return result
