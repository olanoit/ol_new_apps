# -*- coding: utf-8 -*-
"""Clave interna de columna de las hojas de trabajo (paquete 1.16, M116-09 y
CR-22 d).

La hoja de cálculo de Odoo 19 no tiene notas de celda ni rangos con nombre, y
una fila técnica arriba correría las fórmulas de las hojas ya creadas. La
pestaña oculta ``_CLAVES`` guarda, por columna leída, la pestaña, la clave y
``=COLUMN(<pestaña>!<encabezado>)``: la hoja corrige esa referencia cuando se
insertan, mueven o borran columnas, y renombrar el encabezado no la cambia.
Al enviar, el encabezado de cada columna se reemplaza por su clave; los dos
importadores reconocen la clave como encabezado.

Python puro: lo usan las plantillas, el envío y las migraciones.
"""
import re

KEYS_SHEET = '_CLAVES'
KEYS_HEADERS = ['Pestaña', 'Clave', 'Columna']


def col_letter(index):
    """Letra de la columna (0 → A, 26 → AA)."""
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def sheet_ref(name):
    """Nombre de la pestaña para una fórmula (con comillas si hace falta)."""
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
        return name
    return "'%s'" % name.replace("'", "''")


def keys_rows(columns_by_sheet):
    """Filas de ``_CLAVES``: ``{pestaña: [(clave, índice de columna)]}``."""
    rows = [list(KEYS_HEADERS)]
    for sheet, columns in columns_by_sheet.items():
        for key, index in columns:
            rows.append([sheet, key, '=COLUMN(%s!%s1)' % (sheet_ref(sheet), col_letter(index))])
    return rows


def keys_sheet(columns_by_sheet, sheet_id='sheet_claves', header_style=None):
    """Pestaña oculta ``_CLAVES`` (datos de o-spreadsheet)."""
    cells, styles = {}, {}
    for number, row in enumerate(keys_rows(columns_by_sheet), start=1):
        for index, value in enumerate(row):
            cells['%s%s' % (col_letter(index), number)] = value
    if header_style:
        styles = {'%s1' % col_letter(i): header_style for i in range(len(KEYS_HEADERS))}
    return {'id': sheet_id, 'name': KEYS_SHEET, 'colNumber': 4,
            'rowNumber': max(len(cells) // 3 + 10, 50), 'cells': cells, 'styles': styles,
            'isVisible': False}


def keys_by_sheet(sheets):
    """``{pestaña: {índice de columna (0): clave}}`` desde los valores
    calculados de ``_CLAVES``; las columnas borradas (``#REF``) no están."""
    result = {}
    for row in (sheets or {}).get(KEYS_SHEET) or []:
        if len(row) < 3 or row[0] in KEYS_HEADERS[:1]:
            continue
        sheet, key, column = row[0], row[1], row[2]
        if not sheet or not key or isinstance(column, bool) or \
                not isinstance(column, (int, float)) or column < 1:
            continue
        result.setdefault(str(sheet), {})[int(column) - 1] = str(key)
    return result


def apply_keys(sheets):
    """Copia de ``sheets`` sin ``_CLAVES`` y con la clave como encabezado de
    cada columna que la tiene."""
    mapping = keys_by_sheet(sheets)
    result = {}
    for name, rows in (sheets or {}).items():
        if name == KEYS_SHEET:
            continue
        rows = [list(row) for row in rows or []]
        columns = mapping.get(name)
        if columns and rows:
            header = rows[0]
            width = max(columns) + 1
            if len(header) < width:
                header.extend([''] * (width - len(header)))
            for index, key in columns.items():
                header[index] = key
        result[name] = rows
    return result


def headers_to_keys(header_row, columns):
    """``[(clave, índice)]`` de una fila de encabezados, con ``columns`` =
    ``[(clave, [textos aceptados])]`` y ``norm`` aplicado por quien llama."""
    found = []
    for key, texts in columns:
        for index, text in enumerate(header_row):
            if text in texts:
                found.append((key, index))
                break
    return found
