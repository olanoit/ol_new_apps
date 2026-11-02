# -*- coding: utf-8 -*-
"""Versión de la hoja en cada envío del maestro (paquete 1.13, M113-11)."""
from odoo import fields, models


class ConstructionMasterImportWizard(models.TransientModel):
    _inherit = 'construction.master.import.wizard'

    spreadsheet_id = fields.Many2one(
        'documents.document', string='Hoja de trabajo', readonly=True,
        help='Hoja desde la que se envió el maestro: al importar se guarda su versión.',
        check_company=True)

    def action_import(self):
        res = super().action_import()
        if self.spreadsheet_id:
            self.spreadsheet_id._construction_sent(self.env._('Hoja enviada al planificador'))
        return res
