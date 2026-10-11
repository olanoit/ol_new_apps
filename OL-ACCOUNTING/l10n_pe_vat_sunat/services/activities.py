# -*- coding: utf-8 -*-
"""Interpretación del texto de las actividades económicas de la ficha RUC.

SUNAT las publica como «Principal - 4711 - VENTA AL POR MENOR…» o
«Secundaria 1 - 6201 - PROGRAMACIÓN…» (CIIU Rev. 4); las fichas antiguas
traen «Principal - CIIU 52110 - VTA. MIN. …» (CIIU Rev. 3, cinco dígitos).
Algunas API devuelven solo la descripción o «4711 - DESCRIPCIÓN».
"""
import re

_PATTERN = re.compile(
    r'^\s*(?:(?P<kind>principal|secundaria)\s*(?P<num>\d*)\s*-\s*)?'
    r'(?:(?:ciiu\s*)?(?P<code>\d{4,5})\s*-\s*)?'
    r'(?P<name>.*?)\s*$',
    re.IGNORECASE)


def parse(text):
    """Devuelve ``(tipo, código, descripción)``: tipo ``principal`` o
    ``secondary`` (sin prefijo: ``None``), código de 4 o 5 dígitos o ``''``."""
    match = _PATTERN.match(text or '')
    if not match:
        return None, '', (text or '').strip()
    kind = match.group('kind')
    kind = (('principal' if kind.lower() == 'principal' else 'secondary') if kind else None)
    return kind, match.group('code') or '', ' '.join(match.group('name').split())


def parse_all(texts):
    """Lista de dicts ``{kind, code, name}`` sin vacías; la primera sin tipo
    explícito se toma como principal y las demás como secundarias."""
    result = []
    for text in texts or []:
        kind, code, name = parse(text)
        if not code and not name:
            continue
        if kind is None:
            kind = 'principal' if not result else 'secondary'
        result.append({'kind': kind, 'code': code, 'name': name})
    return result
