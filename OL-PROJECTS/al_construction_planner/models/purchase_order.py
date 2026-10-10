# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # La OC de servicio por contrata y obra (P-05) llega con las contratas
    # (fase 5); aquí solo el enlace con el plan.
    construction_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de recursos', copy=False,
        index='btree_not_null', check_company=True)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    construction_allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'purchase_line_id',
        string='Asignaciones del plan')
