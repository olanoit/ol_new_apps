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
            # M118-15, punto 3: al terminar, de vuelta a la hoja con el resumen.
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'success', 'sticky': False,
                    'message': self.env._('Hoja enviada al planificador (v%s).',
                                          self.spreadsheet_id.construction_send_version or 1),
                    'next': self.spreadsheet_id.action_open_spreadsheet(),
                },
            }
        return res

    def _construction_import_message(self, summary):
        """M118-15, punto 4: el mensaje nombra la hoja y su versión."""
        if not self.spreadsheet_id:
            return super()._construction_import_message(summary)
        return self.env._(
            'Hoja de planificación «%(sheet)s» enviada (v%(version)s): %(typologies)s tipologías, '
            '%(modules)s módulos de plantilla, %(spaces)s ambientes nuevos y %(eto)s módulos del '
            'ETO.', sheet=self.spreadsheet_id.name,
            version=(self.spreadsheet_id.construction_send_version or 0) + 1,
            typologies=summary['typologies'], modules=summary['modules'],
            spaces=summary['spaces'], eto=summary['eto'])


def _dates(payload):
    """Las fechas del presupuesto viajan como texto en el campo JSON."""
    blocks = []
    for block in payload.get('blocks') or []:
        block = dict(block)
        for key in ('start', 'end', 'start_adjusted', 'end_adjusted'):
            block[key] = fields.Date.to_date(block.get(key)) if block.get(key) else False
        blocks.append(block)
    return dict(payload, blocks=blocks)
