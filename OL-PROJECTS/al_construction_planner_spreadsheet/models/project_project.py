# -*- coding: utf-8 -*-
"""Hoja de trabajo de la oficina técnica (v1.5, M15-15; plantilla del piloto
en la v1.8, M18-22).

La oficina técnica de mobiliario arma el presupuesto y la carga de la obra en
la hoja de cálculo de Odoo. La plantilla reproduce el piloto armado por
Vicente el 16-oct-2026:

* LEEME y RESUMEN (tablas dinámicas sobre la propia hoja: ambientes por
  tipología, costo por módulo y sub etapa, despiece por tablero y materiales
  por tipología, sin el grupo «(Sin definir)» de las filas vacías);
* una pestaña por hoja del maestro (``SHEETS``) con datos crudos: las únicas
  columnas calculadas son el código del producto, los m² de la pieza y el
  costo de la línea de materiales, con el costo vivo del maestro;
* listas desplegables (familia, tipo de módulo, método de unión, sub etapa,
  categoría) y listas dependientes: el producto se elige después de la
  categoría, con los productos de esa categoría (pestaña oculta _LISTAS);
* REFERENCIAS con listas vivas de Odoo: actividades, tipologías, el maestro
  de productos completo (código, nombre completo, unidad, costo y categoría)
  y las categorías de último nivel.

Solo para la vertical Mobiliario: en construcción la receta sigue en los
Work Items y en el planificador.
"""
import base64
import json

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import SHEETS

SPREADSHEET_VERSION = '18.5.10'
REFERENCE_SHEET = 'REFERENCIAS'
LISTS_SHEET = '_LISTAS'
HEADER_STYLE, TITLE_STYLE, CALC_STYLE = 1, 2, 3
DEFAULT_ROWS = 300
MAX_PRODUCTS = 20000
EXCLUDED_CATEGORIES = ('Deliveries', 'Expenses')

