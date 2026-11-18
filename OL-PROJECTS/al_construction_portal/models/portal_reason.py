# -*- coding: utf-8 -*-
"""Motivos que elige el residente en el portal (paquete 6, CR-49 y CR-50,
U8): rechazo de un avance, corrección de su cantidad a la baja y rechazo de
un requerimiento. Cada empresa los configura; el comentario es aparte.

Desde el paquete 1.22 (M122-03) el catálogo vive en el núcleo, con el uso
«Re-trabajo»; el portal le suma estos tres usos y lo envía al celular."""
from odoo import fields, models

REASON_KINDS = [
    ('progress_reject', 'Rechazo de un avance'),
    ('progress_correct', 'Corrección de la cantidad de un avance'),
    ('request_reject', 'Rechazo de un requerimiento'),
]


class ConstructionPortalReason(models.Model):
    _inherit = 'construction.portal.reason'

    kind = fields.Selection(
        selection_add=REASON_KINDS,
        ondelete={kind: 'cascade' for kind, _label in REASON_KINDS})

    def _portal_list(self, company):
        """{kind: [[id, nombre], …]} de la compañía, para el celular."""
        reasons = self.sudo().search([('company_id', 'in', (company.id, False))])
        result = {kind: [] for kind, _label in REASON_KINDS}
        for reason in reasons:
            result.setdefault(reason.kind, []).append([reason.id, reason.name])
        return result
