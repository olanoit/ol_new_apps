# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    construction_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de recursos', readonly=True, copy=False,
        index='btree_not_null', check_company=True)


class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    construction_allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'purchase_request_line_id',
        string='Asignaciones del plan')
    construction_plan_mode = fields.Selection(
        [('project', 'Con analítica de la obra'), ('general', 'Stock general')],
        string='Modo de compra masiva', readonly=True, copy=False)
