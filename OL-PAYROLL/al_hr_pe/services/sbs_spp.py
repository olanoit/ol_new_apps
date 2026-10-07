# -*- coding: utf-8 -*-
"""Comisiones y primas del SPP publicadas por la SBS.

No hay API ni datos abiertos oficiales: la única fuente es la tabla de
https://www.sbs.gob.pe/app/spp/empleadores/comisiones_spp/Paginas/comision_prima.aspx
(«Al mes de devengue AAAA-MM»). La página está detrás de Incapsula, que
responde con un desafío JavaScript a los User-Agent que imitan navegadores;
con uno propio y sencillo devuelve la tabla (verificado el 07/10/2026).

Todo lo leído se valida (las cuatro AFP, rangos plausibles); si algo no
cuadra no se devuelve nada y no se toca ninguna tasa.
"""
import html
import logging
import re

import requests

_logger = logging.getLogger(__name__)

SBS_SPP_URL = ('https://www.sbs.gob.pe/app/spp/empleadores/comisiones_spp/'
               'Paginas/comision_prima.aspx')
TIMEOUT = 30
AFP_NAMES = ('HABITAT', 'INTEGRA', 'PRIMA', 'PROFUTURO')
# User-Agent honesto y sencillo: uno que imita a Chrome dispara el desafío
# JavaScript de Incapsula (que un cliente HTTP no resuelve); este no.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; Odoo al_hr_pe)',
    'Accept': 'text/html',
}


def _number(text):
    """«1,47%» → 1.47; «12 732,70» → 12732.70."""
    text = html.unescape(text).replace('%', '').replace('\xa0', ' ')
    text = re.sub(r'\s+', '', text).replace('.', '').replace(',', '.')
    return float(text)


def parse_sbs_spp(page):
    """Tabla de la página → ``{'period': 'AAAA-MM', 'afp': {NOMBRE: {...}}}``
    o ``None`` si no está completa o no es plausible."""
    period = re.search(r'id="lblMes1"[^>]*>\s*(\d{4}-\d{2})\s*<', page)
    rows = {}
    for row in re.findall(r'<tr[^>]*JER_filaContenido[^>]*>(.*?)</tr>',
                          page, flags=re.S):
        cells = [re.sub(r'<[^>]+>', '', cell).strip()
                 for cell in re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)]
        cells = [cell for cell in cells if cell]
        if len(cells) < 6 or cells[0].upper() not in AFP_NAMES:
            continue
        try:
            rows[cells[0].upper()] = {
                'flow_commission': _number(cells[1]),
                'balance_commission': _number(cells[2]),
                'prima_insurance': _number(cells[3]),
                'retirement_fund': _number(cells[4]),
                'insurable_remuneration': _number(cells[5]),
            }
        except ValueError:
            return None
    if not period or set(rows) != set(AFP_NAMES):
        return None
    for values in rows.values():
        if not (0 < values['flow_commission'] < 5
                and 0 < values['prima_insurance'] < 5
                and 5 <= values['retirement_fund'] <= 15
                and 5000 < values['insurable_remuneration'] < 50000):
            return None
    return {'period': period.group(1), 'afp': rows}


def fetch_sbs_spp():
    """Descarga y lee la tabla vigente; ``None`` si no se pudo."""
    session = requests.Session()
    try:
        for _attempt in range(3):
            response = session.get(SBS_SPP_URL, headers=HEADERS,
                                   timeout=TIMEOUT)
            response.raise_for_status()
            data = parse_sbs_spp(response.text)
            if data:
                return data
            # Si llegó el desafío de Incapsula, se reintenta con las
            # cookies de la sesión.
        _logger.warning('SBS: la tabla de comisiones no se pudo leer.')
    except requests.RequestException as exc:
        _logger.warning('SBS: error al consultar comisiones del SPP: %s', exc)
    return None
