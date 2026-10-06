# -*- coding: utf-8 -*-
"""Lectura de la página de apéndices del SPOT de SUNAT.

https://orientacion.sunat.gob.pe/apendices-del-sistema-de-detracciones

No hay un servicio con el catálogo vigente: la página es HTML y cuenta la
historia de los anexos de la R.S. 183-2004/SUNAT. Trae dos clases de tablas:

* una con **CÓDIGO / TIPO DE BIEN O SERVICIO** (el catálogo 54), fiable;
* varias de **DEFINICIÓN / DESCRIPCIÓN / %**, cada una con la fecha desde la
  que rige («% Desde el 01.04.2018»), numeradas por anexo y **sin código**.

El porcentaje de un código se obtiene cruzando por nombre y quedándose con
la tabla de fecha más reciente. Por eso el resultado solo sirve para
contrastar: lo aplica una persona.
"""
import re
import unicodedata
from datetime import date

from lxml import html as lxml_html

MIN_CODES = 20
RATE = re.compile(r'(\d+(?:[.,]\d+)?)\s*%')
HEADER_DATE = re.compile(r'(\d{2})[./](\d{2})[./](\d{4})')


class SpotPageError(ValueError):
    """La página no trae el catálogo reconocible."""


def normalize(text):
    """Nombre comparable: sin tildes, notas «(3) y (13)» ni puntuación."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r'\(\s*\d+\s*\)?', ' ', text)      # «(3)», «(4», «13)»
    text = re.sub(r'\b\d+\s*\)', ' ', text)
    text = re.sub(r'[^a-z0-9ñ]+', ' ', text)
    text = re.sub(r'(\s+y)+\s*$', '', text.strip())   # «… (3) y (13)»
    return re.sub(r'\s+', ' ', text).strip()


def _cells(row):
    return [re.sub(r'\s+', ' ', cell.text_content()).strip()
            for cell in row.xpath('./td|./th')]


def _same(name_a, name_b):
    """Mismo concepto: iguales o uno empieza por el otro (la página corta
    algunas definiciones largas en una tabla y no en otra)."""
    if name_a == name_b:
        return True
    shorter, longer = sorted((name_a, name_b), key=len)
    return len(shorter) >= 12 and longer.startswith(shorter)


def parse_html(content):
    """``{'codes': {código: (nombre, anexo1)}, 'rates': {código: (%, fecha)}}``.

    El código va con tres dígitos, como en el catálogo 54. ``anexo1`` indica
    la nota «(1)» de la tabla de códigos (bienes del Anexo 1, con mínimo de
    media UIT). La fecha es ``None`` en las tablas que no la indican.
    """
    if isinstance(content, bytes):
        # Sin <meta charset>, lxml supone latin-1 y «CÓDIGO» deja de
        # reconocerse: se decodifica antes (SUNAT publica en UTF-8).
        try:
            content = content.decode('utf-8')
        except UnicodeDecodeError:
            content = content.decode('cp1252', errors='replace')
    try:
        doc = lxml_html.fromstring(content)
    except Exception as error:  # noqa: BLE001 - HTML ilegible
        raise SpotPageError('No se pudo leer la página: %s' % error) from error

    codes, rate_rows = {}, []
    for table in doc.xpath('//table'):
        rows = [cells for cells in map(_cells, table.xpath('.//tr')) if any(cells)]
        if not rows:
            continue
        header = [normalize(cell) for cell in rows[0]]
        if header[:1] == ['codigo'] and len(header) >= 2:
            for cells in rows[1:]:
                if len(cells) >= 2 and cells[0].isdigit():
                    codes[cells[0].zfill(3)] = (
                        re.sub(r'\s*\(\d+\)?\s*$', '', cells[1]).strip(),
                        bool(re.search(r'\(1\)', cells[1])))
            continue
        if 'definicion' not in header:
            continue
        found = HEADER_DATE.search(rows[0][-1])
        since = date(int(found[3]), int(found[2]), int(found[1])) if found else None
        name_col = header.index('definicion')
        for cells in rows[1:]:
            # Las filas numeradas traen una celda más que la cabecera.
            offset = len(cells) - len(header)
            if offset < 0 or len(cells) <= name_col + offset:
                continue
            rate = RATE.search(cells[-1])
            name = normalize(cells[name_col + offset])
            if rate and name:
                rate_rows.append((name, float(rate[1].replace(',', '.')), since))

    if len(codes) < MIN_CODES:
        raise SpotPageError(
            'No se encontró la tabla de códigos del catálogo (%s códigos).' % len(codes))

    rates = {}
    for code, (name, _annex1) in codes.items():
        key = normalize(name)
        matches = [(since or date.min, rate) for row_name, rate, since in rate_rows
                   if _same(key, row_name)]
        if matches:
            since, rate = max(matches)
            rates[code] = (rate, None if since == date.min else since)
    return {'codes': codes, 'rates': rates}
