# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError

# Acción del motivo: modelo y método que lo recibe.
REASON_ACTIONS = {
    'reject': ('construction.task.progress', '_action_reject'),
    'return': ('construction.contract.settlement', '_action_return'),
    'observe': ('construction.valuation', '_action_observe'),
}


class ConstructionReasonWizard(models.TransientModel):
    """Motivo obligatorio para rechazar un avance (P-07), devolver una
    liquidación a la contrata (P-08) o registrar la observación del cliente
    a una valorización (P-20)."""
    _name = 'construction.reason.wizard'
    _description = 'Motivo del rechazo o la devolución'

    reason = fields.Text(string='Motivo', required=True)

    def action_confirm(self):
        self.ensure_one()
        ctx = self.env.context
        model, method = REASON_ACTIONS.get(ctx.get('construction_reason_action'), (None, None))
        if not model or ctx.get('active_model') != model:
            raise UserError(self.env._('No hay nada que rechazar o devolver.'))
        records = self.env[model].browse(ctx.get('active_ids') or [])
        getattr(records, method)(self.reason)
        return {'type': 'ir.actions.act_window_close'}
