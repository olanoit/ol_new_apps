# -*- coding: utf-8 -*-
"""Obtención del tipo de cambio SUNAT (compra/venta) para USD/PEN.

Dos fuentes, ambas devuelven ``{'date': date, 'compra': float, 'venta': float}``
o ``None`` si fallan:

* ``fetch_sunat_txt``  — TXT oficial de SUNAT, gratuito y sin token, pero solo
  del día publicado. Es la fuente principal (la misma que usa el provider
  nativo ``bcrp`` de Odoo, aquí ampliada para leer también la compra).
* ``fetch_apis_net``   — apis.net.pe, admite fecha histórica (best-effort;
  puede requerir token o estar limitada por rate-limit).

Lógica pura (sin ORM): testeable de forma aislada.
"""
import logging
from datetime import datetime

import requests

_logger = logging.getLogger(__name__)

SUNAT_TXT_URL = 'https://www.sunat.gob.pe/a/txt/tipoCambio.txt'
APIS_NET_URL = 'https://api.apis.net.pe/v1/tipo-cambio-sunat'
TIMEOUT = 10


def fetch_sunat_txt():
    """TXT oficial de SUNAT. Formato de línea: ``dd/mm/aaaa|compra|venta|``."""
    try:
        res = requests.get(SUNAT_TXT_URL, timeout=TIMEOUT)
        res.raise_for_status()
        line = (res.text.splitlines() or [''])[0]
        parts = line.split('|')
        return {
            'date': datetime.strptime(parts[0].strip(), '%d/%m/%Y').date(),
            'compra': float(parts[1]),
            'venta': float(parts[2]),
        }
    except (requests.RequestException, ValueError, IndexError) as exc:
        _logger.warning('SUNAT TXT falló: %s', exc)
        return None


def fetch_apis_net(date=None, token=''):
    """apis.net.pe. Con ``date`` consulta una fecha histórica."""
    url = APIS_NET_URL + (('?fecha=%s' % date.strftime('%Y-%m-%d')) if date else '')
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer %s' % token
    try:
        res = requests.get(url, headers=headers, timeout=TIMEOUT)
        if res.status_code != 200:
            _logger.warning('apis.net.pe %s → HTTP %s', url, res.status_code)
            return None
        data = res.json() or {}
        fecha = data.get('fecha')
        return {
            'date': datetime.strptime(fecha, '%Y-%m-%d').date() if fecha else date,
            'compra': float(data['compra']),
            'venta': float(data['venta']),
        }
    except (requests.RequestException, ValueError, KeyError) as exc:
        _logger.warning('apis.net.pe falló: %s', exc)
        return None
