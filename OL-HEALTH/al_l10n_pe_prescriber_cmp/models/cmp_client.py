# -*- coding: utf-8 -*-
"""Consulta del portal «Conoce a tu médico» del Colegio Médico del Perú.

Portado de al_peru_medico_data (Odoo 18) solo en lo que hace falta para
validar al prescriptor, con lxml (viene con Odoo) en lugar de BeautifulSoup:

1. POST de la colegiatura a ``datos-colegiado.php`` → tabla de resultados
   (enlace al detalle, CMP, apellidos, nombres).
2. GET de ``datos-colegiado-detallado.php?id=…`` → estado (HÁBIL o
   INHÁBIL), consejo regional y registros de especialidad.

El portal no tiene API ni contrato: si cambia su HTML o agrega un captcha,
la consulta falla con un mensaje y la receta se valida con los datos a mano.
"""
import re
from urllib.parse import urljoin

import requests
from lxml import html

DEFAULT_BASE_URL = 'https://aplicaciones.cmp.org.pe/conoce_a_tu_medico/'
TIMEOUT = 20
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'es-PE,es;q=0.9',
}


class CmpError(Exception):
    """El portal no respondió o su página no tiene la forma esperada."""


def _text(node):
    return ' '.join(node.text_content().split()) if node is not None else ''


def _tables(document):
    return document.xpath('//table[@border="1"]')


def parse_search(page):
    """Primera fila de la tabla de resultados, o None si no hay resultados."""
    document = html.fromstring(page or '<html/>')
    tables = _tables(document)
    if not tables:
        return None
    for row in tables[0].xpath('.//tr')[1:]:
        cells = row.xpath('./td')
        if len(cells) < 5:
            continue
        links = cells[0].xpath('.//a/@href')
        detail_id = links[0].split('id=')[-1] if links else ''
        return {
            'detail_id': detail_id,
            'code': _text(cells[1]),
            'last_name': ' '.join(filter(None, (_text(cells[2]), _text(cells[3])))),
            'first_name': _text(cells[4]),
        }
    return None


def parse_status(text):
    """«HÁBIL» → enabled; «INHÁBIL» → disabled (se mira INHÁBIL primero: la
    palabra HÁBIL está dentro de INHÁBIL)."""
    text = (text or '').upper().replace('Á', 'A')
    if 'INHABIL' in text:
        return 'disabled'
    if 'HABIL' in text:
        return 'enabled'
    return False


def parse_detail(page):
    document = html.fromstring(page or '<html/>')
    tables = _tables(document)
    data = {'status': False, 'status_text': '', 'council': '', 'email': '', 'specialties': []}
    if len(tables) > 1:
        data['status_text'] = _text(tables[1].xpath('.//td')[0]) if tables[1].xpath('.//td') else ''
        data['status'] = parse_status(data['status_text'])
    if len(tables) > 2:
        for cell in tables[2].xpath('.//td'):
            value = _text(cell)
            if '@' in value and not data['email']:
                data['email'] = value
            elif re.search(r'CONSEJO\s+REGIONAL', value, re.I) and not data['council']:
                data['council'] = value
    if len(tables) > 3:
        for row in tables[3].xpath('.//tr')[1:]:
            cells = row.xpath('./td')
            if cells and _text(cells[0]):
                data['specialties'].append(_text(cells[0]))
    return data


def fetch(code, base_url=DEFAULT_BASE_URL, session=None):
    """Datos del médico con colegiatura ``code``, o None si no existe."""
    session = session or requests.Session()
    base_url = base_url if base_url.endswith('/') else base_url + '/'
    try:
        session.get(urljoin(base_url, 'index.php'), headers=HEADERS, timeout=TIMEOUT)
        response = session.post(
            urljoin(base_url, 'datos-colegiado.php'),
            data={'cmp': code, 'appaterno': '', 'apmaterno': '', 'nombres': ''},
            headers={**HEADERS, 'Referer': urljoin(base_url, 'index.php')}, timeout=TIMEOUT)
        response.raise_for_status()
        found = parse_search(response.text)
        if not found:
            return None
        detail = {}
        if found['detail_id']:
            response = session.get(
                urljoin(base_url, 'datos-colegiado-detallado.php?id=%s' % found['detail_id']),
                headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            detail = parse_detail(response.text)
    except requests.RequestException as error:
        raise CmpError(str(error)) from error
    return {**found, **detail}
