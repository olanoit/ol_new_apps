# -*- coding: utf-8 -*-
"""Tipo de cambio de Decolecta.

Tercera fuente, junto a ``sunat_rate`` (TXT oficial del día y apis.net.pe) y
``bcrp_rate`` (series históricas del BCRP). Decolecta publica el tipo de cambio
de SUNAT con compra y venta, admite fecha histórica y responde en un formato
plano y estable.

Endpoint: ``GET https://api.decolecta.com/v1/tipo-cambio/sunat``
Respuesta: ``buy_price``, ``sell_price``, ``base_currency``, ``quote_currency``,
``date``. Autenticación por Bearer token.

Lógica pura (sin ORM): testeable de forma aislada.
"""
import logging
from datetime import datetime

import requests

_logger = logging.getLogger(__name__)

DECOLECTA_URL = 'https://api.decolecta.com/v1/tipo-cambio/sunat'
TIMEOUT = 15


def parse_rate(payload):
    """Convierte la respuesta en ``{'date', 'compra', 'venta'}`` o ``None``.

    Decolecta devuelve la venta en ``sell_price`` y la compra en ``buy_price``.
    Sin venta no hay conversión contable posible, así que se descarta.
    """
    data = payload or {}
    try:
        venta = float(data['sell_price'])
    except (KeyError, TypeError, ValueError):
        return None
    if venta <= 0:
        return None
    try:
        compra = float(data.get('buy_price') or 0.0)
    except (TypeError, ValueError):
        compra = 0.0

    raw_date = data.get('date')
    try:
        rate_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        rate_date = None

    return {'date': rate_date, 'compra': compra or venta, 'venta': venta}


def fetch_decolecta(token, date=None):
    """Tipo de cambio de una fecha (o del día si no se indica).

    Devuelve ``None`` si el servicio no responde o rechaza el token: es una
    fuente más y no debe interrumpir el proceso que la invoca.
    """
    if not token:
        _logger.warning('Decolecta requiere un token de autenticación.')
        return None

    params = {}
    if date:
        params['date'] = date.strftime('%Y-%m-%d')
    try:
        response = requests.get(
            DECOLECTA_URL, params=params, timeout=TIMEOUT,
            headers={'Authorization': 'Bearer %s' % token,
                     'Accept': 'application/json'})
        if response.status_code != 200:
            _logger.warning('Decolecta devolvió HTTP %s: %s',
                            response.status_code, response.text[:200])
            return None
        result = parse_rate(response.json())
    except (requests.RequestException, ValueError) as exc:
        _logger.warning('Decolecta falló: %s', exc)
        return None

    if result and not result['date']:
        # Si la respuesta no trae fecha, se asume la consultada.
        result['date'] = date
    return result if result and result['date'] else None
