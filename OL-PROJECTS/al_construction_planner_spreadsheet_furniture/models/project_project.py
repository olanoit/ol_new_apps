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

Solo para la vertical Mobiliario (puente de al_construction_planner_spreadsheet
desde el requerimiento CREVAL v1.0, 6.7): en construcción, la hoja es la del
presupuesto y el plan del módulo genérico.
"""
import base64
import json
import re

from odoo import models

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import SHEETS
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_keys import keys_sheet
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_migration import (
    first_part, last_part, second_part,
)

SPREADSHEET_VERSION = '18.5.10'
REFERENCE_SHEET = 'REFERENCIAS'
LISTS_SHEET = '_LISTAS'
HEADER_STYLE, TITLE_STYLE, CALC_STYLE, DATA_STYLE = 1, 2, 3, 4
# Convención común de las hojas de trabajo (paquete 1.16, M116-09): amarillo
# para el dato del usuario y gris para la fórmula.
STYLES = {str(HEADER_STYLE): {'bold': True, 'fillColor': '#DDE4EE'},
          str(TITLE_STYLE): {'bold': True, 'fontSize': 12},
          str(CALC_STYLE): {'bold': True, 'fillColor': '#D9D9D9'},
          str(DATA_STYLE): {'bold': True, 'fillColor': '#FFF2CC'}}
# El producto se elige por nombre, con la unidad y el código al final
# (M116-09): «nombre · unidad · código». El código calculado lee el último
# tramo; un «[código] nombre» de una hoja anterior se sigue leyendo.
PICK_SEPARATOR = ' · '
CODE_FROM_PICK = ('=IF({p}{r}="","",IF(LEFT({p}{r},1)="[",IFERROR(MID({p}{r},2,FIND("]",{p}{r})'
                  '-2),{p}{r}),IFERROR(%s,{p}{r})))' % last_part('{p}{r}', '"%s"' % PICK_SEPARATOR))
DEFAULT_ROWS = 300
MAX_PRODUCTS = 20000
# Paquete 1.13, M113-06 punto 7: materiales base de la obra (tablero, canto,
# bisagra…). Van primero en la lista de su categoría.
WORK_MATERIALS_SHEET = 'MATERIALES OBRA'
WORK_MATERIALS_ROWS = 30
EXCLUDED_CATEGORIES = ('Deliveries', 'Expenses')

# Columnas calculadas que agrega la plantilla a una hoja del maestro:
# (encabezado, fórmula con {r} = fila, {c:<clave>} = letra de la columna y
# {x:<pestaña>:<clave>} = columna completa de otra pestaña). Una clave que
# empieza con «#» es el encabezado de una columna calculada.
_ML_GROUPS_COUNTED = ('Mueble bajo', 'Bajo', 'Mueble alto', 'Alto', 'Mueble completo',
                      'Completo')
# Ambientes de la obra con la tipología de la fila.
_IN_SITE = ('IFERROR(XLOOKUP({c:typology}{r},{x:TIPOLOGIAS:code},'
            '{x:TIPOLOGIAS:#En la obra (calc.)}),0)')
CALCULATED = {
    # Paquete 1.13, M113-07/09: lo que INICIO, FICHA y CONTROL suman.
    'TIPOLOGIAS': [
        ('En la obra (calc.)', '=IF({c:code}{r}="","",COUNTIF({x:ARBOL:typology},{c:code}{r}))'),
        ('Módulos (calc.)', '=IF({c:code}{r}="","",COUNTIF({x:MODULOS:typology},{c:code}{r}))'),
        ('Módulos a armar (calc.)', '=IF({c:code}{r}="","",SUMIFS({x:MODULOS:#A armar (calc.)},'
                                    '{x:MODULOS:typology},{c:code}{r}))'),
        # Con anchos en los módulos, su suma; sin anchos, los ML escritos.
        ('ML (calc.)', '=IF({c:code}{r}="","",IF(SUMIFS({x:MODULOS:#ML (calc.)},'
                       '{x:MODULOS:typology},{c:code}{r})>0,SUMIFS({x:MODULOS:#ML (calc.)},'
                       '{x:MODULOS:typology},{c:code}{r}),IFERROR(VALUE({c:ml_low}{r}),0)+'
                       'IFERROR(VALUE({c:ml_high}{r}),0)))'),
        ('Piezas (calc.)', '=IF({c:code}{r}="","",SUMIFS({x:PIEZAS:qty},{x:PIEZAS:typology},'
                           '{c:code}{r}))'),
        ('Costo de materiales (calc.)', '=IF({c:code}{r}="","",SUMIFS('
                                        '{x:BOM:#Costo de la línea (calc.)},{x:BOM:typology},'
                                        '{c:code}{r}))'),
        ('Precio (calc.)', '=IF({c:code}{r}="","",IFERROR(XLOOKUP({c:code}{r},'
                           '{x:VENTA:typology},{x:VENTA:price}),0))'),
    ],
    # El zócalo no se arma (va sin unión): no cuenta en «módulos a armar».
    'MODULOS': [
        ('A armar (calc.)', '=IF({c:code}{r}="","",IF(OR(ISNUMBER(SEARCH("ZOCALO",{c:code}{r}&" "'
                            '&{c:name}{r})),ISNUMBER(SEARCH("ZÓCALO",{c:code}{r}&" "&{c:name}{r}'
                            '))),0,1))'),
        ('ML (calc.)', '=IF(OR({c:code}{r}="",{c:width}{r}=""),"",IF(OR(%s),{c:width}{r}/1000,0))'
         % ','.join('{c:ml_group}{r}="%s"' % group for group in _ML_GROUPS_COUNTED)),
    ],
    'ARBOL': [
        # Piso con su agrupador («Torre A / Piso 3»), siempre como texto.
        ('Piso (calc.)', '=IF({c:floor}{r}="","",IF({c:group}{r}="",{c:floor}{r}&"",'
                         '{c:group}{r}&" / "&{c:floor}{r}))'),
        ('Rubro (calc.)', '=IF({c:typology}{r}="","",IFERROR(XLOOKUP({c:typology}{r},'
                          '{x:TIPOLOGIAS:code},{x:TIPOLOGIAS:family}),""))'),
        # M113-08, punto 5: módulos a armar y ML de la tipología del ambiente.
        ('Módulos (calc.)', '=IF({c:typology}{r}="","",IFERROR(XLOOKUP({c:typology}{r},'
                            '{x:TIPOLOGIAS:code},{x:TIPOLOGIAS:#Módulos a armar (calc.)}),'
                            '"Falta"))'),
        ('ML (calc.)', '=IF({c:typology}{r}="","",IFERROR(XLOOKUP({c:typology}{r},'
                       '{x:TIPOLOGIAS:code},{x:TIPOLOGIAS:#ML (calc.)}),0))'),
    ],
    'ACTIVIDADES': [
        ('Tarifa (calc.)', '=IF({c:activity}{r}="","",IFERROR(XLOOKUP({c:activity}{r},'
                           '{x:TARIFAS:activity},{x:TARIFAS:price}),0))'),
        ('Costo en la obra (calc.)', '=IF({c:activity}{r}="","",IFERROR(VALUE({c:qty}{r}),0)*'
                                     '{c:#Tarifa (calc.)}{r}*%s)' % _IN_SITE),
    ],
    'PIEZAS': [
        ('m² (calc.)', '=IF(OR({c:qty}{r}="",{c:length}{r}="",{c:width}{r}=""),"",'
                       '{c:qty}{r}*{c:length}{r}*{c:width}{r}/1000000)'),
    ],
    'BOM': [
        # Paquete 1.13, M113-06: unidad y costo del maestro, a la vista.
        ('Unidad del producto (calc.)', '=IF({c:product_code}{r}="","",IFERROR(VLOOKUP('
                                        '{c:product_code}{r},REFERENCIAS!$K$3:$L${p},2,0),""))'),
        ('Costo unitario (calc.)', '=IF({c:product_code}{r}="","",IFERROR(VLOOKUP('
                                   '{c:product_code}{r},REFERENCIAS!$K$3:$M${p},3,0),'
                                   'IF({c:cost}{r}="","",{c:cost}{r})))'),
        ('Costo de la línea (calc.)', '=IF({c:product_code}{r}="","",IFERROR({c:qty}{r}*'
                                      'VLOOKUP({c:product_code}{r},REFERENCIAS!$K$3:$M${p},3,0),'
                                      '{c:qty}{r}*{c:cost}{r}))'),
        # M113-07: costo de la línea por los ambientes de su tipología.
        ('Costo en la obra (calc.)', '=IF({c:product_code}{r}="","",IFERROR('
                                     '{c:#Costo de la línea (calc.)}{r}*%s,0))'
         % _IN_SITE),
    ],
}
# Columna «Producto» (lista dependiente) y código calculado desde ella.
PRODUCT_PICK = {'PIEZAS': ('categ', 'Producto'), 'BOM': ('categ', 'product_name')}
# Paquete 1.13, M113-06: grupo de categoría (el segundo nivel de la ruta),
# categoría (ruta corta «GRUPO / ÚLTIMO NIVEL») y producto, dependientes.
GROUP_HEADER = 'Grupo de categoría'
CATEGORY_SEPARATOR = ' / '
# Fórmulas de REFERENCIAS sobre la ruta completa de la categoría (columna N):
# tramos separados por « / », sin listas (una fila por producto).
_COUNT = '((LEN(N{r})-LEN(SUBSTITUTE(N{r}," / ","")))/3+1)'
_FIRST = first_part('N{r}', '" / "')
_SECOND = second_part('N{r}', '" / "')
_LAST = last_part('N{r}', '" / "')
REF_GROUP = '=IF(N{r}="","",IF(%s>=2,%s,%s))' % (_COUNT, _SECOND, _FIRST)
REF_LAST = '=IF(N{r}="","",%s)' % _LAST
REF_SHORT = '=IF(N{r}="","",IF(%s>=3,Q{r}&" / "&R{r},R{r}))' % _COUNT
# Marcas de la hoja (formato condicional nativo).
UNKNOWN_FILL = '#F4CCCC'
NO_COST_FILL = '#FCE5CD'


def category_parts(path):
    """(grupo, ruta corta, último nivel) de la ruta de una categoría, como
    las fórmulas de REFERENCIAS."""
    segments = [part.strip() for part in (path or '').split(CATEGORY_SEPARATOR)]
    last = segments[-1]
    group = segments[1] if len(segments) >= 2 else segments[0]
    short = '%s / %s' % (group, last) if len(segments) >= 3 else last
    return group, short, last
FIXED_LISTS = {
    ('TIPOLOGIAS', 'family'): ['Cocina', 'Closet', 'Baño', 'Lavandería', 'Ducto', 'Área común',
                               'Especial', 'Otro'],
    ('MODULOS', 'type'): ['Bajo', 'Alto', 'Cajonera', 'Campana', 'Repisero', 'Otro'],
    ('MODULOS', 'module_class'): ['Estándar', 'Especial'],
    ('MODULOS', 'join_method'): ['Tornillo', 'Tarugo', 'Mixto', 'Minifix', 'Sin unión'],
    ('MODULOS', 'ml_group'): ['Mueble bajo', 'Mueble alto', 'Mueble completo', 'Sin ML'],
    ('MUEBLES', 'ml_group'): ['Bajo', 'Alto', 'Completo', 'Otro'],
    ('TARIFAS', 'family'): ['Cocina y baño', 'Closet y cajones'],
}
LEEME = [
    'Hoja de trabajo de la oficina técnica (mobiliario)',
    '',
    'INICIO muestra el estado de la hoja, la ruta de planificación con su semáforo, los '
    'indicadores y lo que falta. FICHA resume una tipología, PROGRAMA arma el pre-plan por '
    'piso y CONTROL compara la hoja con el planificador. Las acciones están en el menú '
    'Planificación de obra.',
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
    '8. Aprobado el presupuesto por el cliente: Planificación de obra › Validar y después › '
    'Enviar al planificador. Un segundo envío no duplica nada.',
]


def sheet_ref(name):
    """Nombre de la pestaña para una fórmula (entre comillas si tiene espacios)."""
    return "'%s'" % name if ' ' in name else name


def column_of(layout, sheet, key):
    """Letra de la columna ``key`` de una pestaña; «#encabezado» es una
    columna calculada."""
    info = layout['sheets'][sheet]
    if key.startswith('#'):
        return info['calc_letters'][key[1:]]
    return info['letters'][key]


def full_column(layout, sheet, key):
    """«ARBOL!$E:$E»: la columna completa, que sigue valiendo si la hoja
    se amplía."""
    letter = column_of(layout, sheet, key)
    return '%s!$%s:$%s' % (sheet_ref(sheet), letter, letter)


def sheet_formula(layout, name, text):
    """Fórmula de la pestaña ``name`` con ``{c:clave}`` (columna de la
    misma pestaña) y ``{x:pestaña:clave}`` (columna completa de otra)."""
    text = re.sub(r'\{x:([^:}]+):([^}]+)\}',
                  lambda match: full_column(layout, match.group(1), match.group(2)), text)
    return re.sub(r'\{c:([^}]+)\}', lambda match: column_of(layout, name, match.group(1)),
                  text)


def _letter_index(letters):
    """Índice de la columna (A → 0, AA → 26)."""
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - 64
    return index - 1


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

    def _construction_spreadsheet_kind(self):
        """Las obras sin perfil llenan el maestro de muebles, como antes del
        perfil; las demás, la hoja de su perfil (paquete 1.16)."""
        self.ensure_one()
        if not self.construction_profile_id:
            return 'furniture'
        return super()._construction_spreadsheet_kind()

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
        if name in PRODUCT_PICK:
            # M113-06: el grupo antes de la categoría (no es una clave del
            # importador: la hoja lo usa para la lista de categorías).
            index = next(i for i, (key, _h) in enumerate(columns) if key == 'categ')
            columns.insert(index, ('categ_group', GROUP_HEADER))
        return columns

    def _construction_reference_counts(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        products = self.env['product.product'].search_count(
            [('type', '=', 'consu'), ('company_id', 'in', (company.id, False))])
        categories = self.env['product.category'].search_count(
            [('child_id', '=', False), ('name', 'not in', EXCLUDED_CATEGORIES)])
        return min(max(products, 1), MAX_PRODUCTS), max(categories, 1)

    def _construction_material_root(self):
        """Ruta de la categoría raíz de materiales de la hoja (Ajustes)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        return company.construction_sheet_material_categ_id.complete_name or ''

    def _construction_material_categories(self):
        """Grupos y categorías cortas con productos (dentro de la raíz de
        Ajustes) y el mayor número de productos de una categoría: el tamaño de
        las listas de _LISTAS (M113-06)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        domain = [('type', '=', 'consu'), ('company_id', 'in', (company.id, False))]
        root = company.construction_sheet_material_categ_id
        if root:
            domain.append(('categ_id', 'child_of', root.id))
        groups, shorts = {}, {}
        for categ, count in self.env['product.product']._read_group(
                domain, ['categ_id'], ['__count']):
            if not categ:
                continue
            group, short, last = category_parts(categ.complete_name)
            if last in EXCLUDED_CATEGORIES:
                continue
            groups.setdefault(group, set()).add(short)
            shorts[short] = shorts.get(short, 0) + count
        return groups, shorts

    # Pestañas con lista dependiente de materiales y su orden en _LISTAS:
    # cada fila de datos usa 4 filas seguidas (categoría y producto de PIEZAS
    # y de BOM), así una hoja ampliada sigue el mismo orden (M113-04).
    HELPER_KINDS = (('PIEZAS', 'categ'), ('PIEZAS', 'prod'), ('BOM', 'categ'), ('BOM', 'prod'))

    def _construction_sheet_layout(self):
        """Lo que no depende de las filas: columnas y letras de cada pestaña,
        tamaño del maestro de productos y de las listas de _LISTAS."""
        self.ensure_one()
        n_products, _n_categories = self._construction_reference_counts()
        groups, shorts = self._construction_material_categories()
        n_groups = len(groups) + 5
        n_shorts = len(shorts) + 20
        width = max([60] + [len(c) for c in groups.values()] + list(shorts.values())) + 5
        sheets = {}
        for name in SHEETS:
            columns = self._construction_sheet_columns(name)
            calculated = CALCULATED.get(name, [])
            sheets[name] = {
                'columns': columns,
                'calculated': calculated,
                'letters': {key: _col(i) for i, (key, _h) in enumerate(columns)},
                'calc_letters': {header: _col(len(columns) + i)
                                 for i, (header, _f) in enumerate(calculated)},
                'headers': [h for _k, h in columns] + [h for h, _f in calculated],
            }
        return {
            'sheets': sheets, 'last_product': n_products + 2, 'n_products': n_products,
            'n_groups': n_groups, 'n_shorts': n_shorts, 'width': width,
            'last_col': _col(width), 'list_base': n_groups + n_shorts,
            'stage_count': len(self.env['construction.stage']._offered_stages(self)),
        }

    def _construction_helper_row(self, layout, name, kind, row):
        """Fila de _LISTAS con la lista de ``kind`` de la fila ``row``."""
        return layout['list_base'] + (row - 2) * len(self.HELPER_KINDS) + \
            self.HELPER_KINDS.index((name, kind)) + 1

    def _construction_row_parts(self, layout, first, last):
        """Celdas, reglas de validación y formato condicional de las filas
        ``first`` a ``last`` (números de fila de la hoja) de cada pestaña del
        maestro y sus filas de _LISTAS: lo usa la plantilla y la ampliación de
        una hoja ya abierta (M113-04/05).

        :return: ``{pestaña: {'cells': {ref: texto}, 'rules': [...],
            'conditional': [...]}}``; las reglas llevan ``zone`` (top, bottom,
            left, right desde 0) además de ``ranges``.
        """
        self.ensure_one()
        last_product = layout['last_product']
        result = {name: {'cells': {}, 'rules': [], 'conditional': []} for name in SHEETS}
        result[LISTS_SHEET] = {'cells': {}, 'rules': [], 'conditional': []}
        if last < first:
            return result

        def zone(letter, top, bottom):
            col = _letter_index(letter)
            return {'top': top - 1, 'bottom': bottom - 1, 'left': col, 'right': col}

        for name, info in layout['sheets'].items():
            part = result[name]
            cells = part['cells']
            letters = info['letters']
            for header, formula in info['calculated']:
                col = info['calc_letters'][header]
                template = sheet_formula(layout, name, formula)
                for row in range(first, last + 1):
                    cells['%s%s' % (col, row)] = template.replace('{r}', str(row)).replace(
                        '{p}', str(last_product))
            for (sheet, key), values in FIXED_LISTS.items():
                if sheet == name and key in letters:
                    part['rules'].append({
                        'id': '%s_%s_%s' % (name, key, first), 'isBlocking': False,
                        'zone': zone(letters[key], first, last),
                        'ranges': ['%s%s:%s%s' % (letters[key], first, letters[key], last)],
                        'criterion': {'type': 'isValueInList', 'values': values,
                                      'displayStyle': 'arrow'}})
            if 'stage' in letters and layout['stage_count']:
                part['rules'].append({
                    'id': '%s_stage_%s' % (name, first), 'isBlocking': False,
                    'zone': zone(letters['stage'], first, last),
                    'ranges': ['%s%s:%s%s' % (letters['stage'], first, letters['stage'], last)],
                    'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                                  'values': ['%s!$T$3:$T$%s' % (
                                      REFERENCE_SHEET, layout['stage_count'] + 2)]}})
            if name not in PRODUCT_PICK:
                continue
            pick = letters['product_name']
            code = letters['product_code']
            for row in range(first, last + 1):
                # Código calculado desde «nombre · unidad · código».
                cells['%s%s' % (code, row)] = CODE_FROM_PICK.replace(
                    '{p}', pick).replace('{r}', str(row))
            # M113-06: grupo › categoría › producto, con validación nativa
            # (filtra al escribir). Cada fila apunta a su fila de _LISTAS.
            group = letters['categ_group']
            part['rules'].append({
                'id': '%s_group_%s' % (name, first), 'isBlocking': False,
                'zone': zone(group, first, last),
                'ranges': ['%s%s:%s%s' % (group, first, group, last)],
                'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                              'values': ['%s!$A$1:$A$%s' % (LISTS_SHEET, layout['n_groups'])]}})
            for row in range(first, last + 1):
                for kind, column in (('categ', letters['categ']), ('prod', pick)):
                    helper = self._construction_helper_row(layout, name, kind, row)
                    part['rules'].append({
                        'id': '%s_%s_%s' % (name, kind, row), 'isBlocking': False,
                        'zone': zone(column, row, row), 'ranges': ['%s%s' % (column, row)],
                        'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                                      'values': ['%s!$A$%s:$%s$%s' % (
                                          LISTS_SHEET, helper, layout['last_col'], helper)]}})
            # Marcas: rojo el código que no está en el maestro ni en PRODUCTOS
            # NUEVOS; ámbar el producto con costo 0.
            code_range = '%s%s:%s%s' % (code, first, code, last)
            part['conditional'].append({
                'id': '%s_unknown_%s' % (name, first), 'ranges': [code_range], 'stopIfTrue': True,
                'rule': {'type': 'CellIsRule', 'operator': 'customFormula', 'values': [
                    '=AND({c}{f}<>"",COUNTIF({ref}!$K$3:$K${p},{c}{f})=0,COUNTIF('
                    "'PRODUCTOS NUEVOS'!$A$2:$A${n},{c}{f})=0)".format(
                        c=code, f=first, ref=REFERENCE_SHEET, p=last_product, n=last)],
                    'style': {'fillColor': UNKNOWN_FILL}}})
            if 'Costo unitario (calc.)' in info['calc_letters']:
                unit_cost = info['calc_letters']['Costo unitario (calc.)']
                part['conditional'].append({
                    'id': '%s_no_cost_%s' % (name, first), 'ranges': [code_range],
                    'stopIfTrue': False,
                    'rule': {'type': 'CellIsRule', 'operator': 'customFormula', 'values': [
                        '=AND({c}{f}<>"",{u}{f}<>"",{u}{f}=0)'.format(
                            c=code, f=first, u=unit_cost)],
                        'style': {'fillColor': NO_COST_FILL}}})
        # _LISTAS: las filas de lista de cada fila de datos.
        n_groups, n_shorts = layout['n_groups'], layout['n_shorts']
        groups_zone = '$B$1:$%s$%s' % (layout['last_col'], n_groups)
        group_names = '$A$1:$A$%s' % n_groups
        shorts_zone = '$B$%s:$%s$%s' % (n_groups + 1, layout['last_col'], n_groups + n_shorts)
        short_names = '$A$%s:$A$%s' % (n_groups + 1, n_groups + n_shorts)
        list_cells = result[LISTS_SHEET]['cells']
        for name in PRODUCT_PICK:
            letters = layout['sheets'][name]['letters']
            for row in range(first, last + 1):
                # Sin grupo: todas las categorías; con grupo: las suyas.
                list_cells['A%s' % self._construction_helper_row(layout, name, 'categ', row)] = (
                    '=IF({s}!{g}{r}="",IFERROR(TRANSPOSE({ref}!$W$3:$W${n}),""),IFERROR(INDEX('
                    '{zone},MATCH({s}!{g}{r},{names},0),0),""))').format(
                    s=name, g=letters['categ_group'], r=row, ref=REFERENCE_SHEET,
                    n=n_shorts + 2, zone=groups_zone, names=group_names)
                list_cells['A%s' % self._construction_helper_row(layout, name, 'prod', row)] = (
                    '=IF({s}!{c}{r}="","",IFERROR(INDEX({zone},MATCH({s}!{c}{r},{names},0),0),'
                    '""))').format(s=name, c=letters['categ'], r=row, zone=shorts_zone,
                                   names=short_names)
        return result

    def _construction_summary(self, layout, rows, sheet_ids):
        """RESUMEN: tablas dinámicas sobre la propia hoja y sus fórmulas, para
        ``rows`` filas de datos. Las filas vacías del rango quedan en el grupo
        nulo, que va al final con el orden ascendente: la fórmula muestra solo
        las filas con dato."""
        cells, styles, pivots = {}, {}, {}
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
            info = layout['sheets'][sheet]
            by_key = dict(info['columns'])
            measure_name = by_key.get(measure, measure)
            pivots[pivot_id] = {
                'type': 'SPREADSHEET', 'name': title, 'formulaId': pivot_id,
                'dataSet': {'sheetId': sheet_ids.get(sheet), 'zone': {
                    'top': 0, 'bottom': rows, 'left': 0, 'right': len(info['headers']) - 1}},
                'rows': [{'fieldName': by_key[row_key], 'order': 'asc'}],
                'columns': [{'fieldName': by_key[col_key], 'order': 'asc'}] if col_key else [],
                'measures': [{'id': '%s:%s' % (measure_name, aggregator),
                              'fieldName': measure_name, 'aggregator': aggregator}],
            }
            letter = info['letters'].get(row_key, 'A')
            data_range = '%s!%s2:%s%s' % (sheet, letter, letter, rows + 1)
            count_rows = 'IFERROR(ROWS(UNIQUE(FILTER(%s,%s<>""))),0)' % (data_range, data_range)
            formula = '=PIVOT(%s,%s' % (pivot_id, count_rows)
            if col_key:
                col_letter = info['letters'][col_key]
                col_range = '%s!%s2:%s%s' % (sheet, col_letter, col_letter, rows + 1)
                formula += ',TRUE,TRUE,IFERROR(ROWS(UNIQUE(FILTER(%s,%s<>""))),0)' % (
                    col_range, col_range)
            cells[anchor] = title
            styles[anchor] = TITLE_STYLE
            column, line = anchor[0], int(anchor[1:])
            cells['%s%s' % (column, line + 1)] = formula + ')'
        return cells, styles, pivots

    def _construction_spreadsheet_data(self, rows=None):
        """Hoja de trabajo con la estructura del piloto (M18-22)."""
        self.ensure_one()
        rows = max(rows or self.construction_spreadsheet_rows or DEFAULT_ROWS, 10)
        layout = self._construction_sheet_layout()
        last_product = layout['last_product']
        n_products = layout['n_products']
        # Las etapas del perfil de la obra (paquete 1.16, M116-01).
        stage_labels = [stage._label() for stage in
                        self.env['construction.stage']._offered_stages(self)]
        parts = self._construction_row_parts(layout, 2, rows + 1)
        sheets = []
        sheet_ids = {name: 'sheet%s' % index
                     for index, name in enumerate(layout['sheets'], start=1)}
        # Paquete 1.13, M113-07 a 11: INICIO (la hoja abre en ella), FICHA,
        # PROGRAMA, CONTROL y ERRORES.
        sheet_ids.update({name: 'sheet_%s' % name.lower() for name in (
            'INICIO', 'FICHA', 'PROGRAMA', 'CONTROL', 'ERRORES')})
        planning = self._construction_planning_sheets(layout, rows, sheet_ids, stage_labels)
        formats = {}

        def add_planning(name):
            sheet = dict(planning[name], id=sheet_ids[name])
            sheet['formats'] = {
                ref: formats.setdefault(text, len(formats) + 1)
                for ref, text in sheet.pop('formats', {}).items()}
            sheets.append(sheet)

        add_planning('INICIO')

        # LEEME
        sheets.append({
            'id': 'sheet_leeme', 'name': 'LEEME', 'colNumber': 4, 'rowNumber': 40,
            'cells': {'A%s' % (i + 1): text for i, text in enumerate(LEEME) if text},
            'styles': {'A1': TITLE_STYLE}, 'cols': {'0': {'size': 900}},
        })
        summary = {'id': 'sheet_resumen', 'name': 'RESUMEN', 'colNumber': 30,
                   'rowNumber': 400, 'cells': {}, 'styles': {}}
        sheets.append(summary)

        # Pestañas del maestro.
        key_columns = {}
        for index, (name, info) in enumerate(layout['sheets'].items(), start=1):
            headers = info['headers']
            cells = {'%s1' % _col(i): header for i, header in enumerate(headers)}
            styles = {'%s1' % _col(i): DATA_STYLE for i in range(len(info['columns']))}
            for letter in info['calc_letters'].values():
                styles['%s1' % letter] = CALC_STYLE
            if name in PRODUCT_PICK:
                styles['%s1' % info['letters']['product_code']] = CALC_STYLE
            cells.update(parts[name]['cells'])
            key_columns[name] = [(key, i) for i, (key, _h) in enumerate(info['columns'])]
            sheet_id = sheet_ids[name]
            sheets.append({
                'id': sheet_id, 'name': name, 'colNumber': max(26, len(headers)),
                'rowNumber': rows + 50, 'cells': cells, 'styles': styles,
                'cols': {str(i): {'size': max(110, 9 * len(header))}
                         for i, header in enumerate(headers)},
                'panes': {'xSplit': 0, 'ySplit': 1},
                'dataValidationRules': [{k: v for k, v in rule.items() if k != 'zone'}
                                        for rule in parts[name]['rules']],
                'conditionalFormats': parts[name]['conditional'],
            })

        sheets.append(self._construction_work_materials_sheet(last_product))

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
        # Categoría de cada producto (M113-06): ruta corta (O), grupo (Q),
        # último nivel (R) y si está dentro de la raíz de materiales (S).
        root = self._construction_material_root()
        excluded = ','.join('R{r}<>"%s"' % name for name in EXCLUDED_CATEGORIES)
        if root:
            in_root = 'OR(N{r}="%s",LEFT(N{r},%s)="%s / ")' % (root, len(root) + 3, root)
        else:
            in_root = 'TRUE'
        for column, title, formula in (
                ('O', 'Categoría', REF_SHORT), ('Q', GROUP_HEADER, REF_GROUP),
                ('R', 'Último nivel', REF_LAST),
                ('S', 'Material', '=IF(N{r}="",0,IF(AND(%s,%s),1,0))' % (in_root, excluded))):
            cells['%s2' % column] = title
            styles['%s2' % column] = HEADER_STYLE
            for row in range(3, last_product + 1):
                cells['%s%s' % (column, row)] = formula.replace('{r}', str(row))
        # Producto para elegir: «nombre · unidad · código» (M116-09).
        cells['P2'] = 'Para elegir'
        styles['P2'] = HEADER_STYLE
        for row in range(3, last_product + 1):
            cells['P%s' % row] = (
                '=IF(K{r}="","",IFERROR(MID(J{r},FIND("] ",J{r})+2,500),J{r})&"{s}"&L{r}&"{s}"&K{r})'
                .replace('{r}', str(row)).replace('{s}', PICK_SEPARATOR))
        cells['T1'] = 'Sub etapas'
        styles['T1'] = TITLE_STYLE
        for row, label in enumerate(stage_labels, start=3):
            cells['T%s' % row] = label
        cells['V2'] = GROUP_HEADER
        cells['V3'] = '=IFERROR(SORT(UNIQUE(FILTER($Q$3:$Q$%s,$S$3:$S$%s=1))),"")' % (
            last_product, last_product)
        cells['W2'] = 'Categoría'
        cells['W3'] = '=IFERROR(SORT(UNIQUE(FILTER($O$3:$O$%s,$S$3:$S$%s=1))),"")' % (
            last_product, last_product)
        styles['V2'] = styles['W2'] = HEADER_STYLE
        sheets.append({
            'id': 'sheet_ref', 'name': REFERENCE_SHEET, 'colNumber': 26,
            'rowNumber': max(last_product, 302) + 2, 'cells': cells, 'styles': styles,
        })

        # _LISTAS (oculta, M113-06): una fila por grupo y por categoría con su
        # FILTER (menos de 100 aunque la hoja tenga 8 000 filas) y, por fila de
        # datos, INDEX/MATCH sobre ellas.
        ref = REFERENCE_SHEET
        n_groups, n_shorts = layout['n_groups'], layout['n_shorts']
        list_cells = {}
        for index in range(1, n_groups + 1):
            list_cells['A%s' % index] = '=IFERROR(INDEX(%s!$V$3:$V$%s,%s),"")' % (
                ref, n_groups + 2, index)
            list_cells['B%s' % index] = (
                '=IF(A{i}="","",IFERROR(TRANSPOSE(SORT(UNIQUE(FILTER({ref}!$O$3:$O${p},'
                '{ref}!$Q$3:$Q${p}=A{i},{ref}!$S$3:$S${p}=1)))),""))').format(
                i=index, ref=ref, p=last_product)
        for index in range(1, n_shorts + 1):
            row = n_groups + index
            list_cells['A%s' % row] = '=IFERROR(INDEX(%s!$W$3:$W$%s,%s),"")' % (
                ref, n_shorts + 2, index)
            # Los materiales de la obra de esa categoría primero (M113-06,
            # punto 7); sin ellos, la misma lista dos veces y UNIQUE la deja
            # en una.
            catalog = 'FILTER({ref}!$P$3:$P${p},{ref}!$O$3:$O${p}=A{i},{ref}!$S$3:$S${p}=1)'
            list_cells['B%s' % row] = (
                '=IF(A{i}="","",IFERROR(TRANSPOSE(UNIQUE(VSTACK(IFERROR(FILTER({w}!$A$2:$A${m},'
                '{w}!$B$2:$B${m}=A{i}),%s),%s))),""))' % (catalog, catalog)).format(
                i=row, ref=ref, p=last_product, w=sheet_ref(WORK_MATERIALS_SHEET),
                m=WORK_MATERIALS_ROWS + 1)
        list_cells.update(parts[LISTS_SHEET]['cells'])
        sheets.append({'id': 'sheet_listas', 'name': LISTS_SHEET,
                       'colNumber': layout['width'] + 2,
                       'rowNumber': self._construction_helper_row(
                           layout, 'BOM', 'prod', rows + 1) + 10,
                       'cells': list_cells, 'isVisible': False})

        summary_cells, summary_styles, pivots = self._construction_summary(
            layout, rows, sheet_ids)
        summary['cells'].update(summary_cells)
        summary['styles'].update(summary_styles)
        for name in ('FICHA', 'PROGRAMA', 'CONTROL', 'ERRORES'):
            add_planning(name)

        # Clave interna de cada columna del maestro (M116-09).
        sheets.append(keys_sheet(key_columns, header_style=HEADER_STYLE))
        settings = self.env['documents.document']._empty_spreadsheet_data().get('settings', {})
        return {
            'version': SPREADSHEET_VERSION,
            'sheets': sheets,
            'styles': STYLES,
            'formats': {str(format_id): text for text, format_id in formats.items()},
            'settings': settings,
            'lists': lists,
            'listNextId': len(reference_lists) + 1,
            'pivots': pivots,
            'pivotNextId': len(pivots) + 1,
            'revisionId': 'START_REVISION',
        }

    def _construction_work_materials_sheet(self, last_product):
        """MATERIALES OBRA (M113-06, punto 7): los materiales base de la obra,
        elegidos de todo el maestro, con su categoría y su código."""
        cells = {'A1': 'Material', 'B1': 'Categoría (calc.)', 'C1': 'Código (calc.)',
                 'E1': 'Los materiales de esta lista van primero en la lista de su categoría '
                       '(BOM y PIEZAS). «Reemplazar un material…» del panel Planificación '
                       'cambia uno por otro en la hoja.'}
        for row in range(2, WORK_MATERIALS_ROWS + 2):
            cells['C%s' % row] = CODE_FROM_PICK.replace('{p}', 'A').replace('{r}', str(row))
            cells['B%s' % row] = ('=IF(C{r}="","",IFERROR(XLOOKUP(C{r},{ref}!$K$3:$K${p},'
                                  '{ref}!$O$3:$O${p}),""))').format(
                r=row, ref=REFERENCE_SHEET, p=last_product)
        return {
            'id': 'sheet_materiales_obra', 'name': WORK_MATERIALS_SHEET, 'colNumber': 8,
            'rowNumber': WORK_MATERIALS_ROWS + 10, 'cells': cells,
            'styles': {'A1': DATA_STYLE, 'B1': CALC_STYLE, 'C1': CALC_STYLE},
            'cols': {'0': {'size': 380}, '1': {'size': 220}, '2': {'size': 120}},
            'panes': {'xSplit': 0, 'ySplit': 1},
            'dataValidationRules': [{
                'id': 'work_materials', 'isBlocking': False,
                'ranges': ['A2:A%s' % (WORK_MATERIALS_ROWS + 1)],
                'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                              'values': ['%s!$P$3:$P$%s' % (REFERENCE_SHEET, last_product)]}}],
        }

    def _construction_spreadsheet_template(self, kind):
        if kind == 'furniture':
            return self._construction_spreadsheet_data(), self.env._(
                'Maestro de planificación · %s', self.name)
        return super()._construction_spreadsheet_template(kind)
