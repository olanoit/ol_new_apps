# -*- coding: utf-8 -*-
"""Pestañas de planificación del maestro (paquete 1.13, M113-07 a M113-11).

* INICIO: estado de la hoja, ruta de 8 pasos con semáforo, indicadores,
  conteos por pestaña, dos gráficos, «Lo que falta» y un resumen por piso con
  filtros nativos.
* FICHA: una tipología con fórmulas (datos, pisos, módulos con el ancho de OT
  frente al de piezas, ML, piezas, costo por sub etapa, precio y margen).
* PROGRAMA: pre-plan por piso y semana; solo Inicio y Fin pasan a OBRA.
* CONTROL: hoja, planificador y origen (FUENTES) por piso, con su semáforo.

Todo es fórmula sobre las pestañas del maestro, con columnas completas para
que siga valiendo cuando la hoja se amplía. Lo que escribe el sistema (estado,
datos del planificador, origen) lo pone la hoja en el navegador en celdas
fijas: ``STATE_CELL``, ``CONTROL_PLANNER_COL`` y ``CONTROL_ORIGIN_COL``.
"""
from odoo import models

from .construction_sheet_parameter import parameter_formula
from .project_project import (
    CALC_STYLE, DATA_STYLE, FIXED_LISTS, HEADER_STYLE, REFERENCE_SHEET, TITLE_STYLE, _col,
    column_of, full_column, sheet_ref,
)

START_SHEET = 'INICIO'
CARD_SHEET = 'FICHA'
PROGRAM_SHEET = 'PROGRAMA'
CONTROL_SHEET = 'CONTROL'
ERRORS_SHEET = 'ERRORES'
PLANNING_SHEETS = (START_SHEET, CARD_SHEET, PROGRAM_SHEET, CONTROL_SHEET)
# Celdas que escribe el sistema o lee una acción del menú.
STATE_CELL = 'B7'
CARD_TYPOLOGY_CELL = 'B3'
CARD_PRICE_CELL = 'B22'
PROGRAM_START_CELL = 'B12'
PROGRAM_END_CELL = 'B13'
CONTROL_RESULT_CELL = 'B3'
CONTROL_FIRST_ROW = 7
CONTROL_PLANNER_COL = 'N'
CONTROL_ORIGIN_COL = 'S'
READY, MISSING = 'Listo', 'Falta'
MATCH, MISMATCH = 'Coincide', 'No coincide'
GREEN_FILL, RED_FILL = '#E3F4EC', '#F6E1E4'
# Colores de las sub etapas en PROGRAMA (se repiten si hay más).
STAGE_FILLS = ('#CFE2F3', '#FFF2CC', '#D9EAD3', '#FCE5CD', '#EAD1DC', '#D9D2E9')
# Pestañas que cuenta INICIO, con la clave de una columna obligatoria.
COUNTED_SHEETS = (
    ('ARBOL', 'space'), ('TIPOLOGIAS', 'code'), ('MUEBLES', 'name'), ('MODULOS', 'code'),
    ('ACTIVIDADES', 'activity'), ('BOM', 'product_name'), ('PIEZAS', 'qty'),
    ('PRODUCTOS NUEVOS', 'code'), ('TARIFAS', 'activity'), ('OBRA', 'key'),
    ('CONTRATOS', 'name'), ('VENTA', 'typology'), ('ETO', 'code'),
)
CARD_MODULE_ROWS = 60
PROGRAM_WEEKS = 30
PROGRAM_FLOORS = 200
SUMMARY_ROWS = 300


def _rule(rule_id, ranges, formula, fill):
    """Formato condicional por fórmula (nativo)."""
    return {'id': rule_id, 'ranges': ranges, 'stopIfTrue': False,
            'rule': {'type': 'CellIsRule', 'operator': 'customFormula', 'values': [formula],
                     'style': {'fillColor': fill}}}


