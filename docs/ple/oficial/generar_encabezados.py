#!/usr/bin/env python3
"""Genera los encabezados del Excel de revisión desde el Anexo 2 de SUNAT.

    python docs/ple/oficial/generar_encabezados.py          # escribe el módulo
    python docs/ple/oficial/generar_encabezados.py --check  # ¿está al día?

Lee ``Estructura del PLE.xls`` (hojas «1 Libro Caja y Bancos» … «14 Registro
de Ventas»), toma de cada formato la columna «Descripción» de sus campos
numerados —los «Campos de libre utilización» no van en el TXT— y escribe
``al_l10n_pe_ple/models/ple_official_headers.py``.

Cada formato debe tener tantos campos como valida el módulo
(``PLE_EXPECTED_FIELDS``); si no, el script falla en vez de generar un Excel
con las columnas corridas.
"""
import re
import sys
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent / 'Estructura del PLE.xls'
TARGET = ROOT / 'al_l10n_pe_ple' / 'models' / 'ple_official_headers.py'
MIXIN = ROOT / 'al_l10n_pe_ple' / 'models' / 'ple_mixin.py'

TITLE = re.compile(r'^(\d+)\.(\d+)(?:\.(\d+))?\s')
FIELD = re.compile(r'^(\d+)(?:\.0)?$')
MAX_LENGTH = 90


def book_code(match):
    book, fmt, sub = match.groups()
    return '%02d%02d%02d' % (int(book), int(fmt), int(sub or 0))


def short(description):
    """Encabezado legible: la descripción sin su explicación.

    «Código Único de la Operación (CUO), que es la llave única…» queda en
    «Código Único de la Operación (CUO)».
    """
    text = ' '.join(str(description).split())
    for cut in (', que ', '. ', '; ', ': '):
        if cut in text:
            text = text.split(cut, 1)[0]
    text = text.rstrip(' .,;:')
    text = text[:1].upper() + text[1:]
    if len(text) > MAX_LENGTH:
        text = text[:MAX_LENGTH].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'
    return text


def read_structures():
    """``{código: {número de campo: descripción}}`` de todas las hojas."""
    book = xlrd.open_workbook(str(SOURCE))
    structures = {}
    for sheet in book.sheets():
        if not re.match(r'^\d', sheet.name):
            continue
        current = None
        for row in range(sheet.nrows):
            first = str(sheet.cell_value(row, 0)).strip()
            title = TITLE.match(first)
            if title:
                current = structures.setdefault(book_code(title), {})
                continue
            number = FIELD.match(first)
            if current is not None and number and sheet.ncols > 4:
                description = str(sheet.cell_value(row, 4)).strip()
                if description:
                    current[int(number.group(1))] = description
    return structures


def expected_fields():
    text = MIXIN.read_text(encoding='utf-8')
    block = text[text.index('PLE_EXPECTED_FIELDS = {'):]
    block = block[:block.index('\n}')]
    return {code: int(count) for code, count in re.findall(r"'(\d{6})': (\d+)", block)}


def render(structures, expected):
    headers, errors = {}, []
    for code, count in sorted(expected.items()):
        fields = structures.get(code)
        if not fields:
            continue  # SIRE (8.4, 8.5, 14.4): no están en el Anexo 2
        numbers = sorted(fields)
        if numbers != list(range(1, count + 1)):
            errors.append('%s: el Anexo 2 trae los campos %s y el módulo valida %s'
                          % (code, numbers, count))
            continue
        headers[code] = [short(fields[n]) for n in numbers]
    if errors:
        raise SystemExit('\n'.join(errors))

    lines = [
        '# -*- coding: utf-8 -*-',
        '"""Encabezados de los formatos PLE según el Anexo 2 de SUNAT.',
        '',
        'ARCHIVO GENERADO: no editar a mano. Fuente:',
        '``docs/ple/oficial/Estructura del PLE.xls``; se regenera con',
        '``docs/ple/oficial/generar_encabezados.py``.',
        '"""',
        '',
        'PLE_OFFICIAL_HEADERS = {',
    ]
    for code, names in headers.items():
        lines.append('    %r: [' % code)
        lines.extend('        %r,' % name for name in names)
        lines.append('    ],')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def main(argv):
    content = render(read_structures(), expected_fields())
    current = TARGET.read_text(encoding='utf-8') if TARGET.exists() else ''
    if '--check' in argv:
        if content != current:
            print('desfasado: %s' % TARGET.relative_to(ROOT))
            return 1
        print('al día')
        return 0
    TARGET.write_text(content, encoding='utf-8')
    print('generado %s (%s formatos)' % (TARGET.relative_to(ROOT), content.count(': [')))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
