# -*- coding: utf-8 -*-
"""Tipo de cambio del BCRP (Banco Central de Reserva del Perú).

Complementa a ``sunat_rate``: el TXT de SUNAT solo publica el día en curso y
apis.net.pe puede exigir token o limitar por frecuencia, mientras que el BCRP
expone series históricas completas, gratuitas y sin autenticación.

Se usan las series del **sistema bancario SBS**, que son las que corresponden
al tipo de cambio publicado por la SBS y que SUNAT toma para efectos
tributarios; no las interbancarias, que son otra cosa:

* ``PD04639PD`` — TC Sistema bancario SBS (S/ por US$) · Compra
* ``PD04640PD`` — TC Sistema bancario SBS (S/ por US$) · Venta

**Ojo con la fecha.** El BCRP fecha cada valor con el día del cierre SBS,
mientras que SUNAT publica ese cierre como tipo de cambio del día siguiente
(y lo mantiene los días sin publicación): el T.C. SUNAT del lunes es el cierre
del viernes anterior. Verificado el 06/10/2026: SUNAT 06/10 = BCRP 05.Oct
(3.423 / 3.435) y SUNAT 03, 04 y 05/10 = BCRP 02.Oct (3.437 / 3.442).
``to_sunat_dates`` hace esa traslación.

Lógica pura (sin ORM): testeable de forma aislada.
"""
import logging
import time
from datetime import datetime, timedelta

import requests

_logger = logging.getLogger(__name__)

BCRP_URL = ('https://estadisticas.bcrp.gob.pe/estadisticas/series/api/'
            '%(series)s/json/%(date_from)s/%(date_to)s')
BCRP_SERIES_BUY = 'PD04639PD'
BCRP_SERIES_SELL = 'PD04640PD'
TIMEOUT = 20
ATTEMPTS = 3
RETRY_SECONDS = 2

# El BCRP nombra los periodos como «02.Mar.26», con el mes abreviado en
# castellano; la abreviatura no coincide siempre con la de ``strptime``.
BCRP_MONTHS = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'set': 9, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}


def parse_period(name):
    """«02.Mar.26» → ``date(2026, 3, 2)``. Devuelve ``None`` si no encaja."""
    try:
        day, month, year = (name or '').strip().split('.')
        month_number = BCRP_MONTHS.get(month.strip().lower()[:3])
        if not month_number:
            return None
        year = int(year)
        # El BCRP abrevia el año a dos dígitos.
        if year < 100:
            year += 2000
        return datetime(year, month_number, int(day)).date()
    except (ValueError, AttributeError):
        return None


def parse_value(raw):
    """Convierte el valor de la serie; «n.d.» y vacíos devuelven ``None``."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def parse_response(payload):
    """Convierte la respuesta del BCRP en ``[{'date', 'compra', 'venta'}, …]``.

    Las dos series se piden juntas, así que cada periodo trae los valores en el
    orden en que se pidieron: primero compra, después venta.
    """
    rates = []
    for period in (payload or {}).get('periods') or []:
        rate_date = parse_period(period.get('name'))
        values = period.get('values') or []
        if not rate_date or len(values) < 2:
            continue
        compra, venta = parse_value(values[0]), parse_value(values[1])
        if not venta:
            # Sin tipo de cambio venta no hay conversión contable posible.
            continue
        rates.append({'date': rate_date, 'compra': compra or venta,
                      'venta': venta})
    return rates


def to_sunat_dates(rates, date_from, date_to):
    """Traslada los cierres SBS del BCRP a las fechas de SUNAT.

    Cada día del rango ``[date_from, date_to]`` toma el último cierre
    **anterior** a ese día, como hace SUNAT al publicar. Los días sin cierre
    previo en ``rates`` se omiten. ``rates`` debe venir ordenado por fecha.
    """
    result = []
    index, current = 0, None
    day = date_from
    while day <= date_to:
        while index < len(rates) and rates[index]['date'] < day:
            current = rates[index]
            index += 1
        if current:
            result.append({'date': day, 'compra': current['compra'],
                           'venta': current['venta'], 'close_date': current['date']})
        day += timedelta(days=1)
    return result


#: Días hacia atrás que se piden al BCRP para tener el cierre anterior al
#: primer día del rango (fines de semana largos, feriados de Semana Santa…).
LOOKBACK_DAYS = 10


def fetch_bcrp(date_from, date_to):
    """Tipos de cambio SBS del rango, ordenados por fecha.

    Devuelve una lista vacía si el servicio no responde: es una fuente de
    respaldo y no debe interrumpir el proceso que la invoca.
    """
    url = BCRP_URL % {
        'series': '%s-%s' % (BCRP_SERIES_BUY, BCRP_SERIES_SELL),
        'date_from': date_from.strftime('%Y-%m-%d'),
        'date_to': date_to.strftime('%Y-%m-%d'),
    }
    # El BCRP devuelve a veces una respuesta vacía o que no es JSON (visto el
    # 07/10/2026 en dos consultas seguidas): se reintenta antes de rendirse.
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT,
                                    headers={'Accept': 'application/json'})
            response.raise_for_status()
            return sorted(parse_response(response.json()),
                          key=lambda rate: rate['date'])
        except (requests.RequestException, ValueError) as exc:
            _logger.warning('BCRP falló para %s..%s (intento %s de %s): %s',
                            date_from, date_to, attempt, ATTEMPTS, exc)
            if attempt < ATTEMPTS:
                time.sleep(RETRY_SECONDS * attempt)
    return []