def _bar_chart(chart_id, title, labels, values, col, row):
    return {
        'id': chart_id, 'tag': 'chart', 'col': col, 'row': row, 'offset': {'x': 0, 'y': 0},
        'width': 520, 'height': 300,
        'data': {
            'type': 'bar', 'chartId': chart_id, 'title': {'text': title},
            'dataSets': [{'dataRange': values}], 'labelRange': labels,
            'dataSetsHaveTitle': False, 'legendPosition': 'none', 'stacked': False,
            'aggregated': False, 'background': '#FFFFFF',
        },
    }


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _construction_planning_sheets(self, layout, rows, sheet_ids, stage_labels):
        """Pestañas INICIO, FICHA, PROGRAMA, CONTROL y ERRORES de la plantilla.

        :param sheet_ids: ``{pestaña: id}`` para los enlaces «Ir».
        :return: ``{pestaña: datos de la pestaña}`` (el formato de la hoja).
        """
        self.ensure_one()
        return {
            START_SHEET: self._construction_start_sheet(layout, rows, sheet_ids, stage_labels),
            CARD_SHEET: self._construction_card_sheet(layout, rows, stage_labels),
            PROGRAM_SHEET: self._construction_program_sheet(layout, stage_labels),
            CONTROL_SHEET: self._construction_control_sheet(layout),
            ERRORS_SHEET: {
                'name': ERRORS_SHEET, 'colNumber': 8, 'rowNumber': 500,
                'cells': {'A1': self.env._('Sin validar: menú Planificación de obra › Validar'),
                          'A2': 'Hoja', 'B2': 'Fila', 'C2': 'Columna', 'D2': 'Mensaje',
                          'E2': 'Tipo', 'F2': 'Ir'},
                'styles': dict({'A1': TITLE_STYLE},
                               **{'%s2' % c: HEADER_STYLE for c in 'ABCDEF'}),
                'cols': {'3': {'size': 520}},
            },
        }

    # ------------------------------------------------------------------
    # INICIO (M113-07)
    # ------------------------------------------------------------------
    def _construction_start_sheet(self, layout, rows, sheet_ids, stage_labels):
        cells, styles = {}, {}
        last = rows + 1

        def col(sheet, key):
            return full_column(layout, sheet, key)

        def rng(sheet, key):
            letter = column_of(layout, sheet, key)
            return '%s!$%s$2:$%s$%s' % (sheet_ref(sheet), letter, letter, last)

        def obra(key):
            return 'IFERROR(XLOOKUP("%s",%s,%s),"")' % (key, col('OBRA', 'key'),
                                                         col('OBRA', 'value'))

        def link(sheet):
            sheet_id = sheet_ids.get(sheet)
            return '=HYPERLINK("o-spreadsheet://%s","%s")' % (sheet_id, sheet) if sheet_id \
                else sheet

        cells['A1'] = self.env._('Planificación de la obra')
        styles['A1'] = TITLE_STYLE
        partner = (self.partner_id.name or '').replace('"', '')
        header = [
            ('A3', self.env._('Obra'), self.name),
            ('A4', self.env._('Cliente'), '=IF(%s="","%s",%s)' % (obra('Cliente'), partner,
                                                                  obra('Cliente'))),
            ('A5', self.env._('Perfil'), self.construction_profile_id.name or ''),
            ('A6', self.env._('Contrato'), '=IFERROR(INDEX(%s,2)&"","")' % col(
                'CONTRATOS', 'name')),
            ('A7', self.env._('Estado de la hoja'), self.env._('Borrador')),
            ('A8', self.env._('Hoja de venta'), '=%s&""' % obra('Hoja de venta')),
            ('A9', self.env._('Parámetros cambiados'),
             '=SUMPRODUCT((PARAMETROS!$C$2:$C$40<>"")*(PARAMETROS!$C$2:$C$40<>PARAMETROS!$F$2:$F$40))'),
        ]
        for ref, label, value in header:
            cells[ref] = label
            styles[ref] = HEADER_STYLE
            cells['B%s' % ref[1:]] = value

        # Ruta de planificación (M117-16, punto 8): paso, qué se hace, ir, estado y
        # qué falta. El primer paso pendiente se marca «Siguiente».
        cells['A10'] = self.env._('Ruta de planificación')
        styles['A10'] = TITLE_STYLE
        for letter, text in zip('ABCDE', (self.env._('Paso'), self.env._('Qué se hace'),
                                          self.env._('Ir'), self.env._('Estado'),
                                          self.env._('Qué falta'))):
            cells['%s11' % letter] = text
            styles['%s11' % letter] = HEADER_STYLE
        in_site = rng('TIPOLOGIAS', '#En la obra (calc.)')
        finish = "'ACABADOS DE OBRA'!$%s$2:$%s$61"
        has_sale = '%s<>""' % obra('Hoja de venta')
        steps = [
            (self.env._('Traer la venta'), self.env._('Lo vendido llega a la hoja'), 'OBRA',
             'IF(%s,%s<>"",AND(%s<>"",%s<>"",%s<>""))' % (
                 has_sale, obra('Venta traída el'), obra('Inicio'), obra('Fin'), obra('Cliente')),
             False, self.env._('Traiga la venta, o llene Inicio, Fin y Cliente')),
            (self.env._('Tablero de cada acabado'), self.env._('El producto de cada acabado vendido'),
             'ACABADOS DE OBRA',
             'SUMPRODUCT((%s<>"")*(%s=""))=0' % (finish % ('A', 'A'), finish % ('G', 'G')),
             '%s=FALSE' % has_sale, self.env._('Hay acabados sin tablero')),
            (self.env._('Muebles y módulos del ETO'), self.env._('Árbol, tipologías y módulos'),
             'MODULOS',
             'AND(COUNTA(%s)>1,COUNTIF(%s,"Falta")=0,COUNTIFS(%s,">0",%s,0)=0,'
             'COUNTIFS(ERRORES!$A:$A,"ARBOL",ERRORES!$E:$E,"Error")=0)' % (
                 col('TIPOLOGIAS', 'code'), col('ARBOL', '#Módulos (calc.)'), in_site,
                 rng('TIPOLOGIAS', '#Módulos (calc.)')),
             False, self.env._('Cada tipología del ARBOL tiene MODULOS')),
            (self.env._('Materiales y piezas'), self.env._('BOM y PIEZAS de cada módulo'), 'BOM',
             'AND(COUNTA(%s)>1,COUNTIFS(%s,">0",%s,0)=0,SUMPRODUCT((%s<>"")*(%s=""))=0)' % (
                 col('BOM', 'product_name'), in_site,
                 rng('TIPOLOGIAS', '#Costo de materiales (calc.)'),
                 rng('BOM', 'product_name'), rng('BOM', '#Etapa usada (calc.)')),
             False, self.env._('Cada módulo tiene BOM con etapa')),
            (self.env._('Actividades a hitos'), self.env._('Contratas, contrato y precios'), 'TARIFAS',
             'AND(COUNTA(%s)>1,COUNTIF(%s,0)=0,COUNTA(%s)>1,COUNTIFS(%s,">0",%s,0)=0)' % (
                 col('TARIFAS', 'activity'), col('ACTIVIDADES', '#Tarifa (calc.)'),
                 col('VENTA', 'price'), in_site, rng('TIPOLOGIAS', '#Precio (calc.)')),
             False, self.env._('TARIFAS tiene cada actividad y VENTA cada tipología')),
            (self.env._('Programa por piso'), self.env._('Fecha de inicio y ritmo'), PROGRAM_SHEET,
             'AND(PROGRAMA!$B$3<>"",IFERROR(PROGRAMA!$B$4>0,FALSE))',
             False, self.env._('PROGRAMA tiene fecha de inicio y ritmo')),
            (self.env._('Validar y enviar'), self.env._('Última validación sin errores'), ERRORS_SHEET,
             'AND(LEFT(ERRORES!$A$1,7)="Validad",ISNUMBER(SEARCH("· 0 errores",ERRORES!$A$1)))',
             False, self.env._('Menú Planificación de obra › Validar')),
        ]
        first_step = 12
        for index, (name, what, sheet, condition, not_applicable, missing) in enumerate(steps):
            row = first_step + index
            cells['A%s' % row] = '%s · %s' % (index + 1, name)
            cells['B%s' % row] = what
            cells['C%s' % row] = link(sheet)
            state = '=IFERROR(IF(%s,"%s","%s"),"%s")' % (condition, READY, MISSING, MISSING)
            if not_applicable:
                state = '=IF(%s,"—",%s)' % (not_applicable, state[1:])
            cells['D%s' % row] = state
            previous = 'COUNTIF($D$%s:D%s,"%s")=0' % (first_step, row - 1, MISSING) \
                if index else 'TRUE'
            cells['E%s' % row] = '=IF(D{r}<>"{m}","",IF({p},"◀ Siguiente · ","")&"{t}")'.format(
                r=row, m=MISSING, p=previous, t=missing)
        last_step = first_step + len(steps) - 1
        status = 'D%s:D%s' % (first_step, last_step)
        conditional = [
            _rule('start_ready', [status], '=D%s="%s"' % (first_step, READY), GREEN_FILL),
            _rule('start_missing', [status], '=D%s="%s"' % (first_step, MISSING), RED_FILL),
        ]

        # Indicadores.
        cells['A21'] = self.env._('Indicadores')
        styles['A21'] = TITLE_STYLE
        tip = lambda key: rng('TIPOLOGIAS', key)  # noqa: E731
        indicators = [
            (self.env._('Muebles a producir'), '=MAX(COUNTA(%s)-1,0)' % col('ARBOL', 'space')),
            (self.env._('Módulos a armar (sin zócalos)'),
             '=SUM(%s)' % col('ARBOL', '#Módulos (calc.)')),
            (self.env._('ML a instalar'), '=SUM(%s)' % col('ARBOL', '#ML (calc.)')),
            (self.env._('Piezas'), '=SUMPRODUCT(%s,%s)' % (in_site, tip('#Piezas (calc.)'))),
            (self.env._('Costo de materiales (costo vivo)'),
             '=SUM(%s)' % col('BOM', '#Costo en la obra (calc.)')),
            (self.env._('Contratas'), '=SUM(%s)' % col('ACTIVIDADES',
                                                       '#Costo en la obra (calc.)')),
            (self.env._('Venta'), '=SUMPRODUCT(%s,%s)' % (in_site, tip('#Precio (calc.)'))),
            (self.env._('Margen'), '=IF(B28=0,"",B28-B26-B27)'),
        ]
        for row, (label, formula) in enumerate(indicators, start=22):
            cells['A%s' % row] = label
            cells['B%s' % row] = formula
        cells['C29'] = '=IF(B28=0,"",B29/B28)'
        formats = {'B26': '#,##0.00', 'B27': '#,##0.00', 'B28': '#,##0.00', 'B29': '#,##0.00',
                   'C29': '0.0%', 'B24': '#,##0.00'}

        # Conteos por pestaña (el nombre de la pestaña no admite un conteo).
        cells['F10'] = self.env._('Pestañas')
        styles['F10'] = TITLE_STYLE
        for letter, text in zip('FGHI', (self.env._('Pestaña'), self.env._('Filas'),
                                         self.env._('Errores'), self.env._('Avisos'))):
            cells['%s11' % letter] = text
            styles['%s11' % letter] = HEADER_STYLE
        for row, (sheet, key) in enumerate(COUNTED_SHEETS, start=12):
            cells['F%s' % row] = link(sheet)
            cells['G%s' % row] = '=MAX(COUNTA(%s)-1,0)' % col(sheet, key)
            cells['H%s' % row] = '=COUNTIFS(ERRORES!$A:$A,"%s",ERRORES!$E:$E,"Error")' % sheet
            cells['I%s' % row] = '=COUNTIFS(ERRORES!$A:$A,"%s",ERRORES!$E:$E,"Aviso")' % sheet

        # Lo que falta: una fila por paso no listo.
        cells['F27'] = self.env._('Lo que falta')
        styles['F27'] = TITLE_STYLE
        cells['F28'] = '=IFERROR(FILTER(A{f}:A{l}&": "&E{f}:E{l},D{f}:D{l}="{m}"),"{ok}")'.format(
            f=first_step, l=last_step, m=MISSING,
            ok=self.env._('Nada: la hoja está lista para enviar'))

        # Gráficos: costo de materiales por sub etapa y muebles por rubro.
        cells['A31'] = self.env._('Costo de materiales por sub etapa')
        styles['A31'] = TITLE_STYLE
        stage_rows = max(len(stage_labels), 1)
        for row, label in enumerate(stage_labels, start=32):
            cells['A%s' % row] = label
            cells['B%s' % row] = '=SUMIFS(%s,%s,A%s)' % (
                col('BOM', '#Costo en la obra (calc.)'), col('BOM', 'stage'), row)
            formats['B%s' % row] = '#,##0.00'
        families = FIXED_LISTS[('TIPOLOGIAS', 'family')]
        cells['D31'] = self.env._('Muebles por rubro')
        styles['D31'] = TITLE_STYLE
        for row, family in enumerate(families, start=32):
            cells['D%s' % row] = family
            cells['E%s' % row] = '=SUMIFS(%s,%s,D%s)' % (in_site, rng('TIPOLOGIAS', 'family'),
                                                       row)
        figures = [
            _bar_chart('al_start_stage_cost', self.env._('Costo de materiales por sub etapa'),
                       'A32:A%s' % (31 + stage_rows), 'B32:B%s' % (31 + stage_rows), 10, 1),
            _bar_chart('al_start_family', self.env._('Muebles por rubro'),
                       'D32:D%s' % (31 + len(families)), 'E32:E%s' % (31 + len(families)), 10,
                       17),
        ]

        # Resumen por piso con filtros nativos (torre, piso y rubro). La clave
        # del piso («Torre A / Piso 3») viene de ARBOL: los vacíos de un rango
        # derramado valen 0 y no sirven de criterio.
        top = 42
        cells['A%s' % top] = self.env._('Resumen por piso: filtre por torre, piso o rubro')
        styles['A%s' % top] = TITLE_STYLE
        head = top + 1
        for letter, text in zip('ABCDEFG', (self.env._('Torre'), self.env._('Piso'),
                                            self.env._('Rubro'), self.env._('Piso con torre'),
                                            self.env._('Muebles'), self.env._('Módulos'),
                                            self.env._('ML'))):
            cells['%s%s' % (letter, head)] = text
            styles['%s%s' % (letter, head)] = HEADER_STYLE
        first = head + 1
        cells['A%s' % first] = '=IFERROR(UNIQUE(FILTER(HSTACK(%s,%s,%s,%s),%s<>"")),"")' % (
            rng('ARBOL', 'group'), rng('ARBOL', 'floor'), rng('ARBOL', '#Rubro (calc.)'),
            rng('ARBOL', '#Piso (calc.)'), rng('ARBOL', 'floor'))
        for row in range(first, first + SUMMARY_ROWS):
            criteria = '%s,D%s&"",%s,C%s&""' % (col('ARBOL', '#Piso (calc.)'), row,
                                                col('ARBOL', '#Rubro (calc.)'), row)
            cells['E%s' % row] = '=IF(D%s="","",COUNTIFS(%s))' % (row, criteria)
            cells['F%s' % row] = '=IF(D%s="","",SUMIFS(%s,%s))' % (
                row, col('ARBOL', '#Módulos (calc.)'), criteria)
            cells['G%s' % row] = '=IF(D%s="","",SUMIFS(%s,%s))' % (
                row, col('ARBOL', '#ML (calc.)'), criteria)
        tables = [{'range': 'A%s:G%s' % (head, first + SUMMARY_ROWS - 1), 'type': 'static',
                   'config': {'hasFilters': True, 'totalRow': False, 'firstColumn': False,
                              'lastColumn': False, 'numberOfHeaders': 1, 'bandedRows': True,
                              'bandedColumns': False, 'automaticAutofill': False,
                              'styleId': 'TableStyleLight1'}}]
        return {
            'name': START_SHEET, 'colNumber': 20, 'rowNumber': first + SUMMARY_ROWS + 10,
            'cells': cells, 'styles': styles, 'formats': formats,
            'cols': {'0': {'size': 230}, '1': {'size': 200}, '2': {'size': 320},
                     '5': {'size': 160}},
            'conditionalFormats': conditional, 'figures': figures, 'tables': tables,
        }

    # ------------------------------------------------------------------
    # FICHA (M113-09)
    # ------------------------------------------------------------------
    def _construction_card_sheet(self, layout, rows, stage_labels):
        cells, styles = {}, {}
        last = rows + 1
        typology = '$%s$%s' % (CARD_TYPOLOGY_CELL[0], CARD_TYPOLOGY_CELL[1:])

        def col(sheet, key):
            return full_column(layout, sheet, key)

        def tip(key):
            return 'IFERROR(XLOOKUP(%s,%s,%s),"")' % (typology, col('TIPOLOGIAS', 'code'),
                                                      col('TIPOLOGIAS', key))

        cells['A1'] = self.env._('Ficha de tipología')
        styles['A1'] = TITLE_STYLE
        cells['A3'] = self.env._('Tipología')
        styles['A3'] = HEADER_STYLE
        styles[CARD_TYPOLOGY_CELL] = DATA_STYLE
        cells['C3'] = self.env._('‹ Anterior y Siguiente ›: menú Planificación de obra')
        ml = lambda *groups: '+'.join(  # noqa: E731
            'SUMIFS(%s,%s,%s,%s,"%s")' % (col('MODULOS', '#ML (calc.)'), col('MODULOS', 'typology'),
                                         typology, col('MODULOS', 'ml_group'), group)
            for group in groups)
        lines = [
            (self.env._('Nombre'), '=IF(%s="","",IFERROR(XLOOKUP(%s,%s,%s),"%s"))' % (
                typology, typology, col('TIPOLOGIAS', 'code'), col('TIPOLOGIAS', 'name'),
                self.env._('No está en TIPOLOGIAS'))),
            (self.env._('Familia'), '=%s' % tip('family')),
            (self.env._('Variante de'), '=%s' % tip('variant_of')),
            (self.env._('En la obra'), '=%s' % tip('#En la obra (calc.)')),
            (self.env._('Pisos'), '=IF(%s="","",IFERROR(TEXTJOIN(", ",TRUE,UNIQUE(FILTER(%s,%s=%s'
                                  '))),""))' % (typology, col('ARBOL', '#Piso (calc.)'),
                                               col('ARBOL', 'typology'), typology)),
            (self.env._('Módulos'), '=%s' % tip('#Módulos (calc.)')),
            (self.env._('Módulos a armar'), '=%s' % tip('#Módulos a armar (calc.)')),
            (self.env._('ML bajo'), '=%s' % ml('Mueble bajo', 'Bajo')),
            (self.env._('ML alto'), '=%s' % ml('Mueble alto', 'Alto')),
            (self.env._('ML de mueble completo'), '=%s' % ml('Mueble completo', 'Completo')),
            (self.env._('ML total'), '=%s' % tip('#ML (calc.)')),
            (self.env._('Piezas'), '=%s' % tip('#Piezas (calc.)')),
            (self.env._('Costo por unidad'), '=%s' % tip('#Costo de materiales (calc.)')),
            (self.env._('Costo en la obra'), '=IFERROR(B17*B8,"")'),
            (self.env._('Precio por ambiente (VENTA)'), '=%s' % tip('#Precio (calc.)')),
            (self.env._('Margen por unidad'), '=IF(IFERROR(VALUE(B19),0)=0,"",B19-B17)'),
        ]
        formats = {}
        for row, (label, formula) in enumerate(lines, start=5):
            cells['A%s' % row] = label
            cells['B%s' % row] = formula
            styles['A%s' % row] = HEADER_STYLE
        for row in (17, 18, 19, 20):
            formats['B%s' % row] = '#,##0.00'
        cells['A22'] = self.env._('Precio nuevo por ambiente')
        styles['A22'] = HEADER_STYLE
        styles[CARD_PRICE_CELL] = DATA_STYLE
        # M117-22, punto 9: los ML vendidos junto a los de los módulos.
        cells['A23'] = self.env._('ML vendidos')
        cells['B23'] = '=SUMIF(VENDIDO!$A$2:$A$300,$B$3,VENDIDO!$D$2:$D$300)'
        styles['A23'] = HEADER_STYLE
        formats['B23'] = '#,##0.00'
        cells['C22'] = self.env._('Menú Planificación de obra › Escribir el precio en VENTA')

        # Costo por sub etapa.
        cells['D4'] = self.env._('Costo por sub etapa (una unidad)')
        styles['D4'] = TITLE_STYLE
        for row, label in enumerate(stage_labels, start=5):
            cells['D%s' % row] = label
            cells['E%s' % row] = '=IF(%s="","",SUMIFS(%s,%s,%s,%s,D%s))' % (
                typology, col('BOM', '#Costo de la línea (calc.)'), col('BOM', 'typology'),
                typology, col('BOM', 'stage'), row)
            formats['E%s' % row] = '#,##0.00'

        # Módulos: ancho de OT frente al de las piezas (base, tapa o techo).
        top = 25
        cells['A%s' % top] = self.env._('Módulos de la tipología')
        styles['A%s' % top] = TITLE_STYLE
        heads = (self.env._('Módulo'), self.env._('Nombre'), self.env._('Grupo ML'),
                 self.env._('Ancho OT (mm)'), self.env._('Ancho de piezas (mm)'),
                 self.env._('Piezas'), self.env._('Observación'))
        for letter, text in zip('ABCDEFG', heads):
            cells['%s%s' % (letter, top + 1)] = text
            styles['%s%s' % (letter, top + 1)] = HEADER_STYLE
        first = top + 2
        cells['A%s' % first] = '=IF(%s="","",IFERROR(FILTER(%s,%s=%s),""))' % (
            typology, col('MODULOS', 'code'), col('MODULOS', 'typology'), typology)

        def module_value(key, row):
            return 'IFERROR(INDEX(FILTER(%s,%s=%s,%s=$A%s),1),"")' % (
                col('MODULOS', key), col('MODULOS', 'typology'), typology,
                col('MODULOS', 'code'), row)

        piece_width = ','.join(
            'MAXIFS(%s,%s,%s,%s,$A{r},%s,"%s")' % (
                col('PIEZAS', 'length'), col('PIEZAS', 'typology'), typology,
                col('PIEZAS', 'module'), col('PIEZAS', 'piece_type'), kind)
            for kind in ('BASE', 'TAPA', 'TECHO'))
        for row in range(first, first + CARD_MODULE_ROWS):
            cells['B%s' % row] = '=IF($A%s="","",%s)' % (row, module_value('name', row))
            cells['C%s' % row] = '=IF($A%s="","",%s)' % (row, module_value('ml_group', row))
            cells['D%s' % row] = '=IF($A%s="","",%s)' % (row, module_value('width', row))
            cells['E%s' % row] = '=IF($A{r}="","",MAX({w}))'.format(
                r=row, w=piece_width.replace('{r}', str(row)))
            cells['F%s' % row] = '=IF($A%s="","",SUMIFS(%s,%s,%s,%s,$A%s))' % (
                row, col('PIEZAS', 'qty'), col('PIEZAS', 'typology'), typology,
                col('PIEZAS', 'module'), row)
            cells['G%s' % row] = (
                '=IF($A{r}="","",IF(D{r}="","{no_ot}",IF(AND(E{r}>0,E{r}<>D{r}),"{dispute}",'
                '"")))').format(r=row, no_ot=self.env._('Sin medida de OT'),
                                dispute=self.env._('Controversia de ancho'))
        last_module = first + CARD_MODULE_ROWS - 1
        conditional = [_rule('card_dispute', ['G%s:G%s' % (first, last_module)],
                             '=AND(G%s<>"",G%s<>"")' % (first, first), RED_FILL)]
        rules = [{
            'id': 'card_typology', 'isBlocking': False, 'ranges': [CARD_TYPOLOGY_CELL],
            'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                          'values': ['TIPOLOGIAS!$%s$2:$%s$%s' % (
                              column_of(layout, 'TIPOLOGIAS', 'code'),
                              column_of(layout, 'TIPOLOGIAS', 'code'), last)]},
        }]
        return {
            'name': CARD_SHEET, 'colNumber': 12, 'rowNumber': last_module + 10, 'cells': cells,
            'styles': styles, 'formats': formats, 'conditionalFormats': conditional,
            'dataValidationRules': rules,
            'cols': {'0': {'size': 200}, '1': {'size': 220}, '2': {'size': 200},
                     '3': {'size': 200}, '6': {'size': 180}},
        }

    # ------------------------------------------------------------------
    # PROGRAMA (M113-10)
    # ------------------------------------------------------------------
    def _construction_program_stage(self, stage_labels):
        """Sub etapa de instalación propuesta: la del catálogo que se llama
        así; el usuario la cambia en la lista."""
        for stage in self.env['construction.stage']._offered_stages(self):
            if 'instal' in (stage.name or '').lower() and stage._label() in stage_labels:
                return stage._label()
        return stage_labels[min(2, len(stage_labels) - 1)] if stage_labels else ''

    def _construction_program_sheet(self, layout, stage_labels):
        cells, styles, formats = {}, {}, {}
        n_stages = max(len(stage_labels), 1)
        stages = '%s!$T$3:$T$%s' % (REFERENCE_SHEET, n_stages + 2)
        cells['A1'] = self.env._('Programa por piso y sub etapa (pre-plan)')
        styles['A1'] = TITLE_STYLE
        inputs = [
            (self.env._('Inicio de producción (lunes)'), ''),
            (self.env._('Pisos por semana'), '2'),
            (self.env._('Días por sub etapa'), '5'),
            (self.env._('Orden de pisos'), self.env._('Como en ARBOL')),
            (self.env._('Sub etapa de instalación'), self._construction_program_stage(
                stage_labels)),
        ]
        for row, (label, value) in enumerate(inputs, start=3):
            cells['A%s' % row] = label
            styles['A%s' % row] = HEADER_STYLE
            cells['B%s' % row] = value
            styles['B%s' % row] = DATA_STYLE
        formats['B3'] = 'dd/mm/yyyy'
        # Calculados: semanas por sub etapa, sub etapas, pisos, semanas, inicio
        # y fin (lunes a viernes).
        floors = full_column(layout, 'ARBOL', '#Piso (calc.)')
        calculated = [
            (self.env._('Semanas por sub etapa'), '=MAX(1,ROUNDUP(IFERROR(VALUE(B5),%s)/%s,0))' % (
                parameter_formula('dias_sub_etapa'), parameter_formula('dias_semana'))),
            (self.env._('Sub etapas'), '=MAX(1,COUNTA(%s))' % stages),
            (self.env._('Pisos'), '=IFERROR(ROWS(UNIQUE(FILTER(%s,%s<>"",ROW(%s)>1))),0)' % (
                floors, floors, floors)),
            (self.env._('Semanas'), '=IF(B10<=0,0,INT((B10-1)/MAX(1,B4))+B9*B8)'),
            (self.env._('Inicio'), '=IF(B3="","",B3)'),
            (self.env._('Fin estimado'), '=IF(OR(B3="",B11=0),"",B3+B11*7-(8-%s))' % (
                parameter_formula('dias_semana'))),
        ]
        for row, (label, formula) in enumerate(calculated, start=8):
            cells['A%s' % row] = label
            styles['A%s' % row] = HEADER_STYLE
            cells['B%s' % row] = formula
            styles['B%s' % row] = CALC_STYLE
        formats.update({PROGRAM_START_CELL: 'dd/mm/yyyy', PROGRAM_END_CELL: 'dd/mm/yyyy'})
        cells['C%s' % PROGRAM_END_CELL[1:]] = self.env._('Menú Planificación de obra › Escribir fechas en OBRA')

        # Matriz piso × semana.
        week_row, date_row, ml_row = 15, 16, 17
        first = 18
        cells['A%s' % week_row] = self.env._('Semana')
        cells['A%s' % date_row] = self.env._('Lunes')
        cells['A%s' % ml_row] = self.env._('ML en instalación')
        cells['B%s' % week_row] = self.env._('ML del piso')
        for row in (week_row, date_row, ml_row):
            styles['A%s' % row] = HEADER_STYLE
        floor_list = 'UNIQUE(FILTER(%s,%s<>"",ROW(%s)>1))' % (floors, floors, floors)
        cells['A%s' % first] = (
            '=IFERROR(IF(B6="{rev}",INDEX({l},SEQUENCE(B10,1,B10,-1)),{l}),"")'.format(
                rev=self.env._('Inverso'), l=floor_list))
        last_floor = first + PROGRAM_FLOORS - 1
        ml_col = full_column(layout, 'ARBOL', '#ML (calc.)')
        install = 'IFERROR(MATCH($B$7,%s,0),0)' % stages
        weeks = [_col(index + 2) for index in range(PROGRAM_WEEKS)]
        for index, letter in enumerate(weeks, start=1):
            cells['%s%s' % (letter, week_row)] = str(index)
            styles['%s%s' % (letter, week_row)] = HEADER_STYLE
            cells['%s%s' % (letter, date_row)] = '=IF($B$3="","",$B$3+%s)' % ((index - 1) * 7)
            formats['%s%s' % (letter, date_row)] = 'dd/mm'
            cells['%s%s' % (letter, ml_row)] = '=SUMIFS($B${f}:$B${l},{c}${f}:{c}${l},{i})'.format(
                f=first, l=last_floor, c=letter, i=install)
        for row in range(first, last_floor + 1):
            cells['B%s' % row] = '=IF($A{r}="","",SUMIFS({ml},{fl},$A{r}))'.format(
                r=row, ml=ml_col, fl=floors)
            # Orden del piso en la lista (0 = el primero) y su semana de inicio.
            start = '(INT(%s/MAX(1,$B$4))+1)' % (row - first)
            for letter in weeks:
                stage = 'INT(({c}${w}-{s})/$B$8)+1'.format(c=letter, w=week_row, s=start)
                cells['%s%s' % (letter, row)] = (
                    '=IF(OR($A{r}="",$B$3=""),"",IF(AND({c}${w}>={s},{st}<=$B$9),{st},""))'
                ).format(r=row, c=letter, w=week_row, s=start, st=stage)
        matrix = '%s%s:%s%s' % (weeks[0], first, weeks[-1], last_floor)
        conditional = [
            _rule('program_stage_%s' % number, [matrix], '=%s%s=%s' % (weeks[0], first, number),
                  STAGE_FILLS[(number - 1) % len(STAGE_FILLS)])
            for number in range(1, n_stages + 1)]
        rules = [
            {'id': 'program_order', 'isBlocking': False, 'ranges': ['B6'],
             'criterion': {'type': 'isValueInList', 'displayStyle': 'arrow',
                           'values': [self.env._('Como en ARBOL'), self.env._('Inverso')]}},
            {'id': 'program_install', 'isBlocking': False, 'ranges': ['B7'],
             'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                           'values': [stages]}},
        ]
        cols = {'0': {'size': 220}, '1': {'size': 110}}
        cols.update({str(2 + index): {'size': 48} for index in range(PROGRAM_WEEKS)})
        return {
            'name': PROGRAM_SHEET, 'colNumber': PROGRAM_WEEKS + 4,
            'rowNumber': last_floor + 10, 'cells': cells, 'styles': styles, 'formats': formats,
            'conditionalFormats': conditional, 'dataValidationRules': rules, 'cols': cols,
            'panes': {'xSplit': 2, 'ySplit': first - 1},
        }

    # ------------------------------------------------------------------
    # CONTROL (M113-11)
    # ------------------------------------------------------------------
    def _construction_control_sheet(self, layout):
        cells, styles, formats = {}, {}, {}
        floors = full_column(layout, 'ARBOL', '#Piso (calc.)')
        cells['A1'] = self.env._('Control de alcance por piso')
        styles['A1'] = TITLE_STYLE
        cells['A3'] = self.env._('Resultado')
        styles['A3'] = HEADER_STYLE
        first = CONTROL_FIRST_ROW
        last = first + PROGRAM_FLOORS - 1
        # Coincide solo si cada piso de la hoja coincide y el planificador no
        # tiene otros pisos.
        cells['L3'] = self.env._('Pisos en la hoja')
        cells['M3'] = '=IFERROR(ROWS(UNIQUE(FILTER(%s,%s<>"",ROW(%s)>1))),0)' % (
            floors, floors, floors)
        cells['L4'] = self.env._('Pisos en el planificador')
        cells['M4'] = '=COUNTIF(N{f}:N{l},"?*")'.format(f=first, l=last)
        cells[CONTROL_RESULT_CELL] = (
            '=IF(M4=0,"{pending}",IF(AND(M4=M3,COUNTIF(K{f}:K{l},"{m}")=M3),"{m}","{mm}"))'
        ).format(f=first, l=last, m=MATCH, mm=MISMATCH,
                 pending=self.env._('Sin datos del planificador: menú › Actualizar CONTROL'))
        cells['C3'] = self.env._(
            'Coincide: muebles y módulos iguales y ML con 0.5 % de diferencia o menos.')
        cells['A4'] = self.env._('Actualizado')
        styles['A4'] = HEADER_STYLE
        groups = [('B', self.env._('Hoja')), ('E', self.env._('Planificador')),
                  ('H', self.env._('Origen (FUENTES)'))]
        for letter, text in groups:
            cells['%s5' % letter] = text
            styles['%s5' % letter] = TITLE_STYLE
        heads = ['Piso'] + [self.env._('Muebles'), self.env._('Módulos'), 'ML'] * 3 + [
            self.env._('Resultado')]
        for index, text in enumerate(heads):
            letter = chr(65 + index)
            cells['%s6' % letter] = text
            styles['%s6' % letter] = HEADER_STYLE
        # Datos que escribe la hoja: planificador (N:Q) y origen (S:V).
        for letter, text in ((CONTROL_PLANNER_COL, self.env._('Planificador: piso')),
                             (CONTROL_ORIGIN_COL, self.env._('Origen: piso'))):
            start = ord(letter) - 65
            for offset, head in enumerate((text, self.env._('Muebles'), self.env._('Módulos'),
                                           'ML')):
                ref = '%s6' % chr(65 + start + offset)
                cells[ref] = head
                styles[ref] = CALC_STYLE
        cells['A%s' % first] = '=IFERROR(UNIQUE(FILTER(%s,%s<>"",ROW(%s)>1)),"")' % (
            floors, floors, floors)
        modules = full_column(layout, 'ARBOL', '#Módulos (calc.)')
        ml = full_column(layout, 'ARBOL', '#ML (calc.)')

        def lookup(block, offset, row):
            key_col = block
            value_col = chr(ord(block) + offset)
            return 'IFERROR(XLOOKUP($A{r},${k}${f}:${k}${l},${v}${f}:${v}${l}),"")'.format(
                r=row, k=key_col, v=value_col, f=first, l=last)

        for row in range(first, last + 1):
            cells['B%s' % row] = '=IF($A%s="","",COUNTIF(%s,$A%s))' % (row, floors, row)
            cells['C%s' % row] = '=IF($A%s="","",SUMIFS(%s,%s,$A%s))' % (row, modules, floors,
                                                                         row)
            cells['D%s' % row] = '=IF($A%s="","",ROUND(SUMIFS(%s,%s,$A%s),2))' % (
                row, ml, floors, row)
            for letter, offset in (('E', 1), ('F', 2), ('G', 3)):
                cells['%s%s' % (letter, row)] = '=IF($A%s="","",%s)' % (
                    row, lookup(CONTROL_PLANNER_COL, offset, row))
            for letter, offset in (('H', 1), ('I', 2), ('J', 3)):
                cells['%s%s' % (letter, row)] = '=IF($A%s="","",%s)' % (
                    row, lookup(CONTROL_ORIGIN_COL, offset, row))
            cells['K%s' % row] = (
                '=IF(OR($A{r}="",E{r}=""),"",IF(AND(B{r}=E{r},C{r}=F{r},ABS(D{r}-G{r})<='
                '{t}*MAX(D{r},G{r})),"{m}","{mm}"))').format(
                r=row, m=MATCH, mm=MISMATCH, t=parameter_formula('tolerancia_ml'))
        # M117-22, punto 9: lo planificado frente a lo vendido (X:AB).
        tree = full_column(layout, 'ARBOL', 'apartment')
        factor_cell = 'CONTRATOS!$%s$2' % column_of(layout, 'CONTRATOS', 'discount_factor')
        rng = lambda sheet, key: '%s!$%s$2:$%s$%s' % (
            sheet_ref(sheet), column_of(layout, sheet, key), column_of(layout, sheet, key), 501)
        sale_value = lambda name: 'IFERROR(XLOOKUP("%s",%s,%s),"")' % (
            name, full_column(layout, 'OBRA', 'key'), full_column(layout, 'OBRA', 'value'))
        cells.update({
            'X4': self.env._('Venta frente a planificación'),
            'X3': self.env._('Total valorizable / subtotal de la cotización'),
            'Y3': '=IFERROR(SUMPRODUCT(%s,%s)*IF(%s="",1,%s),0)' % (
                rng('TIPOLOGIAS', '#En la obra (calc.)'), rng('TIPOLOGIAS', '#Precio (calc.)'),
                factor_cell, factor_cell),
            'Z3': '=%s' % sale_value('Subtotal de la cotización'),
            'AB3': '=IF(Z3="","",IF(ABS(Y3-Z3)<=0.05,"%s","%s"))' % (MATCH, MISMATCH),
            'X5': self.env._('Departamentos: árbol / vendidos'),
            'Y5': '=IFERROR(COUNTA(UNIQUE(FILTER(%s,%s<>"",ROW(%s)>1))),0)' % (tree, tree, tree),
            'Z5': '=%s' % sale_value('Departamentos vendidos'),
            'AB5': '=IF(Z5="","",IF(Y5=Z5,"%s","%s"))' % (MATCH, MISMATCH),
            'X6': self.env._('Tipología'), 'Y6': self.env._('ML vendidos'),
            'Z6': self.env._('ML de módulos'), 'AA6': self.env._('Diferencia'),
            'AB6': self.env._('Resultado'),
            'X%s' % first: '=IFERROR(UNIQUE(FILTER(VENDIDO!$A$2:$A$300,VENDIDO!$A$2:$A$300<>"")),"")',
        })
        styles['X4'] = TITLE_STYLE
        for ref in ('X3', 'X5', 'X6', 'Y6', 'Z6', 'AA6', 'AB6'):
            styles[ref] = HEADER_STYLE
        typology_ml = full_column(layout, 'TIPOLOGIAS', '#ML (calc.)')
        typology_code = full_column(layout, 'TIPOLOGIAS', 'code')
        tolerance = parameter_formula('tolerancia_ml_venta')
        for row in range(first, last + 1):
            cells['Y%s' % row] = '=IF($X{r}="","",SUMIF(VENDIDO!$A$2:$A$300,$X{r},VENDIDO!$D$2:$D$300))'.format(r=row)
            cells['Z%s' % row] = '=IF($X{r}="","",IFERROR(XLOOKUP($X{r},{c},{m}),0))'.format(
                r=row, c=typology_code, m=typology_ml)
            cells['AA%s' % row] = '=IF($X{r}="","",Z{r}-Y{r})'.format(r=row)
            cells['AB%s' % row] = ('=IF($X{r}="","",IF(Y{r}=0,"—",IF(ABS(AA{r})<={t}*Y{r},"{m}",'
                                   '"{mm}")))').format(r=row, t=tolerance, m=MATCH, mm=MISMATCH)
        result = 'K%s:K%s' % (first, last)
        conditional = [
            _rule('control_sold', ['AB3:AB%s' % last],
                  '=AB3="%s"' % MISMATCH, '#FCE5CD'),
            _rule('control_match', [result, CONTROL_RESULT_CELL],
                  '=K%s="%s"' % (first, MATCH), GREEN_FILL),
            _rule('control_mismatch', [result], '=K%s="%s"' % (first, MISMATCH), RED_FILL),
        ]
        cells['A%s' % (last + 2)] = self.env._('Total')
        styles['A%s' % (last + 2)] = HEADER_STYLE
        for letter in 'BCDEFGHIJ':
            cells['%s%s' % (letter, last + 2)] = '=SUM(%s%s:%s%s)' % (letter, first, letter, last)
        return {
            'name': CONTROL_SHEET, 'colNumber': 24, 'rowNumber': last + 10, 'cells': cells,
            'styles': styles, 'formats': formats, 'conditionalFormats': conditional,
            'cols': {'0': {'size': 200}, '10': {'size': 120}},
            'panes': {'xSplit': 1, 'ySplit': 6},
        }
