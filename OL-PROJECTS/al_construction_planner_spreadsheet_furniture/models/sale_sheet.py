# -*- coding: utf-8 -*-
"""Hoja de venta de mobiliario (paquete 1.17, M117-15 a M117-21).

Nace con la cotización y no necesita obra. Sigue el orden de trabajo del analista
de presupuestos: edificio, acabados, precios, metrado y resumen. Todo número de
negocio se lee de PARAMETROS por su clave. Sus pestañas no entran en el libro de
carga del planificador (``SHEETS``): tienen su propio registro.

Python puro, salvo lo que recibe del modelo: lo usan la plantilla, la validación
y la importación.
"""
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_keys import keys_sheet

from . import sheet_design as design
from .construction_sheet_parameter import PARAMETERS_SHEET, parameter_formula as param

SALE_ROWS = 300
OBRA_SHEET = 'OBRA'
BUILDING_SHEET = 'EDIFICIO'
FINISHES_SHEET = 'ACABADOS'
RATES_SHEET = 'TARIFARIO'
PRICES_SHEET = 'PRECIOS'
MEASURE_SHEET = 'METRADO'
SUMMARY_SHEET = 'RESUMEN VENTA'
START_SHEET = 'INICIO'
README_SHEET = 'LEEME'
ERRORS_SHEET = 'ERRORES'
REFERENCE_SHEET = 'REFERENCIAS'
LISTS_SHEET = '_LISTAS'
SALE_SHEET_ORDER = (START_SHEET, README_SHEET, OBRA_SHEET, PARAMETERS_SHEET, BUILDING_SHEET,
                    FINISHES_SHEET, RATES_SHEET, PRICES_SHEET, MEASURE_SHEET, SUMMARY_SHEET,
                    ERRORS_SHEET, REFERENCE_SHEET, LISTS_SHEET, '_CLAVES')
SALE_TAB_COLORS = {
    START_SHEET: design.TAB_GENERAL, README_SHEET: design.TAB_GENERAL,
    OBRA_SHEET: design.TAB_GENERAL, PARAMETERS_SHEET: design.TAB_PARAMETERS,
    BUILDING_SHEET: design.HEADER_DATA_COLOR, FINISHES_SHEET: design.HEADER_DATA_COLOR,
    RATES_SHEET: design.HEADER_DATA_COLOR, PRICES_SHEET: design.HEADER_DATA_COLOR,
    MEASURE_SHEET: design.HEADER_DATA_COLOR, SUMMARY_SHEET: design.HEADER_DATA_COLOR,
    ERRORS_SHEET: design.TAB_SYSTEM, REFERENCE_SHEET: design.TAB_SYSTEM,
    LISTS_SHEET: design.TAB_SYSTEM, '_CLAVES': design.TAB_SYSTEM,
}
# Filas fijas de OBRA (M117-21, punto 2).
OBRA_ROWS = ('Proyecto', 'Código de cotización', 'Versión de la cotización', 'Fecha de cotización',
             'Cliente', 'Solicitante', 'Ubicación', 'Departamentos según el plano', 'Inicio',
             'Fin', 'Adelanto %', 'Fondo de garantía %', 'Descuento comercial',
             'Condiciones generales', 'Forma de pago', 'Garantía', 'Validez de la oferta')
OBRA_ROW = {name: index for index, name in enumerate(OBRA_ROWS, start=2)}
# Precargados de la cotización: en gris, se cambian en Ventas.
OBRA_PRELOADED = ('Proyecto', 'Código de cotización', 'Versión de la cotización',
                  'Fecha de cotización', 'Cliente', 'Solicitante', 'Ubicación')
PARTIDAS = ('Cocina', 'Closet', 'Baño', 'Lavandería', 'Ducto', 'Área común', 'Especial', 'Otro')
RATE_GROUPS = ('Mueble bajo', 'Mueble alto', 'Mueble completo', 'Sin ML', 'Accesorio', 'Global')
UNIT_TYPES = ('Departamento', 'Ducto', 'Estacionamiento', 'Área común', 'Depósito', 'Local',
              'Piloto')
