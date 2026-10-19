# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError


class ConstructionApprovalRefuseWizard(models.TransientModel):
    _name = 'construction.approval.refuse.wizard'
    _description = 'Rechazar solicitudes de obra'

    # Varias solicitudes con un solo motivo (paquete 1.10, M110-07).
    approval_ids = fields.Many2many('approval.request', string='Solicitudes', required=True)
    reason = fields.Text(string='Motivo', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Desde la acción de la lista llegan las solicitudes marcadas.
        if 'approval_ids' in fields_list and not res.get('approval_ids') \
                and self.env.context.get('active_model') == 'approval.request':
            res['approval_ids'] = [fields.Command.set(self.env.context.get('active_ids') or [])]
        return res

    def action_refuse(self):
        self.ensure_one()
        requests = self.approval_ids
        mine = requests.filtered(lambda r: r._construction_active_approvers(self.env.user))
        others = requests - mine
        if not mine:
            raise UserError(self.env._(
                'No tiene una aprobación pendiente en el tramo actual de %s.',
                ', '.join(requests.mapped('name'))))
        for request in mine:
            # El motivo es un campo de solo lectura de la solicitud: lo escribe
            # el aprobador del tramo activo, recién comprobado.
            request.sudo().construction_refuse_reason = self.reason
            request.message_post(body=Markup('%s<br/>%s') % (
                self.env._('Rechazada. Motivo:'), self.reason))
            request.action_refuse()
        if not others:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Rechazar'),
                'message': self.env._('Rechazadas: %(done)s. No le toca aprobar: %(others)s.',
                                      done=', '.join(mine.mapped('name')),
                                      others=', '.join(others.mapped('name'))),
                'type': 'warning', 'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
