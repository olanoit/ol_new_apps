# -*- coding: utf-8 -*-
from io import BytesIO

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import (
    SHEETS, sheet_key,
)
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_keys import KEYS_SHEET


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    def _construction_send_sheet_names(self):
        """Solo las pestañas del maestro y _CLAVES (paquete 1.13, M113-02)."""
        if self.construction_sheet_kind == 'budget':
            return super()._construction_send_sheet_names()
        return list(SHEETS) + [KEYS_SHEET]

    def _construction_furniture_workbook(self, sheets):
        """Libro .xlsx (bytes) con las pestañas del maestro de la hoja."""
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.remove(workbook.active)
        for name, rows in (sheets or {}).items():
            if not sheet_key(name):
                continue
            worksheet = workbook.create_sheet(name[:31])
            for row in rows or []:
                worksheet.append([None if value in ('', False) else value for value in row])
        if not workbook.worksheets:
            raise UserError(self.env._('La hoja no tiene ninguna pestaña del maestro.'))
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    def _construction_furniture_wizard(self, sheets):
        self.ensure_one()
        return self.env['construction.master.import.wizard'].create({
            'project_id': self.construction_project_id.id,
            'file': BinaryBytes(self._construction_furniture_workbook(sheets)),
            'filename': '%s.xlsx' % self.name,
            # Los productos nuevos de la hoja (PRODUCTOS NUEVOS) se crean.
            'create_missing_products': True,
        })

    def _construction_send_furniture(self, sheets):
        """Lleva las pestañas del maestro al asistente «Importar maestro y
        ETO» de la obra de la hoja (v1.5, M15-15)."""
        self.ensure_one()
        wizard = self._construction_furniture_wizard(sheets)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Importar maestro y ETO'),
            'res_model': wizard._name,
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def _construction_validate_furniture(self, sheets):
        """«Validar» del maestro (paquete 1.13, M113-03): el análisis del
        importador, sin escribir, como filas de ERRORES."""
        self.ensure_one()
        wizard = self._construction_furniture_wizard(sheets)
        try:
            data = wizard._analyze()
            issues = wizard._construction_issues(data)
        finally:
            wizard.unlink()
        return issues

    def action_construction_download_template(self):
        """«Descargar formato de carga» del menú del maestro (M113-03): el
        mismo de «Importar maestro y ETO»."""
        self.ensure_one()
        return self.env['construction.master.import.wizard'].action_download_template()
