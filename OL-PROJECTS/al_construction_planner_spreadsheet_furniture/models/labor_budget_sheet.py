# -*- coding: utf-8 -*-
"""Presupuesto de mano de obra en la hoja de planificación (paquete 1.19,
M119-01).

* PARAMETROS: «Banda del rendimiento» y la sección «Rendimientos», una fila
  por actividad de las sub etapas con presupuesto (clave ``rend:<código>``),
  que se comporta como los demás parámetros: si la celda queda vacía vale el
  inicial (el de la obra o, si no tiene, el del catálogo) y un cambio pide el
  motivo.
* ``_MO`` (oculta): los días equivalentes de cada fecha según el horario de
  obra, y una fila por columna de la matriz de actividades con su cantidad en
  la obra, su rendimiento, sus persona-días y su tarifa.
* PROGRAMA, debajo de la grilla de pisos: un bloque por sub etapa y modalidad
  con el plazo (de los pisos o ajustado, con motivo), los días equivalentes,
  las personas, el rendimiento exigido, el presupuesto y las metas por
  semana.

El servidor no evalúa fórmulas: el envío lee los valores calculados de estos
bloques y escribe la tabla de rendimientos y el presupuesto de la obra, que se
recalcula en Python con la misma regla (núcleo, ``compute_budget``).
"""
from datetime import date, timedelta

from odoo import fields, models

from odoo.addons.al_construction_planner.models.construction_labor_budget import (
    BUDGET_MODES, budget_mode,
)

from .activity_matrix import (
    CODE_ROW, RATE_ROW, SPARE_COLUMNS, STAGE_ROW, TOTAL_ROW, _col,
)
from .construction_sheet_parameter import PARAMETERS_SHEET, parameter_formula

BUDGET_SHEET = '_MO'
PRODUCTIVITY_PREFIX = 'rend:'
BUDGET_TITLE = 'Presupuesto de mano de obra · '
# _MO: fechas en A:B; tabla de actividades en D:L; sub etapas en N:O.
HELPER_FIRST = 2
# Bloques de PROGRAMA: desplazamiento de cada fila desde el título.
BLOCK_ROWS = {
    'stage': 1, 'mode': 2, 'start': 3, 'end': 4, 'start_adjusted': 5, 'end_adjusted': 6,
    'reason': 7, 'date_from': 8, 'date_to': 9, 'equivalent_days': 10, 'quantity': 11,
    'person_days_needed': 12, 'persons_exact': 13, 'persons': 14, 'required': 15,
    'deviation': 16, 'person_days_budget': 17, 'daily_wage': 18, 'amount': 19, 'warning': 20,
    'flags': 21, 'share': 22, 'target': 23, 'target_cum': 24, 'person_days': 25,
    'person_days_cum': 26, 'week_amount': 27, 'week_amount_cum': 28,
}
BLOCK_HEIGHT = 30
SPREADSHEET_EPOCH = date(1899, 12, 30)


