# -*- coding: utf-8 -*-
"""El requerimiento de fabricación a la vista en la orden y en sus
transferencias (paquete 1.25, M125-02), y el cierre de su actividad
(M125-03)."""
from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_mrp_request_id = fields.Many2one(
        'construction.manufacturing.request', string='Requerimiento de fabricación',
        readonly=True, copy=False, index='btree_not_null', check_company=True)
    construction_group_task_id = fields.Many2one(
        'project.task', string='Agrupador', readonly=True, copy=False)
    construction_typology_id = fields.Many2one(
        'construction.typology', string='Tipología', readonly=True, copy=False)

    def action_view_construction_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Requerimiento de fabricación'),
            'res_model': 'construction.manufacturing.request',
            'res_id': self.construction_mrp_request_id.id,
            'view_mode': 'form',
        }

    def action_confirm(self):
        requests = self.construction_mrp_request_id
        res = super().action_confirm()
        requests._construction_close_review()
        return res

    def action_cancel(self):
        requests = self.construction_mrp_request_id
        res = super().action_cancel()
        requests._construction_close_review()
        return res


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    construction_mrp_request_id = fields.Many2one(
        'construction.manufacturing.request', string='Requerimiento de fabricación',
        compute='_compute_construction_mrp_request_id', search='_search_construction_mrp_request_id',
        groups='stock.group_stock_user')

    @api.depends('reference_ids')
    def _compute_construction_mrp_request_id(self):
        for picking in self:
            picking.construction_mrp_request_id = \
                picking.reference_ids.construction_mrp_request_ids[:1]

    def _search_construction_mrp_request_id(self, operator, value):
        return [('reference_ids.construction_mrp_request_ids', operator, value)]
