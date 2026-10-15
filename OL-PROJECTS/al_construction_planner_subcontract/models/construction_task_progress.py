# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

# Liquidación que deja el avance como «liquidado» (no se revierte).
SETTLED_STATES = ('approved', 'paid')


class ConstructionTaskProgress(models.Model):
    _inherit = 'construction.task.progress'

    settlement_id = fields.Many2one(
        'construction.contract.settlement', string='Liquidación', readonly=True, copy=False,
        index='btree_not_null', check_company=True)
    settled = fields.Boolean(compute='_compute_settled', store=True)

    @api.depends('settlement_id.state')
    def _compute_settled(self):
        for progress in self:
            progress.settled = progress.settlement_id.state in SETTLED_STATES

    def _construction_check_resettable(self):
        super()._construction_check_resettable()
        busy = self.filtered(lambda p: p.settlement_id.state in ('submitted', 'validated'))
        if busy:
            raise UserError(self.env._(
                'Estos avances están en una liquidación presentada o validada; devuélvala '
                'antes: %s.', ', '.join(busy.mapped('name'))))

    def _construction_reset_values(self):
        return dict(super()._construction_reset_values(), settlement_id=False)

    def action_reset(self):
        """Si estaba en una liquidación en borrador, sale de ella."""
        settlements = self.settlement_id
        res = super().action_reset()
        settlements._refresh_lines()
        return res

    def write(self, vals):
        res = super().write(vals)
        if 'settlement_id' in vals:
            self.plan_line_id._refresh_control()
        return res
