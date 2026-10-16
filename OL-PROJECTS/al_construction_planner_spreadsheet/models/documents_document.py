# -*- coding: utf-8 -*-
import base64
from io import BytesIO

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import sheet_key


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    construction_project_id = fields.Many2one(
        'project.project', string='Obra (hoja de trabajo)', index='btree_not_null',
        ondelete='set null', readonly=True, copy=False,
        help='Obra cuyo maestro de planificación se llena en esta hoja.')

    def _get_spreadsheet_metadata(self, access_token=None):
        data = super()._get_spreadsheet_metadata(access_token)
        # sudo: solo se lee el vínculo de la hoja con su obra para mostrar
        # el menú «Enviar al planificador».
        project_sudo = self.sudo().construction_project_id
        data['construction_project_id'] = project_sudo.id or False
        return data

    def action_construction_send_to_planner(self, sheets):
        """Lleva las pestañas del maestro al asistente «Importar maestro y
        ETO» de la obra de la hoja.

        :param sheets: ``{nombre de la pestaña: [[valor, …], …]}`` con los
            valores calculados de cada pestaña, fila por fila (la primera, los
            encabezados).
        :return: la acción del asistente con su análisis.
        """
        self.ensure_one()
        project = self.construction_project_id
        if not project:
            raise UserError(self.env._('Esta hoja no es la hoja de trabajo de una obra.'))
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
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': project.id,
            'file': base64.b64encode(output.getvalue()),
            'filename': '%s.xlsx' % self.name,
            # Los productos nuevos de la hoja (PRODUCTOS NUEVOS) se crean.
            'create_missing_products': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Importar maestro y ETO'),
            'res_model': wizard._name,
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }
