# -*- coding: utf-8 -*-

from odoo import fields, models


class ReportPosOrder(models.Model):
    _inherit = "report.pos.order"

    seller_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Vendedor',
    )

    def _select(self):
        return super()._select() + ", s.seller_id as seller_id"

    def _group_by(self):
        return super()._group_by() + ", s.seller_id"
