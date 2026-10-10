# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    construction_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de recursos', readonly=True, copy=False,
        index='btree_not_null', check_company=True)

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'purchase_request_line_id', self.line_ids)
        return res


class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    construction_allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'purchase_request_line_id',
        string='Asignaciones del plan')
    construction_plan_mode = fields.Selection(
        [('project', 'Con analítica de la obra'), ('general', 'Stock general')],
        string='Modo de compra masiva', readonly=True, copy=False)

    def write(self, vals):
        res = super().write(vals)
        if {'cancelled', 'product_qty', 'product_uom_id'} & set(vals):
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'purchase_request_line_id', self)
        return res
