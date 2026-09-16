# -*- coding: utf-8 -*-
"""Lectura de la tabla salarial del convenio desde su PDF.

CAPECO y la FTCCP publican la tabla del convenio solo en PDF; no hay un
servicio del que leerla. Los dos PDF tienen texto extraíble, pero el
extractor rompe palabras y números a su antojo («Jornal B ásico 89.30
*6días535.8 0»), así que se buscan los datos en el texto **sin espacios**:
los importes siempre llevan dos decimales y eso basta para separarlos
aunque queden pegados.

Las tres primeras apariciones de cada dato son la tabla base, en el orden
en que ambos PDF la imprimen: operario, oficial y peón. Las páginas
siguientes de CAPECO repiten al operario con cada BAE y se ignoran.
"""
import io
import re
import unicodedata
from datetime import date

from odoo.tools.pdf import PdfReader

AMOUNT = r'(\d{1,3}(?:,\d{3})*\.\d{2})'
CATEGORIES = ('operario', 'oficial', 'peon')

PATTERNS = {
    'daily_wage': r'JORNALB[ÁA]SICO' + AMOUNT,
    'mobility': r'MOVILIDAD(?:\(\*+\))?' + AMOUNT,
    'buc_percent': r'B\.?U\.?C\.?(\d{2})%',
    'conafovicer': r'CONAF[A-Z]*\.?(\d+(?:\.\d+)?)%(?:\(\*+\))?' + AMOUNT,
    'pension': r'(?:ONP|S\.N\.P\.)(\d+(?:\.\d+)?)%' + AMOUNT,
    'net': r'NETOSEMANAL' + AMOUNT,
}
VALIDITY = (r'VIGENTES?DEL(\d{2})[./](\d{2})[./](\d{4})'
            r'AL(\d{2})[./](\d{2})[./](\d{4})')
RESOLUTION = r'R(?:ESOLUCI[ÓO]N)?\.?M(?:INISTERIAL)?\.?N[°º.]*(\d+-\d{4}-TR)'


class WageTablePdfError(ValueError):
    """El PDF no trae una tabla salarial reconocible."""


def _amount(text):
    return float(text.replace(',', ''))


def pdf_text(content):
    """Texto de todas las páginas del PDF."""
    try:
        reader = PdfReader(io.BytesIO(content))
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    except Exception as error:  # noqa: BLE001 - cualquier PDF ilegible
        raise WageTablePdfError('No se pudo leer el PDF: %s' % error) from error


def flatten(text):
    """Texto en mayúsculas y sin espacios, con los acentos compuestos."""
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', text)).upper()


def parse_text(text):
    """Datos de la tabla base a partir del texto del PDF.

    Devuelve ``{'date_from', 'date_to', 'resolution', 'categories'}``,
    donde cada categoría trae jornal, movilidad, BUC %, las tasas y los
    importes semanales que publica el convenio (CONAFOVICER, pensión y
    neto), que sirven para comprobar la lectura.
    """
    flat = flatten(text)
    validity = re.search(VALIDITY, flat)
    if not validity:
        raise WageTablePdfError(
            'No se encontró la vigencia («Vigente del … al …»).')
    d1, m1, y1, d2, m2, y2 = (int(value) for value in validity.groups())
    try:
        date_from, date_to = date(y1, m1, d1), date(y2, m2, d2)
    except ValueError as error:
        raise WageTablePdfError('Vigencia inválida: %s' % error) from error

    found = {}
    for key, pattern in PATTERNS.items():
        matches = re.findall(pattern, flat)
        if len(matches) < len(CATEGORIES):
            raise WageTablePdfError(
                'No se encontró «%s» para las tres categorías.' % key)
        found[key] = matches[:len(CATEGORIES)]

    categories = {}
    for index, category in enumerate(CATEGORIES):
        conaf_rate, conaf_amount = found['conafovicer'][index]
        pension_rate, pension_amount = found['pension'][index]
        categories[category] = {
            'daily_wage': _amount(found['daily_wage'][index]),
            'mobility': _amount(found['mobility'][index]),
            'buc_percent': float(found['buc_percent'][index]),
            'conafovicer_rate': float(conaf_rate),
            'conafovicer': _amount(conaf_amount),
            'pension_rate': float(pension_rate),
            'pension': _amount(pension_amount),
            'net': _amount(found['net'][index]),
        }

    resolution = re.search(RESOLUTION, flat)
    return {
        'date_from': date_from,
        'date_to': date_to,
        'resolution': 'R.M. N.° %s' % resolution.group(1) if resolution else '',
        'categories': categories,
    }


def parse_pdf(content):
    if not content or not content.startswith(b'%PDF'):
        raise WageTablePdfError('El archivo no es un PDF.')
    return parse_text(pdf_text(content))
