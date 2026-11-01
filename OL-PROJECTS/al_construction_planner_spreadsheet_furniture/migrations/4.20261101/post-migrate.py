# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4 (M116-09): los maestros de mobiliario ya creados
toman la convención común (amarillo el dato, gris la fórmula) y la pestaña
oculta _CLAVES, para leer las columnas por su clave. El perfil Mobiliario
abre el maestro de mobiliario. No se borra nada de lo escrito."""
from odoo import SUPERUSER_ID, api

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import SHEETS
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_migration import (
    add_keys_sheet, header_cells, migrate_documents, paint_headers, style_id,
)
from odoo.addons.al_construction_planner_spreadsheet_furniture.models.project_project import (
    CALCULATED,
)

GREY = {'bold': True, 'fillColor': '#D9D9D9'}
YELLOW = {'bold': True, 'fillColor': '#FFF2CC'}
HEADER = {'bold': True, 'fillColor': '#DDE4EE'}
OLD_CALC = '#E8F0E0'


def _transform(data):
    changed = False
    # Las columnas calculadas pasan de verde a gris.
    for key, style in (data.get('styles') or {}).items():
        if isinstance(style, dict) and style.get('fillColor') == OLD_CALC:
            style['fillColor'] = GREY['fillColor']
            changed = True
    calc_headers = {header for headers in CALCULATED.values() for header, _f in headers}
    calc_headers.add('Código del producto')
    data_headers = set()
    for name, (_description, columns) in SHEETS.items():
        data_headers |= {header for key, header, _r, _h in columns
                         if header not in calc_headers}
    data_headers.add('Producto')
    if paint_headers(data, set(SHEETS), data_headers, YELLOW):
        changed = True
    if paint_headers(data, set(SHEETS), calc_headers, GREY):
        changed = True
    columns = {}
    for name, (_description, sheet_columns) in SHEETS.items():
        columns[name] = [(key, [header]) for key, header, _r, _h in sheet_columns]
        if name in ('PIEZAS', 'BOM') and not any(k == 'product_name' for k, _t in columns[name]):
            columns[name].append(('product_name', ['Producto']))
    if add_keys_sheet(data, columns, header_style=style_id(data, HEADER)):
        changed = True
    return changed


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['construction.vertical.profile']._construction_set_furniture_sheet()
    documents = env['documents.document'].with_context(active_test=False).search(
        [('construction_sheet_kind', '=', 'furniture'), ('handler', '=', 'spreadsheet')])
    migrate_documents(env, documents, _transform)
