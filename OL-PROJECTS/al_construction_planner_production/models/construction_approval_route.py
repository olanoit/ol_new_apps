# -*- coding: utf-8 -*-
from odoo import fields, models


class ConstructionApprovalRoute(models.Model):
    _inherit = 'construction.approval.route'

    document_type = fields.Selection(
        selection_add=[('accessories', 'Accesorios de armado')],
        ondelete={'accessories': 'cascade'})
