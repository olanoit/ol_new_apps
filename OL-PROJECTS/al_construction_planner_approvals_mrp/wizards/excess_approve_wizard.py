# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class ConstructionExcessApproveWizard(models.TransientModel):
    _name = 'construction.excess.approve.wizard'
    _description = 'Aprobar el exceso de la orden de fabricación'

    production_id = fields.Many2one('mrp.production', string='Orden de fabricación',
                                    required=True)
    currency_id = fields.Many2one(related='production_id.construction_currency_id')
    excess_amount = fields.Monetary(related='production_id.construction_excess_amount',
                                    currency_field='currency_id')
    excess_pct = fields.Float(related='production_id.construction_excess_pct')
    reason = fields.Text(string='Motivo', required=True)

    def action_approve(self):
        self.ensure_one()
        production = self.production_id
        if production.construction_excess_action != 'approve':
            raise UserError(self.env._(
                'El exceso de %s no está dentro de su margen: solicite la aprobación.',
                production.name))
        production._construction_excess_approved(self.reason)
        return {'type': 'ir.actions.act_window_close'}