# Pestaña → [(clave, encabezado, ancho, formato, calculada, oculta)], en orden.
_T = None
_M = design.MONEY
_I = design.INTEGER
SALE_COLUMNS = {
    BUILDING_SHEET: [
        ('group', 'Agrupador', 105, _T, 0, 0), ('floor_from', 'Piso desde', 105, _T, 0, 0),
        ('floor_to', 'Piso hasta', 105, _T, 0, 0), ('position', 'Posición', 105, '00', 0, 0),
        ('duplex', 'Nivel del dúplex', 120, _I, 0, 0),
        ('unit_type', 'Tipo de unidad', 125, _T, 0, 0), ('space', 'Ambiente', 215, _T, 0, 0),
        ('typology', 'Tipología', 120, _T, 0, 0), ('note', 'Nota', 220, _T, 0, 0),
        ('count', 'Dptos (calc.)', 105, _I, 1, 0), ('first', 'Primer dpto (calc.)', 105, _T, 1, 0),
        ('last', 'Último dpto (calc.)', 105, _T, 1, 0), ('warning', 'Aviso (calc.)', 200, _T, 1, 0),
        ('group_used', 'Agrupador usado (calc.)', 105, _T, 1, 1),
        ('from_used', 'Piso desde usado (calc.)', 105, _T, 1, 1),
        ('to_used', 'Piso hasta usado (calc.)', 105, _T, 1, 1),
        ('position_used', 'Posición usada (calc.)', 105, '00', 1, 1),
    ],
    FINISHES_SHEET: [
        ('code', 'Código del cliente', 105, _T, 0, 0),
        ('description', 'Descripción en el plano', 280, _T, 0, 0),
        ('kind', 'Tipo de acabado', 145, _T, 0, 0), ('thickness', 'Espesor (mm)', 105, _I, 0, 0),
        ('color', 'Color', 110, _T, 0, 0), ('material', 'Material de referencia', 280, _T, 0, 0),
        ('surcharge', 'Recargo por zona (calc.)', 105, '0%', 1, 0),
    ],
    RATES_SHEET: [
        ('partida', 'Partida', 120, _T, 0, 0), ('item', 'Ítem', 250, _T, 0, 0),
        ('uom', 'Unidad', 120, _T, 0, 0), ('base_size', 'Medida base (cm)', 105, _I, 0, 0),
        ('adjust', 'Medida que ajusta', 120, _T, 0, 0), ('price', 'Precio base', 105, _M, 0, 0),
        ('structure', 'Lleva estructura', 120, _T, 0, 0),
        ('fronts', 'Lleva frentes', 120, _T, 0, 0), ('rule', 'Regla', 120, _T, 0, 0),
        ('group', 'Grupo', 125, _T, 0, 0), ('status', 'En el catálogo (calc.)', 120, _T, 1, 0),
        ('rate_id', 'Id del tarifario (calc.)', 105, _T, 1, 1),
        ('lookup', 'Clave (calc.)', 105, _T, 1, 1),
    ],
    PRICES_SHEET: [
        ('partida', 'Partida', 120, _T, 0, 0), ('item', 'Ítem', 255, _T, 0, 0),
        ('name', 'Nombre en la obra', 200, _T, 0, 0), ('size', 'Medida real (cm)', 105, _I, 0, 0),
        ('structure', 'Acabado estructura', 120, _T, 0, 0),
        ('fronts', 'Acabado frentes', 120, _T, 0, 0), ('agreed', 'Precio acordado', 105, _M, 0, 0),
        ('note', 'Consideración', 230, _T, 0, 0), ('cost', 'Costo estimado', 105, _M, 0, 0),
        ('name_used', 'Nombre usado (calc.)', 240, _T, 1, 0),
        ('structure_used', 'Estructura usada (calc.)', 105, _T, 1, 0),
        ('fronts_used', 'Frentes usado (calc.)', 105, _T, 1, 0),
        ('by_size', 'Precio por medida (calc.)', 105, _M, 1, 0),
        ('surcharge', 'Recargo (calc.)', 105, '0%', 1, 0),
        ('with_finish', 'Con acabado (calc.)', 105, _M, 1, 0),
        ('rounded', 'Redondeado (calc.)', 105, _M, 1, 0),
        ('final', 'Precio final (calc.)', 105, _M, 1, 0),
        ('rate_row', 'Fila del tarifario (calc.)', 105, _I, 1, 1),
    ],
    MEASURE_SHEET: [
        ('typology', 'Tipología', 105, _T, 0, 0), ('name', 'Nombre', 170, _T, 0, 0),
        ('partida', 'Partida', 120, _T, 0, 0), ('item', 'Ítem de la obra', 275, _T, 0, 0),
        ('detail', 'Medida del detalle', 105, _M, 0, 0), ('plan', 'Medida del plano', 105, _M, 0, 0),
        ('note', 'Nota', 170, _T, 0, 0), ('typology_used', 'Tipología usada (calc.)', 105, _T, 1, 0),
        ('partida_used', 'Partida usada (calc.)', 105, _T, 1, 0),
        ('group', 'Grupo (calc.)', 110, _T, 1, 0), ('qty', 'Cantidad usada (calc.)', 105, _M, 1, 0),
        ('uom', 'Unidad (calc.)', 105, _T, 1, 0), ('price', 'Precio (calc.)', 105, _M, 1, 0),
        ('subtotal', 'Subtotal (calc.)', 105, _M, 1, 0), ('warning', 'Aviso (calc.)', 200, _T, 1, 0),
        ('price_row', 'Fila de PRECIOS (calc.)', 105, _I, 1, 1),
    ],
}
SALE_FREEZE = {BUILDING_SHEET: 4, FINISHES_SHEET: 1, RATES_SHEET: 2, PRICES_SHEET: 3,
               MEASURE_SHEET: 4}
SALE_NO_FILTER = (BUILDING_SHEET, MEASURE_SHEET)


def letter_of(sheet, key):
    """Letra de la columna ``key`` de una pestaña de la hoja de venta."""
    for index, column in enumerate(SALE_COLUMNS[sheet]):
        if column[0] == key:
            return chr(65 + index)
    raise KeyError(key)


def _column(sheet, key):
    letter = letter_of(sheet, key)
    return "'%s'!$%s:$%s" % (sheet, letter, letter) if ' ' in sheet else '%s!$%s:$%s' % (
        sheet, letter, letter)


def _text_list(values):
    return list(values)


