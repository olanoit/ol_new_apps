# -*- coding: utf-8 -*-
from odoo import models


class ConstructionValuation(models.Model):
    _inherit = 'construction.valuation'

    def _construction_annex_detail(self):
        """Paquete 1.17, M117-25: en mobiliario, el departamento y su tipología."""
        rows = super()._construction_annex_detail()
        for row, line in zip(rows, self.milestone_line_ids):
            task = line.task_id
            row['detail'] = task.construction_typology_id.display_name or ''
        return rows
