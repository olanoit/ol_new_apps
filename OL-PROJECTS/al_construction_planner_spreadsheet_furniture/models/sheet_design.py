# -*- coding: utf-8 -*-
"""Diseño de las hojas de trabajo (paquete 1.17, M117-01, M117-02 y M117-23).

Lo que dicen las fichas del Anexo A del requerimiento sobre cada pestaña: orden
de las columnas en pantalla, anchos, formatos, columnas fijas, color y tabla. Los
datos van aparte de las fórmulas para que la plantilla, la ampliación de filas y
«Actualizar a la plantilla vigente» apliquen el mismo diseño.

El orden en pantalla es independiente del libro de carga (``SHEETS``): la hoja
lee sus columnas por ``_CLAVES``.
"""

# Paleta. El amarillo es lo que llena el analista; el gris, lo que calcula la hoja.
HEADER_DATA_COLOR = '#FFDC00'
HEADER_CALC_COLOR = '#E6E2DD'
CELL_DATA_COLOR = '#FFF7CC'
CELL_CALC_COLOR = '#F4F2EF'
BORDER_COLOR = '#DDD8D1'
HEADER_LINE_COLOR = '#221F20'
TEXT_COLOR = '#221F20'
HEADER_CALC_TEXT = '#4A4441'
CELL_CALC_TEXT = '#55514F'
OK_FILL, OK_TEXT = '#E3F4EC', '#1D9E75'
ERROR_FILL, ERROR_TEXT = '#F6E1E4', '#B23A48'
WARNING_FILL, WARNING_TEXT = '#FCE5CD', '#7A6200'

HEADER_HEIGHT = 56
TABLE_STYLE_ID = 'construction_worksheet'
TABLE_STYLES = {TABLE_STYLE_ID: {'displayName': 'Hoja de trabajo',
                                 'templateName': 'lightAllBorders',
                                 'primaryColor': BORDER_COLOR}}

_HEADER = {'bold': True, 'wrapping': 'wrap', 'verticalAlign': 'middle'}
HEADER_DATA = dict(_HEADER, fillColor=HEADER_DATA_COLOR, textColor=TEXT_COLOR)
HEADER_CALC = dict(_HEADER, fillColor=HEADER_CALC_COLOR, textColor=HEADER_CALC_TEXT)
CELL_DATA = {'fillColor': CELL_DATA_COLOR, 'fontSize': 10}
CELL_CALC = {'fillColor': CELL_CALC_COLOR, 'textColor': CELL_CALC_TEXT, 'fontSize': 10}
HEADER_BORDER = {'bottom': {'style': 'medium', 'color': HEADER_LINE_COLOR}}

# Formatos. Los porcentajes del maestro se escriben como 30 (el envío los lee
# así), no como 0.30: con el formato 0% se verían como 3000 %.
MONEY = '#,##0.00'
INTEGER = '0'
QUANTITY = '0.0000'
PERCENT = '0"%"'
DATE = 'dd/mm/yyyy'

# Colores de pestaña.
TAB_GENERAL = '#221F20'
TAB_PLANNING_DATA = '#1D9E75'
TAB_ANALYSIS = '#4A4441'
TAB_SYSTEM = '#DDD8D1'

# Orden de pestañas de la hoja de planificación (M117-16, punto 8). Lo demás
# (las pestañas propias del usuario) va al final.
SHEET_ORDER = (
    'INICIO', 'LEEME', 'OBRA', 'TIPOLOGIAS', 'MUEBLES', 'MODULOS', 'ACTIVIDADES', 'BOM', 'PIEZAS',
    'PRODUCTOS NUEVOS', 'TARIFAS', 'ARBOL', 'VARIANTES', 'ETO', 'CONTRATOS', 'HITOS', 'VENTA',
    'MO PROPIA', 'CATALOGO', 'MATERIALES OBRA', 'FICHA', 'PROGRAMA', 'CONTROL', 'RESUMEN',
    'ERRORES', 'REFERENCIAS', '_LISTAS', '_CLAVES',
)
TAB_COLORS = {
    'INICIO': TAB_GENERAL, 'LEEME': TAB_GENERAL, 'OBRA': TAB_GENERAL,
    'FICHA': TAB_ANALYSIS, 'PROGRAMA': TAB_ANALYSIS, 'CONTROL': TAB_ANALYSIS,
    'RESUMEN': TAB_ANALYSIS,
    'ERRORES': TAB_SYSTEM, 'REFERENCIAS': TAB_SYSTEM, '_LISTAS': TAB_SYSTEM,
    '_CLAVES': TAB_SYSTEM,
}
PLANNING_DATA_SHEETS = SHEET_ORDER[SHEET_ORDER.index('TIPOLOGIAS'):
                                   SHEET_ORDER.index('MATERIALES OBRA') + 1]
