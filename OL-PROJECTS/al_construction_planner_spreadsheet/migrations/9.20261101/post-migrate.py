# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4 (CR-22 b, c, f y M116-09): las hojas de presupuesto y
plan ya creadas quedan como las nuevas, sin borrar lo que escribió el usuario:

* sin la función N(), que la hoja de Odoo no tiene (#NAME?);
* con «Costo unitario sin APU» en PRESUPUESTO, al final si faltaba (D1);
* encabezados de fórmula en gris;
* la pestaña oculta _CLAVES, para leer las columnas por su clave.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.al_construction_planner_sale.wizards.budget_book_wizard import (
    COLUMNS, PRESUPUESTO_FORMULAS,
)
from odoo.addons.al_construction_planner_spreadsheet.models.project_project import CALCULATED
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_migration import (
    add_keys_sheet, cell_content, col_letter, first_free_column, header_cells,
    migrate_documents, norm, paint_headers, replace_n, set_cell_content, style_id,
)

GREY = {'bold': True, 'fillColor': '#D9D9D9'}
YELLOW = {'bold': True, 'fillColor': '#FFF2CC'}
HEADER = {'bold': True, 'fillColor': '#DDE4EE'}


def _transform(data):
    changed = False
    for sheet in data.get('sheets') or []:
        cells = sheet.get('cells') or {}
        for ref, cell in list(cells.items()):
            content = cell_content(cell)
            fixed = replace_n(content)
            if fixed != content:
                set_cell_content(cells, ref, fixed)
                changed = True
        if sheet.get('name') == 'PRESUPUESTO':
            label = COLUMNS['PRESUPUESTO'][5][1][0]  # «Costo unitario sin APU»
            if norm(label) not in {norm(text) for _ref, text in header_cells(sheet).values()}:
                ref = '%s1' % col_letter(first_free_column(sheet))
                cells[ref] = label
                sheet.setdefault('styles', {})[ref] = style_id(data, YELLOW)
                sheet['colNumber'] = max(sheet.get('colNumber') or 0,
                                         first_free_column(sheet) + 1)
                changed = True
    formula_headers = [header for headers in CALCULATED.values() for header, _f in headers]
    formula_headers += [aliases[0] for key, aliases, _required in COLUMNS['PRESUPUESTO']
                        if key in PRESUPUESTO_FORMULAS]
    if paint_headers(data, {'INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO'}, formula_headers,
                     GREY):
        changed = True
    columns = {name: [(key, aliases) for key, aliases, _required in COLUMNS[name]]
               for name in ('INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO')}
    if add_keys_sheet(data, columns, header_style=style_id(data, HEADER)):
        changed = True
    return changed


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    documents = env['documents.document'].with_context(active_test=False).search(
        [('construction_sheet_kind', '=', 'budget'), ('handler', '=', 'spreadsheet')])
    migrate_documents(env, documents, _transform)
