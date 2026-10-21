#!/usr/bin/env python3
"""Genera el tablero de cobranza (spreadsheet.dashboard de Odoo 19).

El tablero nativo de Odoo es una hoja de cálculo en JSON (o-spreadsheet). Este
script la arma desde Python para que los cambios se revisen como código:

    python3 docs/cobranza/build_collection_dashboard.py

y escribe OL-ACCOUNTING/al_l10n_pe_collection/data/files/collection_dashboard.json.
Tras editarlo en Odoo (Tableros ▸ editar) también se puede exportar el JSON,
pero entonces este script deja de ser la fuente: elegir una de las dos vías.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'OL-ACCOUNTING/al_l10n_pe_collection/data/files/collection_dashboard.json'

PORTFOLIO = 'l10n_pe.collection.portfolio'
PROMISE = 'l10n_pe.collection.promise'
PAYMENT = 'account.payment'

# Filtros globales (identificadores fijos: los usan las fuentes de datos).
F_PERIOD = 'c0b1a001-0000-4000-8000-000000000001'
F_USER = 'c0b1a001-0000-4000-8000-000000000002'
F_ZONE = 'c0b1a001-0000-4000-8000-000000000003'
F_PARTNER = 'c0b1a001-0000-4000-8000-000000000004'

# «Año a la fecha» incluye hoy; «Últimos 12 meses» de Odoo excluye el mes en curso.
GLOBAL_FILTERS = [
    {'id': F_PERIOD, 'type': 'date', 'label': 'Periodo', 'defaultValue': 'year_to_date'},
    {'id': F_USER, 'type': 'relation', 'label': 'Gestor', 'modelName': 'res.users',
     'defaultValueDisplayNames': []},
    {'id': F_ZONE, 'type': 'relation', 'label': 'Zona', 'modelName': 'l10n_pe.collection.zone',
     'defaultValueDisplayNames': []},
    {'id': F_PARTNER, 'type': 'relation', 'label': 'Cliente', 'modelName': 'res.partner',
     'defaultValueDisplayNames': []},
]

# La cartera es una foto al día: el periodo no la filtra.
MATCH_PORTFOLIO = {
    F_USER: {'chain': 'user_id', 'type': 'many2one'},
    F_ZONE: {'chain': 'zone_id', 'type': 'many2one'},
    F_PARTNER: {'chain': 'partner_id', 'type': 'many2one'},
}
# Compromisos pendientes: tampoco por periodo (interesan todos los vigentes).
MATCH_PROMISE_OPEN = {
    F_USER: {'chain': 'user_id', 'type': 'many2one'},
    F_ZONE: {'chain': 'partner_id.l10n_pe_collection_zone_id', 'type': 'many2one'},
    F_PARTNER: {'chain': 'partner_id', 'type': 'many2one'},
}
# Compromisos pactados en el periodo y compromisos evaluados en el periodo.
MATCH_PROMISE_AGREED = dict(MATCH_PROMISE_OPEN, **{F_PERIOD: {'chain': 'date_agreed', 'type': 'date', 'offset': 0}})
MATCH_PROMISE_EVALUATED = dict(MATCH_PROMISE_OPEN,
                               **{F_PERIOD: {'chain': 'evaluated_on', 'type': 'date', 'offset': 0}})
MATCH_PAYMENT = {
    F_PERIOD: {'chain': 'date', 'type': 'date', 'offset': 0},
    F_USER: {'chain': 'partner_id.followup_responsible_id', 'type': 'many2one'},
    F_ZONE: {'chain': 'partner_id.l10n_pe_collection_zone_id', 'type': 'many2one'},
    F_PARTNER: {'chain': 'partner_id', 'type': 'many2one'},
}

D_PORTFOLIO = [('in_collection', '=', True)]
D_OVERDUE = D_PORTFOLIO + [('is_overdue', '=', True)]
D_PAYMENT = [('payment_type', '=', 'inbound'), ('partner_type', '=', 'customer'),
             ('state', 'in', ['in_process', 'paid'])]


def domain(terms):
    """Dominio en notación prefija, como lo guarda el editor de Odoo."""
    out = ['&'] * (len(terms) - 1)
    for field, op, value in terms:
        out.append([field, op, value])
    return out


# ----------------------------------------------------------------------
# Tablas dinámicas (fuentes de los indicadores y de las tablas)
# ----------------------------------------------------------------------
PIVOTS = {}


def pivot(name, model, terms, measures, matching, rows=(), sorted_by=None):
    pid = str(len(PIVOTS) + 1)
    PIVOTS[pid] = {
        'type': 'ODOO', 'id': pid, 'formulaId': pid, 'name': name, 'model': model,
        'domain': domain(terms), 'context': {}, 'fieldMatching': matching,
        'measures': [dict(m, id=m.get('id') or m['fieldName']) for m in measures],
        'rows': [{'fieldName': r} for r in rows], 'columns': [],
        'sortedColumn': {'measure': sorted_by, 'order': 'desc', 'domain': []} if sorted_by else None,
    }
    if not sorted_by:
        del PIVOTS[pid]['sortedColumn']
    return pid


AMOUNT = {'fieldName': 'amount_residual', 'userDefinedName': 'Saldo'}
PARTNERS = {'id': 'partner_id:count_distinct', 'fieldName': 'partner_id', 'aggregator': 'count_distinct',
            'userDefinedName': 'Clientes'}
COUNT = {'id': '__count', 'fieldName': '__count', 'userDefinedName': 'Cantidad'}

P_PORTFOLIO = pivot('Cartera', PORTFOLIO, D_PORTFOLIO, [AMOUNT, PARTNERS], MATCH_PORTFOLIO)
P_OVERDUE = pivot('Vencido', PORTFOLIO, D_OVERDUE, [AMOUNT, PARTNERS], MATCH_PORTFOLIO)
P_OVERDUE_90 = pivot('Vencido más de 90 días', PORTFOLIO, D_OVERDUE + [('days_overdue', '>', 90)],
                     [AMOUNT, PARTNERS], MATCH_PORTFOLIO)
P_DUE = pivot('Por vencer', PORTFOLIO, D_PORTFOLIO + [('is_overdue', '=', False), ('amount_residual', '>', 0)],
              [AMOUNT, PARTNERS], MATCH_PORTFOLIO)
P_PROMISE_OPEN = pivot('Compromisos pendientes', PROMISE, [('state', '=', 'pending')],
                       [{'fieldName': 'amount', 'userDefinedName': 'Comprometido'}, COUNT], MATCH_PROMISE_OPEN)
P_PROMISE_CLOSED = pivot('Compromisos evaluados', PROMISE, [('state', 'in', ['kept', 'partial', 'broken'])],
                         [COUNT], MATCH_PROMISE_EVALUATED)
P_PROMISE_KEPT = pivot('Compromisos cumplidos', PROMISE, [('state', '=', 'kept')], [COUNT],
                       MATCH_PROMISE_EVALUATED)
P_COLLECTED = pivot('Cobrado', PAYMENT, D_PAYMENT,
                    [{'fieldName': 'amount_company_currency_signed', 'userDefinedName': 'Cobrado'}, COUNT],
                    MATCH_PAYMENT)
# El nombre encabeza la primera columna de la tabla.
P_TOP = pivot('Cliente', PORTFOLIO, D_OVERDUE,
              [dict(AMOUNT, userDefinedName='Vencido'),
               {'fieldName': 'days_overdue', 'userDefinedName': 'Días de atraso'}],
              MATCH_PORTFOLIO, rows=['partner_id'], sorted_by='amount_residual')

LISTS = {
    '1': {
        'id': '1', 'name': 'Compromisos pendientes', 'model': PROMISE,
        'columns': ['partner_id', 'date', 'amount', 'user_id'],
        'domain': domain([('state', '=', 'pending')]), 'context': {},
        'orderBy': [{'name': 'date', 'asc': True}], 'fieldMatching': MATCH_PROMISE_OPEN,
    },
}

# ----------------------------------------------------------------------
# Hoja «Datos»: cálculos que leen los indicadores
# ----------------------------------------------------------------------
DATA_ROWS = [
    # (etiqueta, fórmula del valor, fórmula del texto mostrado, formato del texto)
    ('Cartera', f'=PIVOT.VALUE({P_PORTFOLIO},"amount_residual")', 'large', None),
    ('Vencido', f'=PIVOT.VALUE({P_OVERDUE},"amount_residual")', 'large', None),
    ('Vencido más de 90 días', f'=PIVOT.VALUE({P_OVERDUE_90},"amount_residual")', 'large', None),
    ('Por vencer', f'=PIVOT.VALUE({P_DUE},"amount_residual")', 'large', None),
    ('Comprometido pendiente', f'=PIVOT.VALUE({P_PROMISE_OPEN},"amount")', 'large', None),
    ('Cumplimiento de compromisos', f'=IFERROR(PIVOT.VALUE({P_PROMISE_KEPT},"__count")'
                                    f'/PIVOT.VALUE({P_PROMISE_CLOSED},"__count"),0)', '=B6', 'pct'),
    ('Cobrado en el periodo', f'=PIVOT.VALUE({P_COLLECTED},"amount_company_currency_signed")', 'large', None),
    ('Clientes con deuda vencida', f'=PIVOT.VALUE({P_OVERDUE},"partner_id:count_distinct")', '=B8', None),
    # Líneas base (texto bajo cada indicador)
    ('Clientes en cartera', f'=PIVOT.VALUE({P_PORTFOLIO},"partner_id:count_distinct")', '=B9', None),
    ('% vencido', '=IFERROR(B2/B1,0)', '=B10', 'pct'),
    ('Clientes con más de 90 días', f'=PIVOT.VALUE({P_OVERDUE_90},"partner_id:count_distinct")', '=B11', None),
    ('Clientes por vencer', f'=PIVOT.VALUE({P_DUE},"partner_id:count_distinct")', '=B12', None),
    ('Compromisos pendientes', f'=PIVOT.VALUE({P_PROMISE_OPEN},"__count")', '=B13', None),
    ('Compromisos evaluados', f'=PIVOT.VALUE({P_PROMISE_CLOSED},"__count")', '=B14', None),
    ('Cobros', f'=PIVOT.VALUE({P_COLLECTED},"__count")', '=B15', None),
    ('Vencido sobre clientes en cartera', '=IFERROR(B8/B9,0)', '=B16', 'pct'),
]


def data_sheet():
    cells, formats = {}, {}
    for idx, (label, value, shown, fmt) in enumerate(DATA_ROWS, start=1):
        cells[f'A{idx}'] = label
        cells[f'B{idx}'] = value
        cells[f'C{idx}'] = f'=FORMAT.LARGE.NUMBER(B{idx})' if shown == 'large' else shown
        if fmt == 'pct':
            formats[f'C{idx}'] = 1
    return {
        'id': 'datos-cobranza', 'name': 'Datos', 'colNumber': 4, 'rowNumber': len(DATA_ROWS) + 5,
        'rows': {}, 'cols': {'0': {'size': 220}, '1': {'size': 130}, '2': {'size': 130}},
        'merges': [], 'cells': cells, 'styles': {'C1:C%d' % len(DATA_ROWS): 6}, 'formats': formats,
        'borders': {}, 'conditionalFormats': [], 'figures': [], 'tables': [], 'dataValidationRules': [],
        # Oculta: el tablero solo muestra la hoja «Tablero».
        'areGridLinesVisible': True, 'isVisible': False, 'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
    }


# ----------------------------------------------------------------------
# Hoja «Tablero»
# ----------------------------------------------------------------------
FIGURES = []
MENUS = {}
CARD_W, CARD_H, GAP = 235, 109, 20


def scorecard(fid, title, key_row, base_row, base_text, x, y):
    FIGURES.append({
        'id': fid, 'col': 0, 'row': 0, 'offset': {'x': x, 'y': y}, 'width': CARD_W, 'height': CARD_H,
        'tag': 'chart',
        'data': {'type': 'scorecard', 'title': {'text': title, 'color': '#434343', 'bold': True},
                 'background': '#EFF6FF', 'keyValue': f'Datos!C{key_row}', 'baseline': f'Datos!C{base_row}',
                 'baselineMode': 'text', 'baselineDescr': {'text': base_text},
                 'baselineColorUp': '#00A04A', 'baselineColorDown': '#DC6965', 'humanize': False,
                 'chartId': fid},
    })


def odoo_chart(fid, ctype, model, group_by, measure, terms, matching, col, row, width, menu,
               stacked=False, legend='none'):
    data = {
        'type': ctype, 'title': {'text': ''}, 'background': '#FFFFFF', 'legendPosition': legend,
        'metaData': {'groupBy': group_by, 'measure': measure, 'order': None, 'resModel': model,
                     'mode': ctype.removeprefix('odoo_'), 'cumulatedStart': False},
        'searchParams': {'comparison': None, 'context': {}, 'domain': domain(terms),
                         'groupBy': group_by, 'orderBy': []},
        'dataSets': [], 'fieldMatching': matching, 'chartId': fid,
    }
    if ctype in ('odoo_bar', 'odoo_line'):
        data.update(verticalAxisPosition='left', stacked=stacked)
    if ctype == 'odoo_line':
        data.update(fillArea=True, cumulatedStart=False)
    FIGURES.append({'id': fid, 'col': col, 'row': row, 'offset': {'x': 0, 'y': 0}, 'width': width,
                    'height': 345, 'tag': 'chart', 'data': data})
    MENUS[fid] = menu


MENU_PORTFOLIO = 'al_l10n_pe_collection.menu_collection_portfolio'
MENU_PROMISES = 'al_l10n_pe_collection.menu_collection_promises'
MENU_PAYMENTS = 'account.menu_action_account_payments_receivable'

# Indicadores: dos filas de cuatro.
for i, (title, key, base, text) in enumerate([
    ('Cartera', 1, 9, 'clientes'),
    ('Vencido', 2, 10, 'de la cartera'),
    ('Vencido más de 90 días', 3, 11, 'clientes'),
    ('Por vencer', 4, 12, 'clientes'),
    ('Comprometido pendiente', 5, 13, 'compromisos'),
    ('Compromisos cumplidos', 6, 14, 'de los evaluados'),
    ('Cobrado en el periodo', 7, 15, 'cobros'),
    ('Clientes con deuda vencida', 8, 16, 'de los clientes'),
]):
    scorecard(f'kpi-{i + 1}', title, key, base, text, (i % 4) * (CARD_W + GAP), 11 + (i // 4) * (CARD_H + GAP))

# Filas (índice 0) de los títulos de cada bloque; los gráficos van justo debajo.
R_AGING, R_DUE, R_PAID, R_TABLES = 11, 27, 43, 59
TABLE_ROWS = 10

odoo_chart('chart-bucket', 'odoo_bar', PORTFOLIO, ['bucket_id'], 'amount_residual', D_PORTFOLIO,
           MATCH_PORTFOLIO, 0, R_AGING + 1, 475, MENU_PORTFOLIO)
odoo_chart('chart-user', 'odoo_bar', PORTFOLIO, ['user_id', 'bucket_id'], 'amount_residual', D_PORTFOLIO,
           MATCH_PORTFOLIO, 4, R_AGING + 1, 475, MENU_PORTFOLIO, stacked=True, legend='top')
odoo_chart('chart-due', 'odoo_line', PORTFOLIO, ['date_maturity:week'], 'amount_residual',
           D_PORTFOLIO + [('is_overdue', '=', False), ('amount_residual', '>', 0)],
           MATCH_PORTFOLIO, 0, R_DUE + 1, 475, MENU_PORTFOLIO)
odoo_chart('chart-promise', 'odoo_pie', PROMISE, ['state'], 'amount', [('state', '!=', 'cancel')],
           MATCH_PROMISE_AGREED, 4, R_DUE + 1, 475, MENU_PROMISES, legend='top')
odoo_chart('chart-paid', 'odoo_bar', PAYMENT, ['date:month'], 'amount_company_currency_signed', D_PAYMENT,
           MATCH_PAYMENT, 0, R_PAID + 1, 1000, MENU_PAYMENTS)


def dashboard_sheet():
    cells = {
        f'A{R_AGING + 1}': 'Cartera por tramo de antigüedad',
        f'E{R_AGING + 1}': 'Cartera por gestor',
        f'A{R_DUE + 1}': 'Vencimientos por semana',
        f'E{R_DUE + 1}': 'Compromisos pactados por estado',
        f'A{R_PAID + 1}': 'Cobrado por mes',
        f'A{R_TABLES + 1}': 'Clientes con mayor deuda vencida',
        f'E{R_TABLES + 1}': 'Próximos compromisos de pago',
        # Tabla dinámica: la primera fila trae los encabezados de las medidas.
        f'A{R_TABLES + 2}': f'=PIVOT({P_TOP}, {TABLE_ROWS}, FALSE, FALSE)',
    }
    head = R_TABLES + 2
    for col, field, label in (('E', 'partner_id', 'Cliente'), ('F', 'date', 'Fecha'), ('G', 'amount', 'Importe')):
        cells[f'{col}{head}'] = f'=ODOO.LIST.HEADER(1, "{field}", "{label}")'
        for n in range(1, TABLE_ROWS + 1):
            cells[f'{col}{head + n}'] = f'=ODOO.LIST(1,{n},"{field}")'
    first, last = head + 1, head + TABLE_ROWS
    rows = {str(r): {'size': 40} for r in (R_AGING, R_DUE, R_PAID, R_TABLES, R_TABLES + 1)}
    rows.update({str(r): {'size': 27} for r in range(first - 1, last)})
    titles = ','.join(f'{c}{r + 1}' for c in 'AE' for r in (R_AGING, R_DUE, R_PAID, R_TABLES))
    styles = {t: 1 for t in titles.split(',')}
    styles.update({f'A{head}': 2, f'B{head}:C{head}': 5, f'E{head}:G{head}': 2,
                   f'A{first}:A{last}': 3, f'B{first}:C{last}': 4, f'E{first}:G{last}': 4})
    return {
        'id': 'tablero-cobranza', 'name': 'Tablero', 'colNumber': 7, 'rowNumber': last + 3,
        'rows': rows,
        'cols': {'0': {'size': 225}, '1': {'size': 150}, '2': {'size': 100}, '3': {'size': 50},
                 '4': {'size': 225}, '5': {'size': 150}, '6': {'size': 100}},
        'merges': [], 'cells': cells, 'styles': styles, 'formats': {}, 'borders': {},
        'conditionalFormats': [{
            'id': 'barras-deuda', 'ranges': [f'A{first}:A{last}'],
            'rule': {'type': 'DataBarRule', 'color': 16708338, 'rangeValues': f'B{first}:B{last}'},
        }],
        'figures': FIGURES,
        'tables': [
            {'range': f'A{head}:C{last}', 'type': 'static', 'config': TABLE_CONFIG},
            {'range': f'E{head}:G{last}', 'type': 'static', 'config': TABLE_CONFIG},
        ],
        'dataValidationRules': [], 'areGridLinesVisible': False, 'isVisible': True,
        'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
    }


TABLE_CONFIG = {'hasFilters': False, 'totalRow': False, 'firstColumn': False, 'lastColumn': False,
                'numberOfHeaders': 1, 'bandedRows': True, 'bandedColumns': False, 'automaticAutofill': True,
                'styleId': 'None'}


def build():
    return {
        'version': '18.5.10',
        'sheets': [dashboard_sheet(), data_sheet()],
        'styles': {
            '1': {'textColor': '#01666b', 'bold': True, 'fontSize': 16},
            '2': {'textColor': '#434343', 'bold': True, 'fontSize': 11},
            '3': {'textColor': '#01666B', 'verticalAlign': 'middle'},
            '4': {'textColor': '#434343', 'verticalAlign': 'middle'},
            '5': {'textColor': '#434343', 'bold': True, 'fontSize': 11, 'align': 'center'},
            '6': {'fillColor': '#f8f9fa'},
        },
        'formats': {'1': '0.0%'},
        'borders': {},
        'revisionId': 'START_REVISION',
        'uniqueFigureIds': True,
        'settings': {},
        'pivots': PIVOTS,
        'pivotNextId': len(PIVOTS) + 1,
        'customTableStyles': {},
        'globalFilters': GLOBAL_FILTERS,
        'lists': LISTS,
        'listNextId': len(LISTS) + 1,
        'chartOdooMenusReferences': MENUS,
    }


if __name__ == '__main__':
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(OUT)
