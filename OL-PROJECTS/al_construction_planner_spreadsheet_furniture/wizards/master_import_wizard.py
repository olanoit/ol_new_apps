# -*- coding: utf-8 -*-
"""Versión de la hoja en cada envío del maestro (paquete 1.13, M113-11)."""
from odoo import fields, models


class ConstructionMasterImportWizard(models.TransientModel):
    _inherit = 'construction.master.import.wizard'

    spreadsheet_id = fields.Many2one(
        'documents.document', string='Hoja de trabajo', readonly=True,
        help='Hoja desde la que se envió el maestro: al importar se guarda su versión.')
    # M119-01: rendimientos y presupuesto de mano de obra de la hoja.
    construction_labor_payload = fields.Json(string='Presupuesto de mano de obra de la hoja')

    def action_import(self):
        res = super().action_import()
        if self.construction_labor_payload and self.project_id:
            self.project_id._construction_labor_budget_apply(
                _dates(self.construction_labor_payload))
        if self.spreadsheet_id:
            self.spreadsheet_id._construction_sent(self.env._('Hoja enviada al planificador'))
        return res


def _dates(payload):
    """Las fechas del presupuesto viajan como texto en el campo JSON."""
    blocks = []
    for block in payload.get('blocks') or []:
        block = dict(block)
        for key in ('start', 'end', 'start_adjusted', 'end_adjusted'):
            block[key] = fields.Date.to_date(block.get(key)) if block.get(key) else False
        blocks.append(block)
    return dict(payload, blocks=blocks)