def serial_to_date(value):
    """Fecha de la hoja (número de días) a ``date``; ``None`` si no es fecha."""
    if isinstance(value, (int, float)) and value > 0:
        return SPREADSHEET_EPOCH + timedelta(days=int(value))
    if isinstance(value, str) and value:
        try:
            return fields.Date.to_date(value)
        except ValueError:
            return None
    return None


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # ------------------------------------------------------------------
    # Qué sub etapas llevan presupuesto y con qué actividades
    # ------------------------------------------------------------------
    def _construction_budget_stages(self):
        """[(sub etapa, [(pestaña, índice de columna, actividad o None)])] de
        las sub etapas con presupuesto que tienen columnas en la matriz."""
        self.ensure_one()
        result = []
        for tab in self._construction_matrix_tabs():
            budget_stages = tab['stages'].filtered('labor_budget')
            if not budget_stages:
                continue
            columns = [(tab, index, activity) for index, activity in
                       enumerate(tab['activities'], start=1)
                       if activity.stage in budget_stages.mapped('code')]
            spares = [(tab, 1 + len(tab['activities']) + offset, None)
                      for offset in range(SPARE_COLUMNS)]
            for stage in budget_stages:
                result.append((stage, [column for column in columns
                                       if column[2].stage == stage.code], spares))
        return result

    def _construction_budget_blocks(self):
        """[(sub etapa, modalidad)] de los bloques de PROGRAMA: la modalidad
        por defecto de la sub etapa y las de sus actividades."""
        self.ensure_one()
        stage_modes = self.env['construction.stage'].sudo()._execution_modes()
        blocks = []
        for stage, columns, _spares in self._construction_budget_stages():
            modes = [budget_mode(stage_modes.get(stage.code))]
            for _tab, _index, activity in columns:
                mode = budget_mode(activity._execution_mode(None, stage_modes))
                if mode not in modes:
                    modes.append(mode)
            blocks += [(stage, mode) for mode in modes]
        return blocks

    def _construction_productivity_sheet_rows(self):
        """Filas «Rendimientos» de PARAMETROS: el valor inicial es el de la
        obra o, si no lo tiene, el del catálogo."""
        self.ensure_one()
        current = self._construction_productivity_map()
        rows = []
        for stage, columns, _spares in self._construction_budget_stages():
            for _tab, _index, activity in columns:
                rows.append({
                    'group': 'Rendimientos',
                    'name': '%s · %s' % (activity.code, activity.name),
                    'unit': '%s por persona-día' % (activity.uom_id.name or ''),
                    'help': stage._label(),
                    'key': PRODUCTIVITY_PREFIX + activity.code,
                    'initial': current.get(activity, activity.productivity) or '',
                })
        return rows

    def _construction_productivity_sheet_values(self):
        """{clave: valor} de la tabla de la obra, para «Traer de la obra» y el
        valor vigente."""
        self.ensure_one()
        return {PRODUCTIVITY_PREFIX + activity.code: ('%.4f' % value).rstrip('0').rstrip('.')
                for activity, value in self._construction_productivity_map().items()
                if value}

    # ------------------------------------------------------------------
    # _MO
    # ------------------------------------------------------------------
    def _construction_day_range(self):
        today = fields.Date.context_today(self)
        return date(today.year - 1, 1, 1), date(today.year + 2, 12, 31)

    def _construction_day_factors(self):
        """[(fecha, días equivalentes)] del rango de la hoja."""
        self.ensure_one()
        company = self.company_id or self.env.company
        start, end = self._construction_day_range()
        result, day = [], start
        while day <= end:
            result.append((day, company._construction_day_factor(day)))
            day += timedelta(days=1)
        return result

    def _construction_budget_sheet(self, styles):
        """La pestaña oculta ``_MO``."""
        self.ensure_one()
        from .activity_matrix import _letter_index  # noqa: F401
        cells = {'A1': 'Fecha', 'B1': 'Días equivalentes', 'D1': 'Código', 'E1': 'Sub etapa',
                 'F1': 'Cantidad', 'G1': 'Rendimiento', 'H1': 'Persona-días', 'I1': 'Tarifa',
                 'J1': 'Importe de contrata', 'K1': 'Modalidad', 'L1': 'Sin rendimiento',
                 'N1': 'Sub etapa', 'O1': 'Modalidad por defecto'}
        factors = self._construction_day_factors()
        for row, (day, factor) in enumerate(factors, start=2):
            cells['A%s' % row] = '=DATE(%s,%s,%s)' % (day.year, day.month, day.day)
            # Como lo escribe el navegador (String(1) = «1»), para no reescribirlo al abrir.
            cells['B%s' % row] = str(int(factor)) if factor == int(factor) else repr(factor)
        stage_modes = self.env['construction.stage'].sudo()._execution_modes()
        row = HELPER_FIRST
        stage_row = 2
        seen_spares = set()
        for stage, columns, spares in self._construction_budget_stages():
            cells['N%s' % stage_row] = stage._label()
            cells['O%s' % stage_row] = budget_mode(stage_modes.get(stage.code))
            stage_row += 1
            items = [(tab, index, budget_mode(activity._execution_mode(None, stage_modes)))
                     for tab, index, activity in columns]
            for tab, index, _activity in spares:
                if (tab['name'], index) not in seen_spares:
                    seen_spares.add((tab['name'], index))
                    items.append((tab, index, None))
            for tab, index, mode in items:
                ref = "'%s'!%s" % (tab['name'], _col(index))
                cells['D%s' % row] = '=%s%s&""' % (ref, CODE_ROW)
                cells['E%s' % row] = '=%s%s&""' % (ref, STAGE_ROW)
                cells['F%s' % row] = '=IF(ISNUMBER({r}{t}),{r}{t},0)'.format(r=ref, t=TOTAL_ROW)
                cells['G%s' % row] = (
                    '=IF(D{n}="",0,IFERROR(IF(ISNUMBER(XLOOKUP("{p}"&D{n},{s}!$G:$G,{s}!$I:$I)),'
                    'XLOOKUP("{p}"&D{n},{s}!$G:$G,{s}!$I:$I),0),0))').format(
                    n=row, p=PRODUCTIVITY_PREFIX, s=PARAMETERS_SHEET)
                cells['H%s' % row] = '=IF(AND(F{n}>0,G{n}>0),F{n}/G{n},0)'.format(n=row)
                cells['I%s' % row] = '=IF(ISNUMBER({r}{t}),{r}{t},0)'.format(r=ref, t=RATE_ROW)
                cells['J%s' % row] = '=F{n}*I{n}'.format(n=row)
                cells['K%s' % row] = mode if mode else (
                    '=IFERROR(XLOOKUP(E{n},$N$2:$N$40,$O$2:$O$40),"own")'.format(n=row))
                cells['L%s' % row] = '=IF(AND(F{n}>0,G{n}<=0),1,0)'.format(n=row)
                row += 1
        return {
            'id': 'sheet_mo', 'name': BUDGET_SHEET, 'colNumber': 16,
            'rowNumber': max(len(factors) + 2, row + 2), 'cells': cells, 'isVisible': False,
            'styles': {'A1:O1': styles['head_calc']},
        }

    # ------------------------------------------------------------------
    # PROGRAMA
    # ------------------------------------------------------------------
    def _construction_program_budget(self, sheet, layout, stage_labels, first_floor, last_floor,
                                     week_row, date_row, week_letters, styles):
        """Agrega a PROGRAMA, debajo de la grilla de pisos, un bloque por sub
        etapa y modalidad."""
        self.ensure_one()
        blocks = self._construction_budget_blocks()
        if not blocks:
            return sheet
        from .project_project import column_of
        cells, sheet_styles, formats = sheet['cells'], sheet['styles'], sheet['formats']
        first_block = last_floor + 3
        cells['C14'] = self.env._(
            'Presupuesto de mano de obra y metas por semana: desde la fila %s', first_block)
        mode_labels = dict(BUDGET_MODES)
        band = parameter_formula('banda_rendimiento')
        mo = "'MO PROPIA'" if ' ' in 'MO PROPIA' else 'MO PROPIA'
        wage_col = column_of(layout, 'MO PROPIA', 'daily_cost')
        stage_col = column_of(layout, 'MO PROPIA', 'stage')
        first_week, last_week = week_letters[0], week_letters[-1]
        dates = '${f}${d}:${l}${d}'.format(f=first_week, l=last_week, d=date_row)
        for number, (stage, mode) in enumerate(blocks):
            base = first_block + number * BLOCK_HEIGHT
            row = {key: base + offset for key, offset in BLOCK_ROWS.items()}
            label = stage._label()
            index = stage_labels.index(label) + 1 if label in stage_labels else 0
            cells['A%s' % base] = '%s%s · %s' % (BUDGET_TITLE, label, mode_labels[mode])
            sheet_styles['A%s' % base] = styles['title']
            texts = {
                'stage': 'Sub etapa', 'mode': 'Modalidad', 'start': 'Inicio (pisos)',
                'end': 'Fin (pisos)', 'start_adjusted': 'Inicio ajustado',
                'end_adjusted': 'Fin ajustado', 'reason': 'Motivo del ajuste', 'date_from': 'Desde',
                'date_to': 'Hasta', 'equivalent_days': 'Días equivalentes',
                'quantity': 'Cantidad', 'person_days_needed': 'Persona-días necesarios',
                'persons_exact': 'Personas exactas', 'persons': 'Personas',
                'required': 'Rendimiento exigido', 'deviation': 'Desviación del rendimiento',
                'person_days_budget': 'Persona-días presupuestados', 'daily_wage': 'Jornal',
                'amount': 'Presupuesto', 'warning': 'Aviso',
                'flags': 'Semana con pisos en la sub etapa', 'share': 'Parte del plazo',
                'target': 'Meta de avance', 'target_cum': 'Meta acumulada',
                'person_days': 'Persona-días', 'person_days_cum': 'Persona-días acumulados',
                'week_amount': 'Soles', 'week_amount_cum': 'Soles acumulados',
            }
            for key, text in texts.items():
                cells['A%s' % row[key]] = text
                sheet_styles['A%s' % row[key]] = styles['header']
            b = lambda key: '$B$%s' % row[key]  # noqa: E731
            cells['B%s' % row['stage']] = label
            cells['C%s' % row['stage']] = stage.code
            cells['B%s' % row['mode']] = mode_labels[mode]
            cells['C%s' % row['mode']] = mode
            flags = '${f}${r}:${l}${r}'.format(f=first_week, l=last_week, r=row['flags'])
            cells['B%s' % row['start']] = '=IF(COUNTIF({fl},1)=0,"",MINIFS({d},{fl},1))'.format(
                fl=flags, d=dates)
            cells['B%s' % row['end']] = '=IF(COUNTIF({fl},1)=0,"",MAXIFS({d},{fl},1)+5)'.format(
                fl=flags, d=dates)
            cells['B%s' % row['date_from']] = '=IF({a}<>"",{a},{p})'.format(
                a=b('start_adjusted'), p=b('start'))
            cells['B%s' % row['date_to']] = '=IF({a}<>"",{a},{p})'.format(
                a=b('end_adjusted'), p=b('end'))
            cells['B%s' % row['equivalent_days']] = (
                '=IF(OR({f}="",{t}=""),0,SUMIFS({s}!$B:$B,{s}!$A:$A,">="&{f},{s}!$A:$A,"<="&{t}))'
            ).format(f=b('date_from'), t=b('date_to'), s=BUDGET_SHEET)
            criteria = '{s}!$E:$E,"{l}",{s}!$K:$K,"{m}"'.format(s=BUDGET_SHEET, l=label, m=mode)
            cells['B%s' % row['quantity']] = '=SUMIFS(%s!$F:$F,%s)' % (BUDGET_SHEET, criteria)
            cells['B%s' % row['person_days_needed']] = '=SUMIFS(%s!$H:$H,%s)' % (
                BUDGET_SHEET, criteria)
            cells['B%s' % row['persons_exact']] = '=IF({d}>0,{n}/{d},0)'.format(
                d=b('equivalent_days'), n=b('person_days_needed'))
            cells['B%s' % row['persons']] = (
                '=IF({e}<=0,0,MAX(1,ROUNDUP(ROUND({e}/(1+{band}),9),0)))').format(
                e=b('persons_exact'), band=band)
            cells['B%s' % row['required']] = '=IF({p}*{d}>0,{q}/({p}*{d}),"")'.format(
                p=b('persons'), d=b('equivalent_days'), q=b('quantity'))
            cells['B%s' % row['deviation']] = '=IF({p}>0,{e}/{p}-1,"")'.format(
                p=b('persons'), e=b('persons_exact'))
            cells['B%s' % row['person_days_budget']] = '=%s*%s' % (
                b('persons'), b('equivalent_days'))
            cells['B%s' % row['daily_wage']] = (
                '=IFERROR(AVERAGEIFS({m}!${w}:${w},{m}!${s}:${s},"{l}"),0)').format(
                m=mo, w=wage_col, s=stage_col, l=label)
            if mode == 'own':
                cells['B%s' % row['amount']] = '=%s*%s' % (b('person_days_budget'),
                                                           b('daily_wage'))
            else:
                cells['B%s' % row['amount']] = '=SUMIFS(%s!$J:$J,%s)' % (BUDGET_SHEET, criteria)
            cells['B%s' % row['warning']] = (
                '=TRIM(IF(AND({p}>0,{e}/{p}<1-{band}),"Capacidad ociosa: "&{p}&" persona(s) al "'
                '&ROUND({e}/{p}*100,0)&" %","")&IF(SUMIFS({s}!$L:$L,{c})>0," · Sin rendimiento: "'
                '&TEXTJOIN(", ",TRUE,FILTER({s}!$D$2:$D$500,{s}!$E$2:$E$500="{l}",'
                '{s}!$L$2:$L$500=1)),""))').format(
                p=b('persons'), e=b('persons_exact'), band=band, s=BUDGET_SHEET, c=criteria,
                l=label)
            for key in ('start_adjusted', 'end_adjusted', 'reason'):
                sheet_styles['B%s' % row[key]] = styles['data']
            for key in ('stage', 'mode', 'start', 'end', 'date_from', 'date_to',
                        'equivalent_days', 'quantity', 'person_days_needed', 'persons_exact',
                        'persons', 'required', 'deviation', 'person_days_budget', 'daily_wage',
                        'amount', 'warning'):
                sheet_styles['B%s' % row[key]] = styles['calc']
            for key in ('start', 'end', 'start_adjusted', 'end_adjusted', 'date_from', 'date_to'):
                formats['B%s' % row[key]] = 'dd/mm/yyyy'
            for key in ('equivalent_days', 'quantity', 'person_days_needed', 'persons_exact',
                        'required', 'person_days_budget', 'daily_wage', 'amount'):
                formats['B%s' % row[key]] = '#,##0.00'
            formats['B%s' % row['deviation']] = '0.0%'
            # Un ajuste sin motivo se marca.
            sheet.setdefault('conditionalFormats', []).append({
                'id': 'budget_reason_%s' % number, 'ranges': ['B%s' % row['reason']],
                'stopIfTrue': False,
                'rule': {'type': 'CellIsRule', 'operator': 'customFormula',
                         'values': ['=AND(OR({a}<>"",{e}<>""),{r}="")'.format(
                             a=b('start_adjusted'), e=b('end_adjusted'), r=b('reason'))],
                         'style': {'fillColor': '#F6E1E4', 'textColor': '#B23A48'}}})
            # Metas por semana.
            for letter in week_letters:
                monday = '%s$%s' % (letter, date_row)
                cells['%s%s' % (letter, row['flags'])] = (
                    '=IF({m}="",0,IF(COUNTIF({c}${f}:{c}${l},{k})>0,1,0))').format(
                    m=monday, c=letter, f=first_floor, l=last_floor, k=index)
                cells['%s%s' % (letter, row['share'])] = (
                    '=IF(OR({d}=0,{fr}="",{to}="",{m}=""),0,IF(OR({m}>{to},{m}+6<{fr}),0,'
                    'SUMIFS({s}!$B:$B,{s}!$A:$A,">="&MAX({m},{fr}),{s}!$A:$A,"<="&MIN({m}+6,{to}))'
                    '/{d}))').format(d=b('equivalent_days'), fr=b('date_from'), to=b('date_to'),
                                     m=monday, s=BUDGET_SHEET)
                share = '%s%s' % (letter, row['share'])
                for key, total in (('target', 'quantity'), ('person_days', 'person_days_budget'),
                                   ('week_amount', 'amount')):
                    cells['%s%s' % (letter, row[key])] = '=%s*%s' % (b(total), share)
                    cells['%s%s' % (letter, row[key + '_cum'])] = '=SUM($%s%s:%s%s)' % (
                        first_week, row[key], letter, row[key])
            zone = '%s%s:%s%s' % (first_week, row['flags'], last_week, row['week_amount_cum'])
            sheet_styles[zone] = styles['calc']
            formats['%s%s:%s%s' % (first_week, row['share'], last_week, row['share'])] = '0%'
            formats['%s%s:%s%s' % (first_week, row['target'], last_week,
                                   row['week_amount_cum'])] = '#,##0.00'
        sheet['rowNumber'] = max(sheet.get('rowNumber', 0),
                                 first_block + len(blocks) * BLOCK_HEIGHT + 10)
        return sheet


