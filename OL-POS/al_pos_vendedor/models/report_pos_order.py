# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.tools import SQL


class ReportPosOrder(models.Model):
    _inherit = "report.pos.order"

    seller_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Vendedor',
    )

    def _select(self):
        # Odoo 20: la consulta es SQL y el informe ya no agrupa (una fila por línea).
        return SQL("%s, s.seller_id AS seller_id", super()._select())
