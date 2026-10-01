# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    construction_request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento de obra',
        index='btree_not_null', copy=False, readonly=True)


class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    construction_request_line_id = fields.Many2one(
        'construction.material.request.line', string='Línea de requerimiento de obra',
        index='btree_not_null', copy=False, readonly=True)
