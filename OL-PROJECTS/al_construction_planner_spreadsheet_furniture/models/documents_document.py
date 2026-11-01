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

    # ------------------------------------------------------------------
    # Importar Excel a la hoja (paquete 1.13, M113-04/05)
    # ------------------------------------------------------------------
    def construction_sheet_extension(self, rows):
        """Celdas, reglas y formato condicional para ampliar el maestro a
        ``rows`` filas de datos (las mismas fórmulas y listas de la plantilla).

        :return: ``{'rows': n, 'sheets': {pestaña: {'cells', 'rules',
            'conditional', 'row_number'}}, 'summary': celdas de RESUMEN,
            'pivots': {id: fila final}}``; vacío si la hoja es anterior al
            paquete 1.16 o ya tiene esas filas.
        """
        self.ensure_one()
        current = self.construction_sheet_rows
        project = self.construction_project_id
        if not current or rows <= current or self.construction_sheet_kind != 'furniture':
            return {}
        layout = project._construction_sheet_layout()
        parts = project._construction_row_parts(layout, current + 2, rows + 1)
        result = {'rows': rows, 'sheets': {}, 'pivots': {}}
        for name, part in parts.items():
            part['row_number'] = rows + 50
            result['sheets'][name] = part
        result['sheets']['_LISTAS']['row_number'] = project._construction_helper_row(
            layout, 'BOM', 'prod', rows + 1) + 10
        summary_cells, _styles, pivots = project._construction_summary(layout, rows, {})
        result['summary'] = summary_cells
        result['pivots'] = {pivot_id: pivot['dataSet']['zone']['bottom']
                            for pivot_id, pivot in pivots.items()}
        self.construction_sheet_rows = rows
        return result

    def construction_sheet_import_done(self, filename, sheets, errors, warnings):
        """Deja en el historial de la obra la importación de un Excel a la
        hoja (M113-04)."""
        self.ensure_one()
        # sudo: quien planifica puede no tener escritura en la obra; solo se
        # deja el mensaje con él como autor.
        project_sudo = self.construction_project_id.sudo()
        project_sudo.message_post(author_id=self.env.user.partner_id.id, body=self.env._(
            'Excel importado a la hoja de trabajo (%(file)s): %(sheets)s pestañas, %(errors)s '
            'errores y %(warnings)s avisos al validar.', file=filename or '—', sheets=sheets,
            errors=errors, warnings=warnings))
        return True
