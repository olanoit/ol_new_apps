# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models
from odoo.exceptions import UserError


class ConstructionApprovalRefuseWizard(models.TransientModel):
    _name = 'construction.approval.refuse.wizard'
    _description = 'Rechazar una solicitud de obra'

    approval_id = fields.Many2one('approval.request', string='Solicitud', required=True)
    reason = fields.Text(string='Motivo', required=True)

    def action_refuse(self):
        self.ensure_one()
        request = self.approval_id
        if not request._construction_active_approvers(self.env.user):
            raise UserError(self.env._(
                'No tiene una aprobación pendiente en el tramo actual de %s.', request.name))
        # El motivo es un campo de solo lectura de la solicitud: lo escribe
        # el aprobador del tramo activo, recién comprobado.
        request.sudo().construction_refuse_reason = self.reason
        request.message_post(body=Markup('%s<br/>%s') % (
            self.env._('Rechazada. Motivo:'), self.reason))
        request.action_refuse()
        return {'type': 'ir.actions.act_window_close'}
