# -*- coding: utf-8 -*-
"""Actividades de cada tipología en una matriz por etapa (paquete 1.19, M119-04).

Una pestaña por etapa del perfil de la obra que tiene actividades por
tipología: en mobiliario «ACT ARMADO» (1.2 Armado) y «ACT INSTALACIÓN» (2.1
Instalación, 2.2 Acabado y 2.3 Limpieza, en bloques). El nombre y los bloques
salen del catálogo de etapas, no del código. Las dos reemplazan a ACTIVIDADES,
que queda oculta: el envío convierte la matriz en sus filas y el importador
y «Generar plan» no cambian.

Filas de la pestaña:

1. encabezado: tipología, una columna por actividad («nombre · unidad»),
   columnas libres para agregar otra actividad y las calculadas;
2. código de la actividad (oculta);
3. qué hace la columna (oculta): ``data`` se escribe, ``ml`` se calcula con
   los ML y va al envío, ``module`` cuenta módulos y no va al envío, porque
   «Generar plan» saca el armado por módulo de MODULOS;
4. sub etapa;
5. tarifa (TARIFAS o, sin tarifa, la base del catálogo);
6. cantidad en la obra;
7 en adelante: una fila por tipología de TIPOLOGIAS.
"""
from odoo import api, fields, models

from . import sheet_design as design

MATRIX_PREFIX = 'ACT '
MATRIX_CODE_LABEL = 'Código (calc.)'
MATRIX_KIND_LABEL = 'Se escribe (calc.)'
KIND_DATA, KIND_ML, KIND_MODULE = 'data', 'ml', 'module'
SENT_KINDS = (KIND_DATA, KIND_ML)
HEADER_ROW, CODE_ROW, KIND_ROW, STAGE_ROW, RATE_ROW, TOTAL_ROW = 1, 2, 3, 4, 5, 6
FIRST_ROW = 7
MATRIX_ROWS = 150
SPARE_COLUMNS = 5
# Lista de actividades de REFERENCIAS para la matriz: código, clave de armado
# y tarifa base (columnas AG a AI).
MATRIX_LIST_ID = '9'
MATRIX_LIST_START = 32
MATRIX_LIST_COUNT = 300
_REF_CODES = 'REFERENCIAS!$AG$3:$AG$%s' % (MATRIX_LIST_COUNT + 2)
_REF_KEYS = 'REFERENCIAS!$AH$3:$AH$%s' % (MATRIX_LIST_COUNT + 2)
_REF_PRICES = 'REFERENCIAS!$AI$3:$AI$%s' % (MATRIX_LIST_COUNT + 2)
_ACTIVITY_CODES = 'REFERENCIAS!$A$3:$A$302'
# Grupo ML de la actividad → (en MODULOS, en MUEBLES, columna de TIPOLOGIAS).
ML_GROUP_LABELS = {
    'low': ('Mueble bajo', 'Bajo', 'ml_low'),
    'high': ('Mueble alto', 'Alto', 'ml_high'),
    'full': ('Mueble completo', 'Completo', None),
}
CALC_HEADERS = ('Ambientes (calc.)', 'Costo por ambiente (calc.)', 'Costo total (calc.)')


def _col(index):
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def _letter_index(letters):
    """A → 0, AA → 26."""
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - 64
    return index - 1


def matrix_last_data(tab):
    """Letra de la última columna de actividades (con las libres)."""
    return _col(len(tab['activities']) + SPARE_COLUMNS)


def matrix_total_col(tab):
    """Letra de «Costo total (calc.)»."""
    return _col(len(tab['activities']) + SPARE_COLUMNS + len(CALC_HEADERS))


def is_matrix(rows):
    """Si las filas de una pestaña (valores calculados) son de una matriz."""
    return bool(rows) and len(rows) >= FIRST_ROW - 1 and len(rows[CODE_ROW - 1]) > 0 \
        and rows[CODE_ROW - 1][0] == MATRIX_CODE_LABEL


def matrix_activity_rows(rows):
    """[[tipología, actividad, cantidad]] de una matriz: las celdas con
    cantidad de las columnas que se escriben o van por ML."""
    codes = rows[CODE_ROW - 1]
    kinds = rows[KIND_ROW - 1] if len(rows) >= KIND_ROW else []
    result = []
    for row in rows[FIRST_ROW - 1:]:
        typology = row[0] if row else ''
        if typology in ('', None, False):
            continue
        for index in range(1, min(len(row), len(codes))):
            code = codes[index]
            kind = kinds[index] if index < len(kinds) else ''
            value = row[index]
            if not code or kind not in SENT_KINDS or value in ('', None, False):
                continue
            try:
                qty = float(value)
            except (TypeError, ValueError):
                result.append([typology, code, value])
                continue
            if qty:
                result.append([typology, code, value])
    return result


