# -*- coding: utf-8 -*-
import base64
import json

from odoo import models

from odoo.addons.al_construction_planner.wizards.master_import_layout import SHEETS

SPREADSHEET_VERSION = '18.5.10'
REFERENCE_SHEET = 'REFERENCIAS'
HEADER_STYLE, TITLE_STYLE = 1, 2
# Listas de Odoo de la pestaña REFERENCIAS: (id, título, modelo, columnas,
# columna inicial).
REFERENCE_LISTS = [
    ('1', 'Actividades', 'construction.labor.activity', ['code', 'name', 'stage', 'uom_id'], 0),
    ('2', 'Tipologías de la obra', 'construction.typology', ['code', 'name', 'family'], 5),
]
REFERENCE_ROWS = 300


def _col(index):
    """Letra de la columna (0 → A, 26 → AA)."""
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _construction_spreadsheet_data(self):
        """Hoja de trabajo vacía: una pestaña por hoja del maestro con sus
        encabezados y REFERENCIAS con listas de Odoo vivas."""
        self.ensure_one()
        sheets = []
        for index, (name, (_description, columns)) in enumerate(SHEETS.items(), start=1):
            cells = {'%s1' % _col(i): header for i, (_k, header, _r, _h) in enumerate(columns)}
            styles = {'%s1' % _col(i): HEADER_STYLE for i in range(len(columns))}
            sheets.append({
                'id': 'sheet%s' % index, 'name': name, 'colNumber': max(26, len(columns)),
                'rowNumber': 1000, 'cells': cells, 'styles': styles,
                'cols': {str(i): {'size': max(110, 9 * len(header))}
                         for i, (_k, header, _r, _h) in enumerate(columns)},
                'panes': {'xSplit': 0, 'ySplit': 1},
            })
        cells, styles, lists = {}, {}, {}
        domains = {
            'construction.labor.activity': [],
            'construction.typology': [['project_id', '=', self.id]],
        }
        for list_id, title, model, columns, start in REFERENCE_LISTS:
            cells['%s1' % _col(start)] = title
            styles['%s1' % _col(start)] = TITLE_STYLE
            for offset, field in enumerate(columns):
                col = _col(start + offset)
                cells['%s2' % col] = '=ODOO.LIST.HEADER(%s,"%s")' % (list_id, field)
                styles['%s2' % col] = HEADER_STYLE
                for row in range(1, REFERENCE_ROWS + 1):
                    cells['%s%s' % (col, row + 2)] = '=ODOO.LIST(%s,%s,"%s")' % (
                        list_id, row, field)
            lists[list_id] = {
                'id': list_id, 'name': title, 'model': model, 'columns': columns,
                'domain': domains[model], 'context': {}, 'orderBy': [{'name': 'code', 'asc': True}],
                'fieldMatching': {},
            }
        sheets.append({
            'id': 'sheet_ref', 'name': REFERENCE_SHEET, 'colNumber': 26,
            'rowNumber': REFERENCE_ROWS + 2, 'cells': cells, 'styles': styles,
        })
        settings = self.env['documents.document']._empty_spreadsheet_data().get('settings', {})
        return {
            'version': SPREADSHEET_VERSION,
            'sheets': sheets,
            'styles': {str(HEADER_STYLE): {'bold': True, 'fillColor': '#DDE4EE'},
                       str(TITLE_STYLE): {'bold': True, 'fontSize': 12}},
            'settings': settings,
            'lists': lists,
            'listNextId': len(REFERENCE_LISTS) + 1,
            'revisionId': 'START_REVISION',
        }

    def action_construction_open_spreadsheet(self):
        """Abre la hoja de trabajo de la obra en Documentos; la crea la
        primera vez."""
        self.ensure_one()
        Document = self.env['documents.document']
        document = Document.search([('construction_project_id', '=', self.id),
                                    ('handler', '=', 'spreadsheet')], limit=1)
        if not document:
            data = json.dumps(self._construction_spreadsheet_data())
            vals = {
                'name': self.env._('Maestro de planificación · %s', self.name),
                'mimetype': 'application/o-spreadsheet',
                'handler': 'spreadsheet',
                'datas': base64.b64encode(data.encode()),
                'construction_project_id': self.id,
            }
            folder = self['documents_folder_id'] if 'documents_folder_id' in self._fields \
                else False
            if folder:
                vals['folder_id'] = folder.id
            document = Document.create(vals)
        return document.action_open_spreadsheet()