# Columnas calculadas que agrega la plantilla a una hoja del maestro:
# (encabezado, fórmula con {r} = fila y {c:<clave>} = letra de la columna).
CALCULATED = {
    'PIEZAS': [
        ('m² (calc.)', '=IF(OR({c:qty}{r}="",{c:length}{r}="",{c:width}{r}=""),"",'
                       '{c:qty}{r}*{c:length}{r}*{c:width}{r}/1000000)'),
    ],
    'BOM': [
        ('Costo de la línea (calc.)', '=IF({c:product_code}{r}="","",IFERROR({c:qty}{r}*'
                                      'VLOOKUP({c:product_code}{r},REFERENCIAS!$K$3:$M${p},3,0),'
                                      '{c:qty}{r}*{c:cost}{r}))'),
    ],
}
# Columna «Producto» (lista dependiente) y código calculado desde ella.
PRODUCT_PICK = {'PIEZAS': ('categ', 'Producto'), 'BOM': ('categ', 'product_name')}
FIXED_LISTS = {
    ('TIPOLOGIAS', 'family'): ['Cocina', 'Closet', 'Baño', 'Lavandería', 'Ducto', 'Área común',
                               'Especial', 'Otro'],
    ('MODULOS', 'type'): ['Bajo', 'Alto', 'Cajonera', 'Campana', 'Repisero', 'Otro'],
    ('MODULOS', 'module_class'): ['Estándar', 'Especial'],
    ('MODULOS', 'join_method'): ['Tornillo', 'Tarugo', 'Mixto', 'Minifix', 'Sin unión'],
    ('MODULOS', 'ml_group'): ['Mueble bajo', 'Mueble alto', 'Sin ML'],
    ('TARIFAS', 'family'): ['Cocina y baño', 'Closet y cajones'],
}
LEEME = [
    'Hoja de trabajo de la oficina técnica (mobiliario)',
    '',
    '1. OBRA: datos y condiciones de la obra (Inicio, Fin, Cliente, Adelanto %, Fondo de '
    'garantía %).',
    '2. ARBOL: piso, departamento, ambiente, tipología y tipo de unidad, medidos sobre el plano.',
    '3. TIPOLOGIAS, MUEBLES y MODULOS: código del módulo (el del ETO), nombre, mueble, tipo, '
    'ancho, tipo de módulo y método de unión.',
    '4. PIEZAS y BOM: elija primero la categoría y después el producto (la lista muestra solo '
    'los de esa categoría; se puede escribir para buscar). El código, los m² y el costo se '
    'calculan solos con el costo vivo del maestro.',
    '5. PRODUCTOS NUEVOS: los que aún no están en el maestro, con un código provisional; al '
    'enviar se crean con el código de la familia y el provisional se reemplaza.',
    '6. ACTIVIDADES, TARIFAS, CONTRATOS, HITOS, VENTA y MO PROPIA: contratas, tarifas de la '
    'obra, contrato con el cliente y mano de obra propia.',
    '7. RESUMEN: tablas dinámicas sobre la propia hoja.',
    '8. Aprobado el presupuesto por el cliente: Archivo › Enviar al planificador. Un segundo '
    'envío no duplica nada.',
]


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

    construction_spreadsheet_rows = fields.Integer(
        string='Filas de la hoja de trabajo', default=DEFAULT_ROWS,
        help='Filas con listas dependientes y columnas calculadas por pestaña (ampliable por '
             'obra antes de crear la hoja).')

    def _construction_is_furniture(self):
        self.ensure_one()
        profile = self.construction_profile_id
        return not profile or profile.code != 'construction'

    # ------------------------------------------------------------------
    # Plantilla
    # ------------------------------------------------------------------
    def _construction_sheet_columns(self, name):
        """[(clave, encabezado)] de una pestaña del maestro con la columna
        «Producto» de las listas dependientes."""
        columns = [(key, header) for key, header, _r, _h in SHEETS[name][1]]
        if name == 'PIEZAS' and not any(key == 'product_name' for key, _h in columns):
            index = next(i for i, (key, _h) in enumerate(columns) if key == 'product_code')
            columns.insert(index, ('product_name', 'Producto'))
        return columns

    def _construction_reference_counts(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        products = self.env['product.product'].search_count(
            [('type', '=', 'consu'), ('company_id', 'in', (company.id, False))])
        categories = self.env['product.category'].search_count(
            [('child_id', '=', False), ('name', 'not in', EXCLUDED_CATEGORIES)])
        return min(max(products, 1), MAX_PRODUCTS), max(categories, 1)

    def _construction_spreadsheet_data(self):
        """Hoja de trabajo con la estructura del piloto (M18-22)."""
        self.ensure_one()
        rows = max(self.construction_spreadsheet_rows or DEFAULT_ROWS, 10)
        n_products, n_categories = self._construction_reference_counts()
        last_product = n_products + 2
        last_category = n_categories + 2
        stage_labels = [label for _code, label in self.env['construction.stage']._get_selection()]
        sheets, pivots = [], {}
        sheet_ids = {}

        # LEEME
        sheets.append({
            'id': 'sheet_leeme', 'name': 'LEEME', 'colNumber': 4, 'rowNumber': 40,
            'cells': {'A%s' % (i + 1): text for i, text in enumerate(LEEME) if text},
            'styles': {'A1': TITLE_STYLE}, 'cols': {'0': {'size': 900}},
        })
        sheets.append({'id': 'sheet_resumen', 'name': 'RESUMEN', 'colNumber': 30,
                       'rowNumber': 400, 'cells': {}, 'styles': {}})

        # Pestañas del maestro.
        positions = {}
        for index, name in enumerate(SHEETS, start=1):
            columns = self._construction_sheet_columns(name)
            calculated = CALCULATED.get(name, [])
            letters = {key: _col(i) for i, (key, _h) in enumerate(columns)}
            positions[name] = letters
            headers = [header for _key, header in columns] + [h for h, _f in calculated]
            cells = {'%s1' % _col(i): header for i, header in enumerate(headers)}
            styles = {'%s1' % _col(i): HEADER_STYLE for i in range(len(headers))}
            rules = []

            def fmt(formula, row, letters=letters):
                text = formula.replace('{r}', str(row)).replace('{p}', str(last_product))
                for key, letter in letters.items():
                    text = text.replace('{c:%s}' % key, letter)
                return text

            for offset, (_header, formula) in enumerate(calculated):
                col = _col(len(columns) + offset)
                for row in range(2, rows + 2):
                    cells['%s%s' % (col, row)] = fmt(formula, row)
                styles['%s1' % col] = CALC_STYLE
            if name in PRODUCT_PICK:
                # Código calculado desde «[código] nombre» del producto elegido.
                pick = letters['product_name']
                code = letters['product_code']
                for row in range(2, rows + 2):
                    cells['%s%s' % (code, row)] = (
                        '=IF({p}{r}="","",IFERROR(MID({p}{r},2,FIND("]",{p}{r})-2),{p}{r}))'
                        .replace('{p}', pick).replace('{r}', str(row)))
                styles['%s1' % code] = CALC_STYLE
                rules.append({'id': '%s_categ' % name, 'ranges': ['%s2:%s%s' % (
                    letters['categ'], letters['categ'], rows + 1)], 'isBlocking': False,
                    'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                                  'values': ['%s!$R$3:$R$%s' % (REFERENCE_SHEET, last_category)]}})
                base = 0 if name == 'PIEZAS' else rows
                for row in range(2, rows + 2):
                    list_row = base + row - 1
                    rules.append({
                        'id': '%s_prod_%s' % (name, row), 'isBlocking': False,
                        'ranges': ['%s%s' % (pick, row)],
                        'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                                      'values': ['%s!$A$%s:$ZZ$%s' % (LISTS_SHEET, list_row,
                                                                     list_row)]}})
            for (sheet, key), values in FIXED_LISTS.items():
                if sheet == name and key in letters:
                    rules.append({'id': '%s_%s' % (name, key), 'isBlocking': False,
                                  'ranges': ['%s2:%s%s' % (letters[key], letters[key], rows + 1)],
                                  'criterion': {'type': 'isValueInList', 'values': values,
                                                'displayStyle': 'arrow'}})
            stage_key = 'stage' if 'stage' in letters else None
            if stage_key and stage_labels:
                rules.append({'id': '%s_stage' % name, 'isBlocking': False,
                              'ranges': ['%s2:%s%s' % (letters[stage_key], letters[stage_key],
                                                       rows + 1)],
                              'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                                            'values': ['%s!$T$3:$T$%s' % (
                                                REFERENCE_SHEET, len(stage_labels) + 2)]}})
            sheet_id = 'sheet%s' % index
            sheet_ids[name] = sheet_id
            sheets.append({
                'id': sheet_id, 'name': name, 'colNumber': max(26, len(headers)),
                'rowNumber': rows + 50, 'cells': cells, 'styles': styles,
                'cols': {str(i): {'size': max(110, 9 * len(header))}
                         for i, header in enumerate(headers)},
                'panes': {'xSplit': 0, 'ySplit': 1},
                'dataValidationRules': rules,
            })

        # REFERENCIAS: listas vivas de Odoo.
        company = self.company_id or self.env.company
        reference_lists = [
            ('1', 'Actividades', 'construction.labor.activity',
             ['code', 'name', 'stage', 'uom_id'], 0, 300,
             [['company_id', 'in', [company.id, False]]], 'code'),
            ('2', 'Tipologías de la obra', 'construction.typology', ['code', 'name', 'family'],
             5, 300, [['project_id', '=', self.id]], 'code'),
            ('3', 'Maestro de productos', 'product.product',
             ['display_name', 'default_code', 'uom_id', 'standard_price', 'categ_id'], 9,
             n_products, [['type', '=', 'consu'], ['company_id', 'in', [company.id, False]]],
             'default_code'),
            ('4', 'Categorías', 'product.category', ['name'], 17, n_categories,
             [['child_id', '=', False], ['name', 'not in', list(EXCLUDED_CATEGORIES)]], 'name'),
        ]
        cells, styles, lists = {}, {}, {}
        for list_id, title, model, columns, start, count, domain, order in reference_lists:
            cells['%s1' % _col(start)] = title
            styles['%s1' % _col(start)] = TITLE_STYLE
            for offset, field in enumerate(columns):
                col = _col(start + offset)
                cells['%s2' % col] = '=ODOO.LIST.HEADER(%s,"%s")' % (list_id, field)
                styles['%s2' % col] = HEADER_STYLE
                for row in range(1, count + 1):
                    cells['%s%s' % (col, row + 2)] = '=ODOO.LIST(%s,%s,"%s")' % (
                        list_id, row, field)
            lists[list_id] = {
                'id': list_id, 'name': title, 'model': model, 'columns': columns,
                'domain': domain, 'context': {}, 'orderBy': [{'name': order, 'asc': True}],
                'fieldMatching': {},
            }
        # Categoría de último nivel del producto (sin la ruta) y la de cada fila
        # de categorías.
        cells['O2'] = 'Categoría (último nivel)'
        styles['O2'] = HEADER_STYLE
        for row in range(3, last_product + 1):
            cells['O%s' % row] = '=IFERROR(TRIM(RIGHT(SUBSTITUTE(N%s,"/",REPT(" ",100)),100)),' \
                                 'N%s)' % (row, row)
        cells['T1'] = 'Sub etapas'
        styles['T1'] = TITLE_STYLE
        for row, label in enumerate(stage_labels, start=3):
            cells['T%s' % row] = label
        sheets.append({
            'id': 'sheet_ref', 'name': REFERENCE_SHEET, 'colNumber': 26,
            'rowNumber': max(last_product, 302) + 2, 'cells': cells, 'styles': styles,
        })

        # _LISTAS (oculta): la lista de productos de la categoría de cada fila.
        list_cells = {}
        for name, base in (('PIEZAS', 0), ('BOM', rows)):
            categ = positions[name]['categ']
            for row in range(2, rows + 2):
                list_cells['A%s' % (base + row - 1)] = (
                    '=IFERROR(TRANSPOSE(FILTER(%s!$J$3:$J$%s,%s!$O$3:$O$%s=%s!%s%s)),"")' % (
                        REFERENCE_SHEET, last_product, REFERENCE_SHEET, last_product, name,
                        categ, row))
        sheets.append({'id': 'sheet_listas', 'name': LISTS_SHEET, 'colNumber': 60,
                       'rowNumber': 2 * rows + 2, 'cells': list_cells, 'isVisible': False})

        # RESUMEN: tablas dinámicas sobre la propia hoja. Las filas vacías del
        # rango quedan en el grupo nulo, que va al final con el orden
        # ascendente: la fórmula muestra solo las filas con dato.
        summary = sheets[1]
        specs = [
            ('1', 'Ambientes por tipología', 'ARBOL', 'typology', None, 'space', 'count', 'A1'),
            ('2', 'Costo por módulo y sub etapa', 'BOM', 'module', 'stage',
             'Costo de la línea (calc.)', 'sum', 'A40'),
            ('3', 'Despiece por tablero', 'PIEZAS', 'product_name', None,
             'm² (calc.)', 'sum', 'L1'),
            ('4', 'Materiales por tipología', 'BOM', 'product_name', 'typology', 'qty', 'sum',
             'L40'),
        ]
        for pivot_id, title, sheet, row_key, col_key, measure, aggregator, anchor in specs:
            columns = self._construction_sheet_columns(sheet)
            headers = [header for _k, header in columns] + [h for h, _f in CALCULATED.get(sheet, [])]
            by_key = dict(columns)
            measure_name = by_key.get(measure, measure)
            pivots[pivot_id] = {
                'type': 'SPREADSHEET', 'name': title, 'formulaId': pivot_id,
                'dataSet': {'sheetId': sheet_ids[sheet], 'zone': {
                    'top': 0, 'bottom': rows, 'left': 0, 'right': len(headers) - 1}},
                'rows': [{'fieldName': by_key[row_key], 'order': 'asc'}],
                'columns': [{'fieldName': by_key[col_key], 'order': 'asc'}] if col_key else [],
                'measures': [{'id': '%s:%s' % (measure_name, aggregator),
                              'fieldName': measure_name, 'aggregator': aggregator}],
            }
            letter = positions[sheet][row_key] if row_key in positions[sheet] else 'A'
            data_range = '%s!%s2:%s%s' % (sheet, letter, letter, rows + 1)
            count_rows = 'IFERROR(ROWS(UNIQUE(FILTER(%s,%s<>""))),0)' % (data_range, data_range)
            formula = '=PIVOT(%s,%s' % (pivot_id, count_rows)
            if col_key:
                col_letter = positions[sheet][col_key]
                col_range = '%s!%s2:%s%s' % (sheet, col_letter, col_letter, rows + 1)
                formula += ',TRUE,TRUE,IFERROR(ROWS(UNIQUE(FILTER(%s,%s<>""))),0)' % (
                    col_range, col_range)
            summary['cells'][anchor] = title
            summary['styles'][anchor] = TITLE_STYLE
            column, line = anchor[0], int(anchor[1:])
            summary['cells']['%s%s' % (column, line + 1)] = formula + ')'

        settings = self.env['documents.document']._empty_spreadsheet_data().get('settings', {})
        return {
            'version': SPREADSHEET_VERSION,
            'sheets': sheets,
            'styles': {str(HEADER_STYLE): {'bold': True, 'fillColor': '#DDE4EE'},
                       str(TITLE_STYLE): {'bold': True, 'fontSize': 12},
                       str(CALC_STYLE): {'bold': True, 'fillColor': '#E8F0E0'}},
            'settings': settings,
            'lists': lists,
            'listNextId': len(reference_lists) + 1,
            'pivots': pivots,
            'pivotNextId': len(pivots) + 1,
            'revisionId': 'START_REVISION',
        }

    def action_construction_open_spreadsheet(self):
        """Abre la hoja de trabajo de la obra en Documentos; la crea la
        primera vez. Solo para la vertical Mobiliario."""
        self.ensure_one()
        if not self._construction_is_furniture():
            raise UserError(self.env._(
                'La hoja de trabajo es de la vertical Mobiliario: en construcción la receta '
                'sigue en los Work Items y en las recetas del planificador.'))
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