def merge_matrix(sheets):
    """``sheets`` con ACTIVIDADES armada desde las matrices, si la hoja las
    tiene; si no, tal cual (hojas anteriores al paquete 1.19)."""
    matrices = [rows for rows in (sheets or {}).values() if is_matrix(rows)]
    if not matrices:
        return sheets
    result = dict(sheets)
    activity_rows = [['typology', 'activity', 'qty']]
    for rows in matrices:
        activity_rows += matrix_activity_rows(rows)
    result['ACTIVIDADES'] = activity_rows
    return result


class ConstructionLaborActivity(models.Model):
    _inherit = 'construction.labor.activity'

    construction_sheet_key = fields.Char(
        string='Clave de armado en la hoja', compute='_compute_construction_sheet_key',
        help='Con qué módulos se cruza en la hoja de planificación: «join:<método de unión>» o '
             '«special:<tipo de módulo especial>», con la misma regla que la actividad de armado '
             'del catálogo.')

    @api.depends('activity_class', 'join_method', 'special_kind')
    def _compute_construction_sheet_key(self):
        joins = dict(self._fields['join_method']._description_selection(self.env))
        specials = dict(self._fields['special_kind']._description_selection(self.env))
        for activity in self:
            key = False
            if activity.activity_class in ('assembly_method', 'onsite_assembly') \
                    and activity.join_method and activity.join_method != 'none':
                key = 'join:%s' % joins.get(activity.join_method, activity.join_method)
            elif activity.activity_class == 'assembly_special' and activity.special_kind:
                key = 'special:%s' % specials.get(activity.special_kind, activity.special_kind)
            activity.construction_sheet_key = key

    def _construction_matrix_kind(self):
        """Qué hace la columna de la actividad en la matriz."""
        self.ensure_one()
        if self.module_level:
            return KIND_MODULE
        if self.ml_based and self.ml_group in ML_GROUP_LABELS:
            return KIND_ML
        return KIND_DATA


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _construction_matrix_tabs(self):
        """Pestañas de la matriz: ``[{'name', 'stages', 'activities'}]``, una
        por etapa padre del perfil de la obra con actividades en sus sub
        etapas. El nombre es el de la sub etapa si es una sola, o el de la
        etapa padre."""
        self.ensure_one()
        company = self.company_id or self.env.company
        stages = self.env['construction.stage']._offered_stages(self)
        activities = self.env['construction.labor.activity'].search([
            ('company_id', 'in', (company.id, False)), ('stage', 'in', stages.mapped('code'))],
            order='sequence, code, id')
        by_stage = {}
        for activity in activities:
            by_stage.setdefault(activity.stage, self.env['construction.labor.activity'])
            by_stage[activity.stage] |= activity
        tabs, seen = [], {}
        for stage in stages:
            if stage.code not in by_stage:
                continue
            parent = stage.parent_id or stage
            if parent.id not in seen:
                seen[parent.id] = {'parent': parent, 'stages': self.env['construction.stage'],
                                   'activities': self.env['construction.labor.activity']}
                tabs.append(seen[parent.id])
            seen[parent.id]['stages'] |= stage
            seen[parent.id]['activities'] |= by_stage[stage.code]
        result, names = [], set()
        for tab in tabs:
            label = tab['stages'].name if len(tab['stages']) == 1 else tab['parent'].name
            name = ('%s%s' % (MATRIX_PREFIX, (label or '').upper()))[:31]
            while name in names:
                name = name[:29] + '%02d' % len(names)
            names.add(name)
            result.append({'name': name, 'stages': tab['stages'],
                           'activities': tab['activities']})
        return result

    def _construction_matrix_sheet(self, tab, layout, styles):
        """La pestaña de la matriz ``tab``.

        :param styles: ``{'head_data', 'head_calc', 'data', 'calc', 'title'}``
            con los ids de estilo de la plantilla.
        """
        self.ensure_one()
        from .project_project import full_column, column_of

        def col_range(sheet, key):
            return full_column(layout, sheet, key)

        typology_code = column_of(layout, 'TIPOLOGIAS', 'code')
        in_site = col_range('TIPOLOGIAS', '#En la obra (calc.)')
        typologies = col_range('TIPOLOGIAS', 'code')
        stage_labels = {stage.code: stage._label() for stage in tab['stages']}
        activities = tab['activities']
        n_activities = len(activities)
        first_spare = 1 + n_activities
        first_calc = first_spare + SPARE_COLUMNS
        last_row = FIRST_ROW + MATRIX_ROWS - 1
        cells, sheet_styles, formats, rules = {}, {}, {}, []
        labels = {HEADER_ROW: 'Tipología', CODE_ROW: MATRIX_CODE_LABEL,
                  KIND_ROW: MATRIX_KIND_LABEL, STAGE_ROW: 'Sub etapa', RATE_ROW: 'Tarifa',
                  TOTAL_ROW: 'Cantidad en la obra (calc.)'}
        for row, label in labels.items():
            cells['A%s' % row] = label
            sheet_styles['A%s' % row] = styles['head_calc']
        for row in range(FIRST_ROW, last_row + 1):
            cells['A%s' % row] = '=IF(TIPOLOGIAS!${c}${t}="","",TIPOLOGIAS!${c}${t})'.format(
                c=typology_code, t=row - FIRST_ROW + 2)
        sheet_styles['A%s:A%s' % (FIRST_ROW, last_row)] = styles['calc']
        ambientes = '$%s{r}' % _col(first_calc)

        def rate_formula(letter):
            return ('=IF({l}${c}="","",IFERROR(XLOOKUP({l}${c},{ta},{tp}),'
                    'IFERROR(XLOOKUP({l}${c},{rc},{rp}),0)))').format(
                l=letter, c=CODE_ROW, ta=col_range('TARIFAS', 'activity'),
                tp=col_range('TARIFAS', 'price'), rc=_REF_CODES, rp=_REF_PRICES)

        def column_common(letter):
            cells['%s%s' % (letter, RATE_ROW)] = rate_formula(letter)
            cells['%s%s' % (letter, TOTAL_ROW)] = (
                '=IF({l}${c}="","",SUMPRODUCT({l}${f}:{l}${e},${a}${f}:${a}${e}))').format(
                l=letter, c=CODE_ROW, f=FIRST_ROW, e=last_row, a=_col(first_calc))
            for row in (RATE_ROW, TOTAL_ROW):
                sheet_styles['%s%s' % (letter, row)] = styles['calc']
                formats['%s%s' % (letter, row)] = design.MONEY
            sheet_styles['%s%s:%s%s' % (letter, CODE_ROW, letter, STAGE_ROW)] = styles['calc']

        for index, activity in enumerate(activities, start=1):
            letter = _col(index)
            kind = activity._construction_matrix_kind()
            cells['%s%s' % (letter, HEADER_ROW)] = '%s · %s' % (
                activity.name, activity.uom_id.name or '')
            cells['%s%s' % (letter, CODE_ROW)] = activity.code or ''
            cells['%s%s' % (letter, KIND_ROW)] = kind
            cells['%s%s' % (letter, STAGE_ROW)] = stage_labels.get(activity.stage, '')
            column_common(letter)
            zone = '%s%s:%s%s' % (letter, FIRST_ROW, letter, last_row)
            if kind == KIND_DATA:
                sheet_styles['%s%s' % (letter, HEADER_ROW)] = styles['head_data']
                sheet_styles[zone] = styles['data']
                continue
            sheet_styles['%s%s' % (letter, HEADER_ROW)] = styles['head_calc']
            sheet_styles[zone] = styles['calc']
            for row in range(FIRST_ROW, last_row + 1):
                cells['%s%s' % (letter, row)] = self._construction_matrix_calc_formula(
                    layout, activity, kind, row)
        for offset in range(SPARE_COLUMNS):
            letter = _col(first_spare + offset)
            cells['%s%s' % (letter, CODE_ROW)] = '=IF({l}${h}="","",{l}${h}&"")'.format(
                l=letter, h=HEADER_ROW)
            cells['%s%s' % (letter, KIND_ROW)] = '=IF({l}${c}="","","{k}")'.format(
                l=letter, c=CODE_ROW, k=KIND_DATA)
            cells['%s%s' % (letter, STAGE_ROW)] = (
                '=IF({l}${c}="","",IFERROR(XLOOKUP({l}${c},{codes},REFERENCIAS!$C$3:$C$302),""))'
            ).format(l=letter, c=CODE_ROW, codes=_ACTIVITY_CODES)
            column_common(letter)
            sheet_styles['%s%s' % (letter, HEADER_ROW)] = styles['head_data']
            sheet_styles['%s%s:%s%s' % (letter, FIRST_ROW, letter, last_row)] = styles['data']
            rules.append({
                'id': 'matrix_spare_%s' % letter, 'isBlocking': False,
                'ranges': ['%s%s' % (letter, HEADER_ROW)],
                'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                              'values': [_ACTIVITY_CODES]}})
        # Calculadas: ambientes, costo por ambiente y costo total.
        last_data = _col(first_calc - 1)
        for offset, header in enumerate(CALC_HEADERS):
            letter = _col(first_calc + offset)
            cells['%s%s' % (letter, HEADER_ROW)] = header
            sheet_styles['%s%s' % (letter, HEADER_ROW)] = styles['head_calc']
            sheet_styles['%s%s:%s%s' % (letter, FIRST_ROW, letter, last_row)] = styles['calc']
            formats['%s%s:%s%s' % (letter, FIRST_ROW, letter, last_row)] = \
                design.INTEGER if offset == 0 else design.MONEY
        amb, cost, total = (_col(first_calc + offset) for offset in range(3))
        for row in range(FIRST_ROW, last_row + 1):
            cells['%s%s' % (amb, row)] = '=IF($A{r}="","",IFERROR(XLOOKUP($A{r},{t},{s}),0))'.format(
                r=row, t=typologies, s=in_site)
            cells['%s%s' % (cost, row)] = (
                '=IF($A{r}="","",SUMPRODUCT($B{r}:${d}{r},$B${rate}:${d}${rate}))').format(
                r=row, d=last_data, rate=RATE_ROW)
            cells['%s%s' % (total, row)] = '=IF($A{r}="","",{a}{r}*{c}{r})'.format(
                r=row, a=amb, c=cost)
        cells['%s%s' % (amb, TOTAL_ROW)] = '=SUM(%s%s:%s%s)' % (amb, FIRST_ROW, amb, last_row)
        cells['%s%s' % (total, TOTAL_ROW)] = '=SUM(%s%s:%s%s)' % (
            total, FIRST_ROW, total, last_row)
        for letter in (amb, total):
            sheet_styles['%s%s' % (letter, TOTAL_ROW)] = styles['calc']
        formats['%s%s' % (total, TOTAL_ROW)] = design.MONEY
        for row in range(FIRST_ROW, last_row + 1):
            formats['B%s:%s%s' % (row, last_data, row)] = design.MONEY
        n_cols = first_calc + len(CALC_HEADERS)
        cols = {'0': {'size': 120}}
        cols.update({str(index): {'size': 115} for index in range(1, n_cols)})
        return {
            'name': tab['name'], 'colNumber': max(n_cols + 2, 26),
            'rowNumber': last_row + 10, 'cells': cells, 'styles': sheet_styles,
            'formats': formats,
            'rows': {'0': {'size': design.HEADER_HEIGHT},
                     str(CODE_ROW - 1): {'isHidden': True},
                     str(KIND_ROW - 1): {'isHidden': True}},
            'cols': cols, 'panes': {'xSplit': 1, 'ySplit': FIRST_ROW - 1},
            'dataValidationRules': rules,
            'construction_matrix': {
                'locked_cols': [index for index, activity in enumerate(activities, start=1)
                                if activity._construction_matrix_kind() != KIND_DATA]
                + list(range(first_calc, n_cols)),
                'first_row': FIRST_ROW - 1,
                'codes': {activity.code: index for index, activity in
                          enumerate(activities, start=1)},
                'first_spare': first_spare,
            },
        }

    def _construction_matrix_calc_formula(self, layout, activity, kind, row):
        """Celda gris de la fila ``row``: módulos de la tipología con esa
        actividad de armado, o sus ML del grupo de la actividad (los anchos de
        MODULOS; sin anchos, MUEBLES; sin muebles, TIPOLOGIAS)."""
        from .project_project import full_column

        def col_range(sheet, key):
            return full_column(layout, sheet, key)

        typology = '$A%s' % row
        if kind == KIND_MODULE:
            value = 'COUNTIFS({t},{ty},{a},"{code}")'.format(
                t=col_range('MODULOS', 'typology'), ty=typology,
                a=col_range('MODULOS', '#Actividad efectiva (calc.)'), code=activity.code)
            return '=IF({ty}="","",IF({v}=0,"",{v}))'.format(ty=typology, v=value)
        module_group, furniture_group, typology_key = ML_GROUP_LABELS[activity.ml_group]
        modules = 'SUMIFS({ml},{t},{ty},{g},"{grp}")'.format(
            ml=col_range('MODULOS', '#ML (calc.)'), t=col_range('MODULOS', 'typology'),
            ty=typology, g=col_range('MODULOS', 'ml_group'), grp=module_group)
        furniture = 'SUMIFS({ml},{t},{ty},{g},"{grp}")'.format(
            ml=col_range('MUEBLES', 'ml'), t=col_range('MUEBLES', 'typology'), ty=typology,
            g=col_range('MUEBLES', 'ml_group'), grp=furniture_group)
        typology_ml = 'IFERROR(VALUE(XLOOKUP({ty},{codes},{ml})),0)'.format(
            ty=typology, codes=col_range('TIPOLOGIAS', 'code'),
            ml=col_range('TIPOLOGIAS', typology_key)) if typology_key else '0'
        value = 'IF({m}>0,{m},IF({f}>0,{f},{t}))'.format(m=modules, f=furniture, t=typology_ml)
        return '=IF({ty}="","",IF({v}=0,"",ROUND({v},4)))'.format(ty=typology, v=value)