class SaleSheetBuilder:
    """Arma el JSON de la hoja de venta. Recibe los datos de la cotización y los
    valores que necesita: no consulta la base salvo por ``parameter_model``."""

    HEAD_DATA, HEAD_CALC, CELL_DATA, CELL_CALC, LABEL, TITLE, TOTAL, BORDER = 1, 2, 3, 4, 5, 6, 7, 1

    def __init__(self, parameter_model, company, obra, overrides, spaces, tr, rows=SALE_ROWS,
                 rates=()):
        self.parameter_model = parameter_model
        self.company = company
        self.obra = obra
        self.overrides = overrides
        self.spaces = spaces
        self._ = tr
        self.rows = rows
        self.last = rows + 1
        self.rates = rates
        self.formats = {}

    def _format(self, text):
        return self.formats.setdefault(text, len(self.formats) + 1)

    def _rule(self, rule_id, ranges, values, blocking=True):
        return {'id': rule_id, 'isBlocking': blocking, 'ranges': ranges,
                'criterion': {'type': 'isValueInList', 'displayStyle': 'arrow',
                              'values': list(values)}}

    def _range_rule(self, rule_id, ranges, target):
        return {'id': rule_id, 'isBlocking': False, 'ranges': ranges,
                'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                              'values': [target]}}

    def _mark(self, mark_id, ranges, formula, fill, text):
        style = {'textColor': text}
        if fill:
            style['fillColor'] = fill
        return {'id': mark_id, 'ranges': ranges, 'stopIfTrue': False,
                'rule': {'type': 'CellIsRule', 'operator': 'customFormula', 'values': [formula],
                         'style': style}}

    def _error_mark(self, mark_id, ranges, formula):
        return self._mark(mark_id, ranges, formula, design.ERROR_FILL, design.ERROR_TEXT)

    def _warning_mark(self, mark_id, ranges, formula):
        return self._mark(mark_id, ranges, formula, design.WARNING_FILL, design.WARNING_TEXT)

    def _gray_mark(self, mark_id, ranges, formula):
        return self._mark(mark_id, ranges, formula, design.CELL_CALC_COLOR, design.CELL_CALC_TEXT)

    def _table_sheet(self, name, formulas, rules=(), conditional=(), extra=None, side_cols=None):
        """Pestaña de datos con el diseño de M117-23: ``formulas`` son
        ``{clave: plantilla con {r}}``; ``{p}`` es la fila anterior."""
        columns = SALE_COLUMNS[name]
        visible_last = chr(65 + len(columns) - 1)
        cells, styles, formats, cols = {}, {}, {}, {}
        for index, (key, header, width, number, calc, hidden) in enumerate(columns):
            letter = chr(65 + index)
            cells['%s1' % letter] = header
            styles['%s1' % letter] = self.HEAD_CALC if calc else self.HEAD_DATA
            ref = '%s2:%s%s' % (letter, letter, self.last)
            styles[ref] = self.CELL_CALC if calc else self.CELL_DATA
            if number:
                formats[ref] = self._format(number)
            cols[str(index)] = {'size': width}
            if hidden:
                cols[str(index)]['isHidden'] = True
            template = formulas.get(key)
            if template:
                for row in range(2, self.last + 1):
                    cells['%s%s' % (letter, row)] = template.replace(
                        '{r}', str(row)).replace('{p}', str(row - 1))
        cols.update(side_cols or {})
        cells.update((extra or {}).get('cells', {}))
        styles.update((extra or {}).get('styles', {}))
        formats.update((extra or {}).get('formats', {}))
        table = design.table_config(name) or {}
        table = dict(table, hasFilters=name not in SALE_NO_FILTER)
        return {
            'id': 'sale_%s' % name.lower().replace(' ', '_'), 'name': name,
            'colNumber': max(26, len(columns) + 10), 'rowNumber': self.rows + 50,
            'cells': cells, 'styles': styles, 'formats': formats,
            'borders': {'A1:%s1' % visible_last: self.BORDER}, 'cols': cols,
            'rows': {'0': {'size': design.HEADER_HEIGHT}},
            'panes': {'xSplit': SALE_FREEZE.get(name, 0), 'ySplit': 1},
            'tables': [{'range': 'A1:%s%s' % (visible_last, self.last), 'type': 'static',
                        'config': table}],
            'dataValidationRules': list(rules), 'conditionalFormats': list(conditional),
        }

    # ------------------------------------------------------------------
    # OBRA
    # ------------------------------------------------------------------
    def _obra_sheet(self):
        cells = {'A1': 'Dato', 'B1': 'Valor', 'D1': 'Fecha', 'E1': 'Versión', 'F1': 'Pedido por',
                 'G1': 'Canal', 'H1': 'Cambio'}
        styles = {'A1:B1': self.HEAD_CALC, 'D1:E1': self.HEAD_CALC, 'F1:H1': self.HEAD_DATA,
                  'F2:H200': self.CELL_DATA, 'D2:E200': self.CELL_CALC}
        for name, row in OBRA_ROW.items():
            cells['A%s' % row] = name
            styles['A%s' % row] = self.LABEL
            value = self.obra.get(name)
            if value not in (None, '', False):
                cells['B%s' % row] = str(value)
            styles['B%s' % row] = self.CELL_CALC if name in OBRA_PRELOADED else self.CELL_DATA
        date_format = self._format(design.DATE)
        formats = {'B%s' % OBRA_ROW['Inicio']: date_format, 'B%s' % OBRA_ROW['Fin']: date_format,
                   'B%s' % OBRA_ROW['Fecha de cotización']: date_format,
                   'B%s' % OBRA_ROW['Adelanto %']: self._format(design.PERCENT),
                   'B%s' % OBRA_ROW['Fondo de garantía %']: self._format(design.PERCENT),
                   'B%s' % OBRA_ROW['Descuento comercial']: self._format(design.MONEY)}
        plan = 'B%s' % OBRA_ROW['Departamentos según el plano']
        return {
            'id': 'sale_obra', 'name': OBRA_SHEET, 'colNumber': 12, 'rowNumber': 210,
            'cells': cells, 'styles': styles, 'formats': formats,
            'cols': {'0': {'size': 220}, '1': {'size': 320}, '3': {'size': 110},
                     '4': {'size': 80}, '5': {'size': 160}, '6': {'size': 110},
                     '7': {'size': 320}},
            'rows': {'0': {'size': design.HEADER_HEIGHT}},
            'panes': {'xSplit': 0, 'ySplit': 1},
            'conditionalFormats': [
                self._error_mark('obra_plan', [plan], '=AND({p}<>"",{p}<>{b}!$T$1)'.format(
                    p=plan.replace('B', '$B$'), b=BUILDING_SHEET)),
                self._error_mark('obra_required', ['B2', 'B3', 'B6'], '=B2=""'),
            ],
        }

    # ------------------------------------------------------------------
    # EDIFICIO (M117-17)
    # ------------------------------------------------------------------
    def _named_prefix(self, floor):
        """Prefijo de un piso con nombre, de «Azotea=AZ;Sótano=SO»."""
        floors = '";"&%s&";"' % param('pisos_nombre')
        return 'TEXTBEFORE(TEXTAFTER(%s,";"&%s&"="),";")' % (floors, floor)

    def _building_sheet(self):
        factor = param('dpto_factor')
        last = self.last
        used = lambda letter, column, text='': (
            '=IF($G{r}="","",IF(AND($A{r}="",$B{r}="",$C{r}="",$D{r}=""),%s{p},$%s{r}%s))' % (
                letter, column, text))
        def number(floor):
            return ('IF($G{r}="","",IF(ISNUMBER(%s{r}),%s{r}*%s+$Q{r},IFERROR(%s,"")&TEXT($Q{r},'
                    '"00")))' % (floor, floor, factor, self._named_prefix('%s{r}' % floor)))
        overlap = ('SUMPRODUCT(($N$2:$N${l}=$N{r})*($Q$2:$Q${l}=$Q{r})*($E$2:$E${l}=$E{r})*'
                   '($G$2:$G${l}=$G{r})*($O$2:$O${l}<=$P{r})*($P$2:$P${l}>=$O{r}))>1'
                   ).replace('{l}', str(last))
        formulas = {
            'group_used': used('N', 'A', '&""'), 'from_used': used('O', 'B'),
            'to_used': used('P', 'C'), 'position_used': used('Q', 'D'),
            'count': '=IF($G{r}="","",IF(ISNUMBER($O{r}),$P{r}-$O{r}+1,1))',
            'first': '=' + number('$O'), 'last': '=' + number('$P'),
            'warning': ('=IF($G{r}="","",IF(%s,"Se cruza con otra fila",IF(AND($H{r}<>"",COUNTIF('
                        '%s,$H{r})=0),"Tipología sin metrado",IF(COUNTIF(%s!$B:$B,$G{r})=0,'
                        '"Ambiente fuera de la lista",""))))' % (
                            overlap, _column(MEASURE_SHEET, 'typology_used'), REFERENCE_SHEET)),
        }
        sheet = self._table_sheet(BUILDING_SHEET, formulas, rules=[
            self._rule('building_duplex', ['E2:E%s' % last], ['2']),
            self._rule('building_unit', ['F2:F%s' % last], UNIT_TYPES),
            self._range_rule('building_space', ['G2:G%s' % last],
                             '%s!$B$3:$B$60' % REFERENCE_SHEET),
            self._range_rule('building_typology', ['H2:H%s' % last],
                             '%s!$Q$3:$Q$%s' % (MEASURE_SHEET, last)),
        ], conditional=[
            self._error_mark('building_error', ['A2:M%s' % last], '=$M2="Se cruza con otra fila"'),
            self._error_mark('building_typology_mark', ['M2:M%s' % last],
                             '=$M2="Tipología sin metrado"'),
            self._warning_mark('building_warning', ['M2:M%s' % last],
                               '=$M2="Ambiente fuera de la lista"'),
            self._error_mark('building_count', ['T1'], '=AND({o}!$B${r}<>"",{o}!$B${r}<>$T$1)'.format(
                o=OBRA_SHEET, r=OBRA_ROW['Departamentos según el plano'])),
        ], extra={
            'cells': {
                'S1': 'Departamentos de la obra',
                'T1': '=SUMIFS($J$2:$J${l},$G$2:$G${l},{a},$E$2:$E${l},"<>2")'.format(
                    l=last, a=param('amb_cuenta')),
                'S2': 'Tipología', 'T2': 'Ambientes',
                'S3': '=IFERROR(UNIQUE(FILTER($H$2:$H${l},$H$2:$H${l}<>"")),"")'.format(l=last),
                **{'T%s' % row: '=IF(S{r}="","",SUMIF($H$2:$H${l},S{r},$J$2:$J${l}))'.format(
                    r=row, l=last) for row in range(3, 103)},
            },
            'styles': {'S1:S2': self.LABEL, 'T1': self.TOTAL, 'T2': self.LABEL},
        }, side_cols={'18': {'size': 190}, '19': {'size': 90}})
        # Primera fila: no hay fila anterior de la que tomar el rango.
        for letter, column in (('N', 'A'), ('O', 'B'), ('P', 'C'), ('Q', 'D')):
            sheet['cells']['%s2' % letter] = '=IF($G2="","",$%s2%s)' % (
                column, '&""' if letter == 'N' else '')
        return sheet

    # ------------------------------------------------------------------
    # ACABADOS (M117-18)
    # ------------------------------------------------------------------
    def _finishes_sheet(self):
        last = self.last
        partida_rows = len(PARTIDAS) + 1
        return self._table_sheet(FINISHES_SHEET, {
            'surcharge': '=IF($C{r}="","",IFERROR(XLOOKUP("Recargo: "&$C{r},%s!$B:$B,%s!$I:$I),0))'
                         % (PARAMETERS_SHEET, PARAMETERS_SHEET),
        }, rules=[
            self._range_rule('finish_kind', ['C2:C%s' % last], '%s!$C$3:$C$60' % REFERENCE_SHEET),
            self._range_rule('finish_default', ['J2:K%s' % partida_rows],
                             '%s!$A$2:$A$%s' % (FINISHES_SHEET, last)),
            self._rule('finish_partida', ['I2:I%s' % partida_rows], PARTIDAS, blocking=False),
        ], conditional=[
            self._error_mark('finish_repeated', ['A2:A%s' % last],
                             '=AND($A2<>"",COUNTIF($A$2:$A${l},$A2)>1)'.format(l=last)),
            self._error_mark('finish_default_missing', ['J2:K%s' % partida_rows],
                             '=AND(J2<>"",COUNTIF($A$2:$A${l},J2)=0)'.format(l=last)),
        ], extra={
            'cells': {
                'I1': 'Partida', 'J1': 'Estructura', 'K1': 'Frentes',
                # Fila base de la casa (M117-18, punto 2).
                'A2': 'STD', 'B2': 'Estándar blanco', 'C2': 'Estándar blanco',
                **{'I%s' % row: name for row, name in enumerate(PARTIDAS, start=2)},
            },
            'styles': {'I1:K1': self.HEAD_DATA, 'I2:K%s' % partida_rows: self.CELL_DATA},
        }, side_cols={'8': {'size': 120}, '9': {'size': 120}, '10': {'size': 120}})

    # ------------------------------------------------------------------
    # TARIFARIO y PRECIOS (M117-19)
    # ------------------------------------------------------------------
    def _rates_sheet(self):
        last = self.last
        # «Traer tarifario» corre solo al crear la hoja (M117-19, punto 6).
        loaded = {'%s%s' % (letter, row): value
                  for row, line in enumerate(self.rates, start=2)
                  for letter, value in line.items() if value not in ('', None)}
        return self._table_sheet(RATES_SHEET, {
            'status': '=IF($B{r}="","",IF($L{r}="","Fuera del tarifario","Vigente"))',
            'lookup': '=IF($B{r}="","",$A{r}&"|"&$B{r})',
        }, rules=[
            self._rule('rate_partida', ['A2:A%s' % last], PARTIDAS),
            self._rule('rate_uom', ['C2:C%s' % last], ('ML', 'UND')),
            self._rule('rate_adjust', ['E2:E%s' % last], ('Alto', 'Ancho', 'Ninguna')),
            self._rule('rate_structure', ['G2:H%s' % last], ('Sí', 'No')),
            self._rule('rate_rule', ['I2:I%s' % last], ('Por costo',)),
            self._rule('rate_group', ['J2:J%s' % last], RATE_GROUPS),
        ], conditional=[
            self._error_mark('rate_repeated', ['A2:B%s' % last],
                             '=AND($M2<>"",COUNTIF($M$2:$M${l},$M2)>1)'.format(l=last)),
            self._warning_mark('rate_status', ['K2:K%s' % last],
                               '=OR($K2="Ya no está",$K2="Fuera del tarifario")'),
        ], extra={'cells': loaded})

    def _prices_sheet(self):
        last = self.last
        rate = lambda key: 'INDEX(%s,$R{r})' % _column(RATES_SHEET, key)
        adjusts = 'AND(%s="Sí",%s<>"Ninguna",$D{r}<>"",%s>0)' % (
            param('regla_tres'), rate('adjust'), rate('base_size'))
        by_cost = '%s="Por costo"' % rate('rule')
        finish = lambda column: 'IF(%s="",0,IFERROR(XLOOKUP(%s,%s,%s),0))' % (
            column, column, _column(FINISHES_SHEET, 'code'), _column(FINISHES_SHEET, 'surcharge'))
        default = lambda written, carries, letter: (
            '=IF($R{r}=0,"",IF(%s="Sí",IF(%s<>"",%s,IFERROR(XLOOKUP($A{r},%s!$I:$I,%s!$%s:$%s),'
            '"")),""))' % (rate(carries), written, written, FINISHES_SHEET, FINISHES_SHEET,
                           letter, letter))
        multiple, direction = param('redondeo_multiplo'), param('redondeo_sentido')
        # ROUND antes de redondear al múltiplo: 345 × 1.8 da 621.0000000001 en
        # coma flotante, y un valor justo en el múltiplo no debe subir.
        rounded = (
            '=IF($R{{r}}=0,"",IF(OR({d}="Sin redondeo",{m}=0),$O{{r}},IF({d}="Hacia arriba",'
            'ROUNDUP(ROUND($O{{r}}/{m},6),0)*{m},ROUND($O{{r}}/{m},0)*{m})))'
        ).format(d=direction, m=multiple)
        return self._table_sheet(PRICES_SHEET, {
            'rate_row': '=IF($B{r}="",0,IFERROR(MATCH($A{r}&"|"&$B{r},%s,0),0))' % _column(
                RATES_SHEET, 'lookup'),
            'name_used': '=IF($B{r}="","",IF($C{r}<>"",$C{r},IF($D{r}<>"",$B{r}&" "&$D{r}&" cm",'
                         '$B{r})))',
            'structure_used': default('$E{r}', 'structure', 'J'),
            'fronts_used': default('$F{r}', 'fronts', 'K'),
            'by_size': '=IF($R{r}=0,"",IF(%s,IF($I{r}="",0,$I{r})*%s,IF(%s,%s*$D{r}/%s,%s)))' % (
                by_cost, param('factor_costo'), adjusts, rate('price'), rate('base_size'),
                rate('price')),
            'surcharge': '=IF($R{r}=0,"",%s+%s)' % (finish('$K{r}'), finish('$L{r}')),
            'with_finish': '=IF($R{r}=0,"",$M{r}*(1+$N{r}))',
            'rounded': rounded,
            'final': '=IF($R{r}=0,"",IF($G{r}<>"",$G{r},$P{r}))',
        }, rules=[
            self._rule('price_partida', ['A2:A%s' % last], PARTIDAS),
            self._range_rule('price_structure', ['E2:F%s' % last],
                             '%s!$A$2:$A$%s' % (FINISHES_SHEET, last)),
        ] + [self._range_rule(
            'price_item_%s' % row, ['B%s' % row],
            '%s!$A$%s:$AZ$%s' % (LISTS_SHEET, _helper_row('item', row), _helper_row('item', row)))
            for row in range(2, last + 1)
        ], conditional=[
            self._warning_mark('price_agreed', ['Q2:Q%s' % last],
                               '=AND($G2<>"",$G2<>$P2)'),
            self._error_mark('price_repeated', ['J2:J%s' % last],
                             '=AND($J2<>"",COUNTIF($J$2:$J${l},$J2)>1)'.format(l=last)),
            self._error_mark('price_item', ['B2:B%s' % last], '=AND($B2<>"",$R2=0)'),
            self._error_mark('price_finish', ['E2:F%s' % last],
                             '=AND(E2<>"",COUNTIF(%s,E2)=0)' % _column(FINISHES_SHEET, 'code')),
            self._gray_mark('price_size_na', ['D2:D%s' % last], (
                '=AND($R2>0,OR(INDEX({a},$R2)="Ninguna",INDEX({a},$R2)=""))'
            ).format(a=_column(RATES_SHEET, 'adjust'))),
            self._gray_mark('price_structure_na', ['E2:E%s' % last],
                            '=AND($R2>0,INDEX(%s,$R2)<>"Sí")' % _column(RATES_SHEET, 'structure')),
            self._gray_mark('price_fronts_na', ['F2:F%s' % last],
                            '=AND($R2>0,INDEX(%s,$R2)<>"Sí")' % _column(RATES_SHEET, 'fronts')),
            self._gray_mark('price_cost_na', ['I2:I%s' % last],
                            '=AND($R2>0,INDEX(%s,$R2)<>"Por costo")' % _column(RATES_SHEET, 'rule')),
        ])

    # ------------------------------------------------------------------
    # METRADO (M117-20)
    # ------------------------------------------------------------------
    def _measure_sheet(self):
        last = self.last
        price = lambda key: 'INDEX(%s,$P{r})' % _column(PRICES_SHEET, key)
        through = lambda key: 'INDEX(%s,%s)' % (_column(RATES_SHEET, key), price('rate_row'))
        qty = 'IF($F{r}="",$E{r},IF($E{r}="",$F{r},IF(%s="Sí",MAX($E{r},$F{r}),$E{r})))' % param(
            'medida_mayor')
        plan_wins = ('AND($F{r}<>"",%s="Sí",$F{r}>$E{r})' % param('medida_mayor'))
        sheet = self._table_sheet(MEASURE_SHEET, {
            'typology_used': '=IF($D{r}="","",IF($A{r}<>"",$A{r},$H{p}))',
            'partida_used': '=IF($D{r}="","",IF($C{r}<>"",$C{r},$I{p}))',
            'price_row': '=IF($D{r}="",0,IFERROR(MATCH($D{r},%s,0),0))' % _column(
                PRICES_SHEET, 'name_used'),
            'group': '=IF($P{r}=0,"",%s)' % through('group'),
            'qty': '=IF($D{r}="","",%s)' % qty,
            'uom': '=IF($P{r}=0,"",%s)' % through('uom'),
            'price': '=IF($P{r}=0,"",%s)' % price('final'),
            'subtotal': '=IF($P{r}=0,"",$K{r}*$M{r})',
            'warning': ('=IF($D{r}="","",IF($P{r}=0,"Ítem que no está en PRECIOS",IF(AND($C{r}<>"",'
                        '$C{r}<>$I{p},$A{r}=""),"Partida distinta en el bloque",IF(COUNTIF(%s,$H{r}'
                        ')=0,"Tipología que no está en EDIFICIO",IF(%s,"Vale la del plano","")))))'
                        % (_column(BUILDING_SHEET, 'typology'), plan_wins)),
        }, rules=[
            self._rule('measure_partida', ['C2:C%s' % last], PARTIDAS),
        ] + [self._range_rule(
            'measure_item_%s' % row, ['D%s' % row],
            '%s!$A$%s:$AZ$%s' % (LISTS_SHEET, _helper_row('measure', row),
                                 _helper_row('measure', row)))
            for row in range(2, last + 1)
        ], conditional=[
            self._warning_mark('measure_plan', ['K2:K%s' % last, 'O2:O%s' % last],
                               '=$O2="Vale la del plano"'),
            self._warning_mark('measure_no_building', ['O2:O%s' % last],
                               '=$O2="Tipología que no está en EDIFICIO"'),
            self._error_mark('measure_error', ['O2:O%s' % last],
                             '=OR($O2="Ítem que no está en PRECIOS",'
                             '$O2="Partida distinta en el bloque")'),
            self._gray_mark('measure_block', ['A3:C%s' % last], '=AND($D3<>"",$A3="")'),
        ], extra=self._measure_summary(), side_cols={
            '16': {'size': 105}, '17': {'size': 170}, '24': {'size': 105, 'isHidden': True}})
        sheet['cells']['H2'] = '=IF($D2="","",$A2)'
        sheet['cells']['I2'] = '=IF($D2="","",$C2)'
        sheet['cells']['O2'] = sheet['cells']['O2'].replace('$I1', '""')
        return sheet

    def _measure_summary(self):
        """Resumen por tipología a la derecha (Q:X); oculta, la partida (Y)."""
        last = self.last
        h, i, j, k, n = ('$%s$2:$%s$%s' % (letter, letter, last) for letter in 'HIJKN')
        building = (_range(BUILDING_SHEET, 'typology', last), _range(BUILDING_SHEET, 'count', last))
        cells = {'Q1': 'Tipología', 'R1': 'Nombre', 'S1': 'ML bajo', 'T1': 'ML alto',
                 'U1': 'ML completo', 'V1': 'Precio por ambiente', 'W1': 'Ambientes',
                 'X1': 'Total sin IGV', 'Y1': 'Partida',
                 'Q2': 'Total', 'X2': '=SUM($X$3:$X$%s)' % (last + 1),
                 'Q3': '=IFERROR(UNIQUE(FILTER({h},{h}<>"")),"")'.format(h=h)}
        for row in range(3, last + 2):
            values = {
                'R': '=IF($Q{r}="","",IFERROR(XLOOKUP($Q{r},$A$2:$A${l},$B$2:$B${l}),""))',
                'S': '=IF($Q{r}="","",SUMIFS(%s,%s,$Q{r},%s,"Mueble bajo"))' % (k, h, j),
                'T': '=IF($Q{r}="","",SUMIFS(%s,%s,$Q{r},%s,"Mueble alto"))' % (k, h, j),
                'U': '=IF($Q{r}="","",SUMIFS(%s,%s,$Q{r},%s,"Mueble completo"))' % (k, h, j),
                'V': '=IF($Q{r}="","",SUMIF(%s,$Q{r},%s))' % (h, n),
                'W': '=IF($Q{r}="","",SUMIF(%s,$Q{r},%s))' % building,
                'X': '=IF($Q{r}="","",$V{r}*$W{r})',
                'Y': '=IF($Q{r}="","",IFERROR(XLOOKUP($Q{r},%s,%s),""))' % (h, i),
            }
            for letter, template in values.items():
                cells['%s%s' % (letter, row)] = template.replace('{r}', str(row)).replace(
                    '{l}', str(last))
        money = self._format(design.MONEY)
        return {
            'cells': cells,
            'styles': {'Q1:Y1': self.HEAD_CALC, 'Q2:X2': self.TOTAL,
                       'Q3:X%s' % (last + 1): self.CELL_CALC},
            'formats': {'S2:V%s' % (last + 1): money, 'X2:X%s' % (last + 1): money},
        }

    # ------------------------------------------------------------------
    # RESUMEN VENTA (M117-21)
    # ------------------------------------------------------------------
    def _summary_sheet(self):
        """Vista de la cotización: todo calculado. El PDF lo arma el reporte."""
        last = self.last
        obra = lambda name: '%s!$B$%s' % (OBRA_SHEET, OBRA_ROW[name])
        money = self._format(design.MONEY)
        partida = "%s!$Y$3:$Y$%s" % (MEASURE_SHEET, last + 1)
        spaces = "%s!$W$3:$W$%s" % (MEASURE_SHEET, last + 1)
        totals = "%s!$X$3:$X$%s" % (MEASURE_SHEET, last + 1)
        cells = {'A1': 'Cotización', 'A2': 'Cliente', 'A3': 'Proyecto', 'A4': 'Ubicación',
                 'A5': 'Solicitante', 'A6': 'Código', 'A7': 'Versión', 'A8': 'Fecha',
                 'A9': 'Moneda', 'B2': '=%s&""' % obra('Cliente'), 'B3': '=%s&""' % obra('Proyecto'),
                 'B4': '=%s&""' % obra('Ubicación'), 'B5': '=%s&""' % obra('Solicitante'),
                 'B6': '=%s&""' % obra('Código de cotización'),
                 'B7': '=%s&""' % obra('Versión de la cotización'),
                 'B8': '=%s' % obra('Fecha de cotización'), 'B9': '=%s&""' % param('moneda'),
                 'A11': 'Producto', 'B11': 'Ambientes', 'C11': 'Subtotal',
                 'A12': '=IFERROR(UNIQUE(FILTER({p},{p}<>"")),"")'.format(p=partida)}
        styles = {'A1': self.TITLE, 'A2:A9': self.LABEL, 'B2:B9': self.CELL_CALC,
                  'A11:C11': self.HEAD_CALC, 'A12:C31': self.CELL_CALC}
        formats = {'C12:C36': money}
        for row in range(12, 32):
            cells['B%s' % row] = '=IF($A{r}="","",SUMIF({p},$A{r},{s}))'.format(
                r=row, p=partida, s=spaces)
            cells['C%s' % row] = '=IF($A{r}="","",SUMIF({p},$A{r},{t}))'.format(
                r=row, p=partida, t=totals)
        total = 'SUM($C$12:$C$31)'
        discount = 'IF(%s="",0,%s)' % (obra('Descuento comercial'), obra('Descuento comercial'))
        without = '%s="Sí"' % param('precio_sin_igv')
        igv = param('igv')
        net = '(%s-%s)' % (total, discount)
        rows = (
            (32, 'Suma de partidas', '=%s' % total),
            (33, 'Descuento comercial', '=IF(%s=0,"",-%s)' % (discount, discount)),
            (34, 'Subtotal', '=IF(%s,%s,%s/(1+%s))' % (without, net, net, igv)),
            (35, 'IGV', '=IF(%s,%s*%s,%s-%s/(1+%s))' % (without, net, igv, net, net, igv)),
            (36, 'Total', '=$C$34+$C$35'),
        )
        for row, label, formula in rows:
            cells['A%s' % row] = label
            cells['C%s' % row] = formula
            styles['A%s:C%s' % (row, row)] = self.TOTAL if row == 36 else self.LABEL
        for row, label, name in ((38, 'Condiciones generales', 'Condiciones generales'),
                                 (39, 'Forma de pago', 'Forma de pago'),
                                 (40, 'Garantía', 'Garantía'),
                                 (41, 'Validez de la oferta', 'Validez de la oferta')):
            cells['A%s' % row] = label
            cells['B%s' % row] = '=%s&""' % obra(name)
            styles['A%s' % row] = self.LABEL
        return {
            'id': 'sale_resumen', 'name': SUMMARY_SHEET, 'colNumber': 8, 'rowNumber': 80,
            'cells': cells, 'styles': styles, 'formats': formats,
            'cols': {'0': {'size': 230}, '1': {'size': 320}, '2': {'size': 130}},
        }

    # ------------------------------------------------------------------
    # INICIO y LEEME (M117-16)
    # ------------------------------------------------------------------
    def _start_sheet(self):
        obra = lambda name: '%s!$B$%s' % (OBRA_SHEET, OBRA_ROW[name])
        building_count = '%s!$T$1' % BUILDING_SHEET
        warnings = _column(BUILDING_SHEET, 'warning')
        plan = obra('Departamentos según el plano')
        steps = (
            ('1 · OBRA', OBRA_SHEET, 'Datos de la cotización',
             'AND(%s<>"",%s<>"",%s<>"")' % (obra('Proyecto'), obra('Cliente'),
                                            obra('Código de cotización')),
             'IF({c}="","Falta el cliente",IF({p}="","Falta el proyecto","Falta el código"))'.format(
                 c=obra('Cliente'), p=obra('Proyecto')), False),
            ('2 · PARAMETROS', PARAMETERS_SHEET, 'Valores de cálculo',
             'SUMPRODUCT(({v}<>"")*({v}<>{i})*({m}=""))=0'.format(
                 v='%s!$C$2:$C$80' % PARAMETERS_SHEET, i='%s!$F$2:$F$80' % PARAMETERS_SHEET,
                 m='%s!$H$2:$H$80' % PARAMETERS_SHEET),
             '"Parámetro cambiado sin motivo"', False),
            ('3 · EDIFICIO', BUILDING_SHEET, 'Departamentos y típicos',
             'AND({n}>0,COUNTIF({w},"Se cruza con otra fila")=0,OR({p}="",{p}={n}))'.format(
                 n=building_count, w=warnings, p=plan),
             'IF({n}=0,"Sin filas",IF(COUNTIF({w},"Se cruza con otra fila")>0,"Rangos que se '
             'cruzan",{n}&" dptos; el plano dice "&{p}))'.format(
                 n=building_count, w=warnings, p=plan), False),
            ('4 · ACABADOS', FINISHES_SHEET, 'Leyenda del cliente',
             'SUMPRODUCT(({u}<>"")*(COUNTIF({c},{u})=0))=0'.format(
                 u='%s!$K$2:$L$%s' % (PRICES_SHEET, self.last), c=_column(FINISHES_SHEET, 'code')),
             '"Acabado usado que no existe"', True),
            ('5 · PRECIOS', PRICES_SHEET, 'Precio de cada ítem',
             'COUNTIF(%s,"Ítem que no está en PRECIOS")=0' % _column(MEASURE_SHEET, 'warning'),
             '"Ítem usado sin precio"', True),
            ('6 · METRADO', MEASURE_SHEET, 'ML y unidades por tipología',
             'COUNTIF(%s,"Tipología sin metrado")=0' % warnings,
             'IFERROR(XLOOKUP("Tipología sin metrado",{w},{t})&" sin metrado","Falta metrar")'.format(
                 w=warnings, t=_column(BUILDING_SHEET, 'typology')), False),
        )
        cells = {'A1': 'Hoja de venta', 'A3': 'Cotización', 'B3': '=%s&""' % obra('Código de cotización'),
                 'A4': 'Cliente', 'B4': '=%s&""' % obra('Cliente'), 'A5': 'Proyecto',
                 'B5': '=%s&""' % obra('Proyecto'), 'A6': 'Versión',
                 'B6': '=%s&""' % obra('Versión de la cotización'), 'A7': 'Fase de la hoja',
                 'B7': self.obra.get('_phase') or 'Venta en curso',
                 'A8': 'Departamentos de la obra', 'B8': '=%s' % building_count,
                 'A9': 'Subtotal sin IGV', 'B9': "='%s'!$C$34" % SUMMARY_SHEET,
                 'A10': 'Parámetros cambiados',
                 'B10': '=SUMPRODUCT(({v}<>"")*({v}<>{i}))'.format(
                     v='%s!$C$2:$C$80' % PARAMETERS_SHEET, i='%s!$F$2:$F$80' % PARAMETERS_SHEET),
                 'A12': 'Paso', 'B12': 'Qué se hace', 'C12': 'Ir', 'D12': 'Estado', 'E12': 'Qué falta'}
        styles = {'A1': self.TITLE, 'A3:A10': self.LABEL, 'A12:E12': self.HEAD_CALC}
        formats = {'B9': self._format(design.MONEY)}
        first = 13
        for row, (step, sheet_name, what, ready, missing, optional) in enumerate(steps, start=first):
            cells['A%s' % row] = step
            cells['B%s' % row] = what
            cells['C%s' % row] = '=HYPERLINK("o-spreadsheet://%s","Ir")' % (
                'sale_%s' % sheet_name.lower().replace(' ', '_') if sheet_name != PARAMETERS_SHEET
                else 'sheet_parametros')
            cells['D%s' % row] = '=IF(%s,"Listo","Falta")' % ready
            cells['E%s' % row] = '=IF(D%s="Listo","",%s)' % (row, missing)
        row = first + len(steps)
        cells.update({
            'A%s' % row: '7 · RESUMEN VENTA', 'B%s' % row: 'Revisar la cotización',
            'C%s' % row: '=HYPERLINK("o-spreadsheet://sale_resumen_venta","Ir")',
            'D%s' % row: '=IF(COUNTIF($D$%s:$D$%s,"Falta")=0,"Listo","Falta")' % (first, row - 1),
            'E%s' % row: '=IF(D%s="Listo","","Complete los pasos anteriores")' % row,
        })
        status = 'D%s:D%s' % (first, row)
        return {
            'id': 'sale_inicio', 'name': START_SHEET, 'colNumber': 8, 'rowNumber': 60,
            'cells': cells, 'styles': styles, 'formats': formats,
            'cols': {'0': {'size': 210}, '1': {'size': 260}, '2': {'size': 60}, '3': {'size': 90},
                     '4': {'size': 320}},
            'conditionalFormats': [
                self._mark('start_ready', [status], '=D%s="Listo"' % first, design.OK_FILL,
                           design.OK_TEXT),
                self._error_mark('start_missing', [status], '=D%s="Falta"' % first),
            ],
        }

    def _readme_sheet(self):
        lines = (
            'Hoja de venta: qué se vende y a qué precio. Siga la ruta de INICIO.',
            '',
            '1. OBRA: datos de la cotización. Los grises vienen de Ventas.',
            '2. PARAMETROS: IGV, redondeo, recargos. Cambiar un valor pide el motivo.',
            '3. EDIFICIO: rangos de departamentos iguales, como se cuentan en el plano.',
            '4. ACABADOS: la leyenda del cliente y el acabado por defecto de cada partida.',
            '5. PRECIOS: cada ítem que lleva la cotización. El precio sale solo.',
            '6. METRADO: los ML y unidades de cada tipología.',
            '7. RESUMEN VENTA: revise la cotización como la verá el cliente.',
            '8. Menú Hoja de venta › Validar y después › Pasar el resumen a la cotización.',
            '',
            'Amarillo: lo que se llena. Gris: lo que calcula la hoja.',
        )
        return {
            'id': 'sale_leeme', 'name': README_SHEET, 'colNumber': 4, 'rowNumber': 40,
            'cells': {'A%s' % index: text for index, text in enumerate(lines, start=1) if text},
            'styles': {'A1': self.TITLE}, 'cols': {'0': {'size': 900}},
        }

    def _errors_sheet(self):
        return {
            'id': 'sale_errores', 'name': ERRORS_SHEET, 'colNumber': 8, 'rowNumber': 400,
            'cells': {'A1': self._('Sin validar: menú Hoja de venta › Validar'),
                      'A2': 'Hoja', 'B2': 'Fila', 'C2': 'Columna', 'D2': 'Mensaje',
                      'E2': 'Tipo', 'F2': 'Ir'},
            'styles': {'A1': self.TITLE, 'A2:F2': self.LABEL},
            'cols': {'0': {'size': 120}, '3': {'size': 480}},
            'panes': {'xSplit': 0, 'ySplit': 2},
            'conditionalFormats': [
                self._error_mark('errors_error', ['E3:E400'], '=$E3="Error"'),
                self._warning_mark('errors_warning', ['E3:E400'], '=$E3="Aviso"'),
            ],
        }

    def _references_sheet(self):
        cells = {'A1': 'Listas de la hoja de venta', 'A2': 'Partida', 'B2': 'Ambiente',
                 'C2': 'Tipo de acabado',
                 'C3': ('=IFERROR(TEXTAFTER(FILTER({n},LEFT({n},9)="Recargo: "),"Recargo: "),"")'
                        ).format(n='%s!$B$2:$B$80' % PARAMETERS_SHEET)}
        for row, name in enumerate(PARTIDAS, start=3):
            cells['A%s' % row] = name
        for row, name in enumerate(self.spaces, start=3):
            cells['B%s' % row] = name
        return {'id': 'sale_referencias', 'name': REFERENCE_SHEET, 'colNumber': 8, 'rowNumber': 100,
                'cells': cells, 'styles': {'A1': self.TITLE, 'A2:C2': self.LABEL},
                'cols': {'0': {'size': 140}, '1': {'size': 240}, '2': {'size': 180}}}

    def _lists_sheet(self):
        """Por partida, sus ítems y sus nombres usados; cada fila de PRECIOS y de
        METRADO busca la de su partida (como las categorías de la otra hoja)."""
        cells = {}
        rate_partida, rate_item = (_column(RATES_SHEET, key) for key in ('partida', 'item'))
        price_partida, price_name = (_column(PRICES_SHEET, key) for key in ('partida', 'name_used'))
        count = len(PARTIDAS)
        for index, name in enumerate(PARTIDAS, start=1):
            cells['A%s' % index] = name
            cells['B%s' % index] = '=IFERROR(TRANSPOSE(FILTER(%s,%s=$A%s)),"")' % (
                rate_item, rate_partida, index)
            row = count + index
            cells['A%s' % row] = name
            cells['B%s' % row] = '=IFERROR(TRANSPOSE(FILTER(%s,%s=$A%s)),"")' % (
                price_name, price_partida, row)
        for row in range(2, self.last + 1):
            cells['A%s' % _helper_row('item', row)] = (
                '=IF({s}!$A{r}="","",IFERROR(INDEX($B$1:$AZ${n},MATCH({s}!$A{r},$A$1:$A${n},0),0),'
                '""))').format(s=PRICES_SHEET, r=row, n=count)
            cells['A%s' % _helper_row('measure', row)] = (
                '=IF({s}!$I{r}="","",IFERROR(INDEX($B${a}:$AZ${b},MATCH({s}!$I{r},$A${a}:$A${b},0)'
                ',0),""))').format(s=MEASURE_SHEET, r=row, a=count + 1, b=count * 2)
        return {'id': 'sale_listas', 'name': LISTS_SHEET, 'colNumber': 54,
                'rowNumber': _helper_row('measure', self.last) + 10, 'cells': cells,
                'isVisible': False}

    # ------------------------------------------------------------------
    def build(self):
        styles = {
            self.HEAD_DATA: design.HEADER_DATA, self.HEAD_CALC: design.HEADER_CALC,
            self.CELL_DATA: design.CELL_DATA, self.CELL_CALC: design.CELL_CALC,
            self.LABEL: {'bold': True, 'fillColor': design.HEADER_CALC_COLOR},
            self.TITLE: {'bold': True, 'fontSize': 16},
            self.TOTAL: {'bold': True, 'fillColor': design.TAB_ANALYSIS, 'textColor': '#FFFFFF'},
        }
        parameters = self.parameter_model._construction_sheet_data(
            'sale', self.company, {
                'head_data': self.HEAD_DATA, 'head_calc': self.HEAD_CALC, 'data': self.CELL_DATA,
                'calc': self.CELL_CALC, 'border': self.BORDER,
            }, self.formats, self.overrides)
        sheets = [
            self._start_sheet(), self._readme_sheet(), self._obra_sheet(), parameters,
            self._building_sheet(), self._finishes_sheet(), self._rates_sheet(),
            self._prices_sheet(), self._measure_sheet(), self._summary_sheet(),
            self._errors_sheet(), self._references_sheet(), self._lists_sheet(),
            keys_sheet({name: [(column[0], index) for index, column in enumerate(columns)]
                        for name, columns in SALE_COLUMNS.items()}, header_style=self.LABEL),
        ]
        for sheet in sheets:
            if sheet['name'] in SALE_TAB_COLORS:
                sheet['color'] = SALE_TAB_COLORS[sheet['name']]
        return {
            'version': '18.5.10', 'sheets': sheets,
            'styles': {str(key): value for key, value in styles.items()},
            'borders': {str(self.BORDER): design.HEADER_BORDER},
            'customTableStyles': design.TABLE_STYLES,
            'formats': {str(format_id): text for text, format_id in self.formats.items()},
            'lists': {}, 'listNextId': 1, 'pivots': {}, 'pivotNextId': 1,
            'revisionId': 'START_REVISION',
        }


_HELPER_BASE = len(PARTIDAS) * 2


def _helper_row(kind, row):
    """Fila de _LISTAS con la lista de ítems de una fila de PRECIOS o de METRADO."""
    return _HELPER_BASE + (row - 2) * 2 + (1 if kind == 'item' else 2)


def _range(sheet, key, last):
    letter = letter_of(sheet, key)
    return '%s!$%s$2:$%s$%s' % (sheet, letter, letter, last)
