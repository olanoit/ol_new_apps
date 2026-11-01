# -*- coding: utf-8 -*-
"""Ayudas para migrar las hojas de trabajo ya creadas (paquete 1.16, CR-22 b,
c, f y M116-09). Python puro: trabajan sobre los datos de o-spreadsheet
(``spreadsheet_binary_data`` y ``spreadsheet_snapshot``); agregan o cambian
formato, nunca borran lo que escribió el usuario."""
import base64
import json
import re
import unicodedata

from .sheet_keys import KEYS_SHEET, col_letter, keys_sheet

CELL_REF = re.compile(r'^([A-Z]+)([0-9]+)$')
NAME_CHAR = re.compile(r'[A-Za-z0-9_.]')


def norm(text):
    text = unicodedata.normalize('NFKD', str(text or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(text.lower().split())


def col_index(letters):
    index = 0
    for char in letters:
        index = index * 26 + ord(char) - 64
    return index - 1


def cell_content(cell):
    if isinstance(cell, dict):
        return cell.get('content')
    return cell


def set_cell_content(cells, ref, content):
    cell = cells.get(ref)
    if isinstance(cell, dict):
        cell['content'] = content
    else:
        cells[ref] = content


def _closing(text, start):
    """Índice del paréntesis que cierra el que abre en ``start``."""
    depth, index, quoted = 0, start, False
    while index < len(text):
        char = text[index]
        if char == '"':
            quoted = not quoted
        elif not quoted:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if not depth:
                    return index
        index += 1
    return -1


def replace_n(formula):
    """``N(x)`` → ``IFERROR(VALUE(x),0)`` (CR-22 c: la hoja de Odoo no tiene
    la función N y la fórmula da #NAME?). Respeta textos entre comillas y
    nombres que terminan en N (MIN, LEN…)."""
    if not isinstance(formula, str) or not formula.startswith('=') or 'N(' not in formula:
        return formula
    result, index, quoted = [], 0, False
    while index < len(formula):
        char = formula[index]
        if char == '"':
            quoted = not quoted
        if not quoted and formula.startswith('N(', index) and (
                index == 0 or not NAME_CHAR.match(formula[index - 1])):
            end = _closing(formula, index + 1)
            if end > 0:
                inner = replace_n('=' + formula[index + 2:end])[1:]
                result.append('IFERROR(VALUE(%s),0)' % inner)
                index = end + 1
                continue
        result.append(char)
        index += 1
    return ''.join(result)


def header_cells(sheet):
    """``{índice de columna: (referencia, texto)}`` de la fila 1."""
    found = {}
    for ref, cell in (sheet.get('cells') or {}).items():
        match = CELL_REF.match(ref)
        if match and match.group(2) == '1':
            content = cell_content(cell)
            if content not in (None, ''):
                found[col_index(match.group(1))] = (ref, str(content))
    return found


def style_id(data, style):
    """Id de un estilo de la hoja (lo agrega si no está)."""
    styles = data.setdefault('styles', {})
    for key, value in styles.items():
        if value == style:
            return int(key)
    new = max([int(key) for key in styles if str(key).isdigit()] + [0]) + 1
    styles[str(new)] = style
    return new


def keys_from_headers(data, columns_by_sheet):
    """``{pestaña: [(clave, índice)]}`` por el texto de los encabezados, con
    ``columns_by_sheet = {pestaña: [(clave, [textos aceptados])]}``."""
    result = {}
    for sheet in data.get('sheets') or []:
        columns = columns_by_sheet.get(sheet.get('name'))
        if not columns:
            continue
        headers = {norm(text): index for index, (_ref, text) in header_cells(sheet).items()}
        found = []
        for key, texts in columns:
            for text in [key] + list(texts):
                if norm(text) in headers:
                    found.append((key, headers[norm(text)]))
                    break
        if found:
            result[sheet['name']] = found
    return result


def add_keys_sheet(data, columns_by_sheet, header_style=None):
    """Agrega la pestaña oculta _CLAVES si no está (M116-09)."""
    sheets = data.get('sheets') or []
    if any(sheet.get('name') == KEYS_SHEET for sheet in sheets):
        return False
    found = keys_from_headers(data, columns_by_sheet)
    if not found:
        return False
    ids = {sheet.get('id') for sheet in sheets}
    sheet_id, number = 'sheet_claves', 1
    while sheet_id in ids:
        number += 1
        sheet_id = 'sheet_claves_%s' % number
    sheets.append(keys_sheet(found, sheet_id=sheet_id, header_style=header_style))
    return True


def paint_headers(data, sheet_names, texts, style):
    """Pone ``style`` al encabezado de las columnas cuyo texto está en
    ``texts`` (CR-22 f, M116-09)."""
    wanted = {norm(text) for text in texts}
    changed = 0
    target = style_id(data, style)
    for sheet in data.get('sheets') or []:
        if sheet.get('name') not in sheet_names:
            continue
        styles = sheet.setdefault('styles', {})
        for _index, (ref, text) in header_cells(sheet).items():
            if norm(text) in wanted and styles.get(ref) != target:
                styles[ref] = target
                changed += 1
    return changed


# La hoja de Odoo 19 no tiene REPT: los tramos de un texto se sacan con
# TEXTBEFORE y TEXTAFTER (nativas). ``text`` es una referencia o expresión y
# ``sep`` el separador entre comillas («" · "», «" / "»).
def last_part(text, sep):
    """Último tramo (todo el texto si no tiene separador)."""
    return 'TRIM(TEXTAFTER(%s&%s,%s,-1))' % (sep, text, sep)


def first_part(text, sep):
    """Primer tramo."""
    return 'TRIM(TEXTBEFORE(%s&%s,%s,1))' % (text, sep, sep)


def second_part(text, sep):
    """Segundo tramo (vacío si no hay)."""
    return 'TRIM(TEXTBEFORE(TEXTAFTER(%s&%s,%s,1)&%s,%s,1))' % (text, sep, sep, sep, sep)


# Cualquier ancho (200 en las plantillas de 1.16, 100 en las anteriores) y
# cualquier separador («" · "», «" / "», «"/"»).
_REPT = r'SUBSTITUTE\(([^,()]+),("[^"]*"),REPT\(" ",\d+\)\)'
_REPT_FORMULAS = (
    (re.compile(r'TRIM\(RIGHT\(%s,\d+\)\)' % _REPT), last_part),
    (re.compile(r'TRIM\(LEFT\(%s,\d+\)\)' % _REPT), first_part),
    (re.compile(r'TRIM\(MID\(%s,\d+,\d+\)\)' % _REPT), second_part),
)


def replace_rept(formula):
    """Reescribe los tramos armados con REPT (que la hoja no tiene y daban
    #NAME?) con TEXTBEFORE y TEXTAFTER."""
    if not isinstance(formula, str) or 'REPT(' not in formula:
        return formula
    for pattern, builder in _REPT_FORMULAS:
        formula = pattern.sub(lambda match, b=builder: b(match.group(1), match.group(2)),
                              formula)
    return formula


def replace_in_cells(data, function):
    """Aplica ``function`` al contenido de cada celda; True si cambió algo."""
    changed = False
    for sheet in data.get('sheets') or []:
        cells = sheet.get('cells') or {}
        for ref, cell in list(cells.items()):
            content = cell_content(cell)
            new = function(content)
            if new != content:
                set_cell_content(cells, ref, new)
                changed = True
    return changed


def _replace_contents(value, function):
    if isinstance(value, dict):
        changed = False
        for key, item in value.items():
            if key == 'content' and isinstance(item, str):
                new = function(item)
                if new != item:
                    value[key] = new
                    changed = True
            elif _replace_contents(item, function):
                changed = True
        return changed
    if isinstance(value, list):
        return any([_replace_contents(item, function) for item in value])
    return False


def migrate_revisions(env, documents, function, marker):
    """Aplica ``function`` al contenido de las celdas que escriben las
    revisiones de las hojas (las que contienen ``marker``)."""
    revisions = env['spreadsheet.revision'].with_context(active_test=False).search([
        ('res_model', '=', 'documents.document'), ('res_id', 'in', documents.ids),
        ('commands', 'ilike', marker)])
    for revision in revisions:
        try:
            commands = json.loads(revision.commands)
        except ValueError:
            continue
        if _replace_contents(commands, function):
            revision.commands = json.dumps(commands)


def migrate_documents(env, documents, transform):
    """Aplica ``transform(data) -> bool`` a los datos y a la última foto de
    cada hoja, sin perder sus revisiones."""
    for document in documents:
        values = {}
        for fname in ('spreadsheet_binary_data', 'spreadsheet_snapshot'):
            raw = document[fname] if fname in document._fields else False
            if not raw:
                continue
            try:
                data = json.loads(base64.b64decode(raw))
            except ValueError:
                continue
            if transform(data):
                values[fname] = base64.b64encode(json.dumps(data).encode())
        if values:
            document.with_context(preserve_spreadsheet_revisions=True).write(values)


def first_free_column(sheet):
    headers = header_cells(sheet)
    return max(headers) + 1 if headers else 0


__all__ = ['add_keys_sheet', 'cell_content', 'col_letter', 'first_free_column', 'first_part',
           'header_cells', 'last_part', 'migrate_documents', 'migrate_revisions', 'norm',
           'paint_headers', 'replace_in_cells', 'replace_n', 'replace_rept', 'second_part',
           'set_cell_content', 'style_id']