def read_labor_payload(sheets):
    """Datos del presupuesto de mano de obra que lee el envío de los valores
    calculados de la hoja: rendimientos, banda, actividades y bloques."""
    payload = {'productivity': [], 'band': None, 'excess_band': None, 'activities': [],
               'blocks': []}
    for row in (sheets.get(PARAMETERS_SHEET) or [])[1:]:
        key = row[6] if len(row) > 6 else ''
        if key in ('banda_rendimiento', 'banda_exceso_personal'):
            used = row[8] if len(row) > 8 else ''
            payload['band' if key == 'banda_rendimiento' else 'excess_band'] = \
                _number(used) * 100 if used not in ('', None) else None
        elif isinstance(key, str) and key.startswith(PRODUCTIVITY_PREFIX):
            payload['productivity'].append({
                'code': key[len(PRODUCTIVITY_PREFIX):],
                'value': row[2] if len(row) > 2 else '',
                'initial': row[5] if len(row) > 5 else '',
                'reason': row[7] if len(row) > 7 else '',
                'used': _number(row[8] if len(row) > 8 else 0),
            })
    for row in (sheets.get(BUDGET_SHEET) or [])[1:]:
        code = row[3] if len(row) > 3 else ''
        if not code:
            continue
        get = lambda index: row[index] if len(row) > index else ''  # noqa: E731
        payload['activities'].append({
            'code': str(code), 'stage': get(4), 'qty': _number(get(5)),
            'productivity': _number(get(6)), 'rate': _number(get(8)),
            'mode': get(10) or 'own'})
    program = sheets.get('PROGRAMA') or []
    for index, row in enumerate(program):
        if not row or not isinstance(row[0], str) or not row[0].startswith(BUDGET_TITLE):
            continue

        def value(key, column=1, base=index):
            line = program[base + BLOCK_ROWS[key]] if base + BLOCK_ROWS[key] < len(program) \
                else []
            return line[column] if len(line) > column else ''

        payload['blocks'].append({
            'stage_code': value('stage', 2), 'stage_label': value('stage'),
            'mode': value('mode', 2), 'start': serial_to_date(value('start')),
            'end': serial_to_date(value('end')),
            'start_adjusted': serial_to_date(value('start_adjusted')),
            'end_adjusted': serial_to_date(value('end_adjusted')),
            'reason': value('reason') or '', 'daily_wage': _number(value('daily_wage')),
        })
    return payload