TAB_COLORS.update({name: TAB_PLANNING_DATA for name in PLANNING_DATA_SHEETS})

# Orden en pantalla de las columnas de BOM y PIEZAS (M117-02): de izquierda a
# derecha como se llena la fila. El código es calculado: va con las calculadas.
COLUMN_ORDER = {
    'BOM': ('typology', 'module', 'categ_group', 'categ', 'product_name', 'qty', 'stage', 'uom',
            'cost', 'product_code'),
    'PIEZAS': ('typology', 'module', 'categ_group', 'categ', 'product_name', 'qty', 'length',
               'width', 'piece_type', 'color', 'edges', 'product_code'),
}

# Pestaña → columnas fijas, si lleva filtro, y {encabezado: (ancho, formato)}.
# Sin tabla: OBRA (página de datos). Sin filtro: ARBOL, porque sus grupos por piso
# se desarmarían al filtrar u ordenar.
SHEET_DESIGN = {
    'OBRA': {'freeze': 0, 'table': False, 'columns': {
        'Dato': (220, None), 'Valor': (320, None)}},
    'TIPOLOGIAS': {'freeze': 2, 'columns': {
        'Código': (105, None), 'Nombre': (170, None), 'Familia': (120, None),
        'Producto terminado': (200, None), 'ML bajo': (105, MONEY), 'ML alto': (105, MONEY),
        'Variante de': (120, None), 'Otros nombres': (170, None),
        'En la obra (calc.)': (105, INTEGER), 'Módulos (calc.)': (105, INTEGER),
        'Módulos a armar (calc.)': (105, INTEGER), 'ML (calc.)': (105, MONEY),
        'Piezas (calc.)': (105, INTEGER), 'Costo de materiales (calc.)': (105, MONEY),
        'Precio (calc.)': (105, MONEY)}},
    'MUEBLES': {'freeze': 2, 'columns': {
        'Tipología': (120, None), 'Mueble': (195, None), 'Grupo': (120, None),
        'Metros lineales': (105, MONEY)}},
    'MODULOS': {'freeze': 3, 'columns': {
        'Tipología': (120, None), 'Orden': (105, INTEGER), 'Código del módulo': (105, None),
        'Tipo': (125, None), 'Ancho (mm)': (105, INTEGER), 'Grupo ML': (130, None),
        'Actividad de armado': (125, None), 'Mueble': (135, None), 'Nombre': (170, None),
        'Tipo de módulo': (120, None), 'Método de unión': (120, None),
        'A armar (calc.)': (105, INTEGER), 'ML (calc.)': (105, MONEY)}},
    'ACTIVIDADES': {'freeze': 2, 'columns': {
        'Tipología': (120, None), 'Actividad': (135, None),
        'Cantidad por ambiente': (105, MONEY), 'Tarifa (calc.)': (105, MONEY),
        'Costo en la obra (calc.)': (105, MONEY)}},
    'BOM': {'freeze': 5, 'columns': {
        'Tipología': (120, None), 'Módulo': (120, None), 'Grupo de categoría': (120, None),
        'Categoría': (185, None), 'Producto': (395, None), 'Cantidad': (105, QUANTITY),
        'Etapa de consumo': (155, None), 'Unidad': (110, None), 'Costo unitario': (105, MONEY),
        'Código del producto': (105, None), 'Unidad del producto (calc.)': (110, None),
        'Costo unitario (calc.)': (105, MONEY), 'Costo de la línea (calc.)': (105, MONEY),
        'Costo en la obra (calc.)': (105, MONEY), 'Etapa usada (calc.)': (140, None)}},
    'PIEZAS': {'freeze': 5, 'columns': {
        'Tipología': (120, None), 'Módulo': (120, None), 'Grupo de categoría': (120, None),
        'Categoría': (175, None), 'Producto': (345, None), 'Cantidad': (105, INTEGER),
        'Largo (mm)': (105, INTEGER), 'Ancho (mm)': (105, INTEGER),
        'Tipo de pieza': (120, None), 'Color': (105, None), 'Cantos': (120, None),
        'Código del producto': (105, None), 'm² (calc.)': (105, MONEY)}},
    'PRODUCTOS NUEVOS': {'freeze': 1, 'columns': {
        'Código provisional': (105, None), 'Nombre': (300, None), 'Unidad': (120, None),
        'Categoría': (215, None), 'Costo estimado': (105, MONEY)}},
    'TARIFAS': {'freeze': 1, 'columns': {
        'Actividad': (125, None), 'Tarifa': (105, MONEY), 'Contratista': (195, None),
        'Retención %': (105, PERCENT), 'Vigente desde': (105, DATE),
        'Vigente hasta': (105, DATE), 'Familia': (135, None)}},
    'ARBOL': {'freeze': 4, 'filter': False, 'columns': {
        'Agrupador': (105, None), 'Piso': (105, None), 'Departamento': (105, None),
        'Ambiente': (170, None), 'Tipología': (120, None), 'Tipo de unidad': (125, None),
        'Piso (calc.)': (105, None), 'Rubro (calc.)': (105, None),
        'Módulos (calc.)': (105, INTEGER), 'ML (calc.)': (105, MONEY)}},
    'VARIANTES': {'freeze': 4, 'columns': {
        'Agrupador': (105, None), 'Piso': (105, None), 'Departamento': (105, None),
        'Ambiente': (160, None), 'Tipo': (120, None), 'Código del producto': (105, None),
        'Reemplazar por': (105, None), 'Cantidad por ambiente': (105, MONEY),
        'Nota': (200, None)}},
    'ETO': {'freeze': 4, 'columns': {
        'Agrupador': (105, None), 'Piso': (105, None), 'Departamento': (105, None),
        'Ambiente': (160, None), 'Código del módulo': (105, None), 'Tipo': (125, None),
        'Ancho (mm)': (105, INTEGER), 'Grupo ML': (130, None)}},
    'CONTRATOS': {'freeze': 1, 'columns': {
        'Contrato': (200, None), 'Cliente': (235, None), 'Adelanto %': (105, PERCENT),
        'Fondo de garantía %': (105, PERCENT), 'Plantilla de hitos': (175, None)}},
    'HITOS': {'freeze': 1, 'columns': {
        'Plantilla': (160, None), 'Hito': (200, None), '%': (105, PERCENT),
        'Etapa': (165, None)}},
    'VENTA': {'freeze': 2, 'columns': {
        'Contrato': (215, None), 'Tipología': (120, None),
        'Precio por ambiente': (110, MONEY)}},
    'MO PROPIA': {'freeze': 1, 'columns': {
        'Rol': (130, None), 'Categoría': (120, None), 'Sub etapa': (165, None),
        'Jornal': (105, MONEY), 'Rendimiento': (105, MONEY), 'Actividad': (125, None)}},
    'CATALOGO': {'freeze': 1, 'columns': {
        'Código': (110, None), 'Nombre': (220, None), 'Etapa': (155, None),
        'Unidad': (105, None), 'Se mide por': (120, None), 'Grupo ML': (130, None),
        'Tarifa base': (105, MONEY)}},
}
MIN_WIDTH = 105


def column_width(name, header):
    """Ancho de la columna ``header`` en la pestaña ``name`` (M117-23, punto 5)."""
    design = SHEET_DESIGN.get(name, {}).get('columns', {})
    return design.get(header, (max(MIN_WIDTH, 9 * len(header)), None))[0]


def column_format(name, header):
    return SHEET_DESIGN.get(name, {}).get('columns', {}).get(header, (0, None))[1]


def table_config(name):
    """Tabla nativa de la pestaña: sin filas alternadas y con filtro salvo que
    la ficha lo quite; ``None`` si la pestaña no lleva tabla."""
    design = SHEET_DESIGN.get(name, {})
    if not design.get('table', True):
        return None
    return {'hasFilters': design.get('filter', True), 'totalRow': False, 'firstColumn': False,
            'lastColumn': False, 'numberOfHeaders': 1, 'bandedRows': False,
            'bandedColumns': False, 'automaticAutofill': True, 'styleId': TABLE_STYLE_ID}
