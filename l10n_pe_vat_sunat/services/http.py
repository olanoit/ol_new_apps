# -*- coding: utf-8 -*-
"""Cliente HTTP centralizado con timeouts y reintentos.

Todas las llamadas a APIs externas de RUC/DNI deben pasar por estas
funciones para garantizar:

  * Timeout uniforme (evita que un servicio caído cuelgue la sesión
    del usuario).
  * Reintentos limitados con backoff exponencial en errores
    transitorios (5xx, timeout, ConnectionError).
  * Logging consistente para diagnóstico.
  * User-Agent neutro reutilizable (algunos servicios bloquean el
    UA por defecto de ``python-requests``).
"""
import logging
import time

import requests

_logger = logging.getLogger(__name__)


# Timeout (conexión, lectura) en segundos. 15s lectura es agresivo
# pero los servicios de RUC/DNI deben responder rápido o no responder.
DEFAULT_TIMEOUT = (5, 15)

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
)

# Errores que vale la pena reintentar.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class HttpError(Exception):
    """Error normalizado para fallos de red/HTTP.

    Atributos:
      * ``status_code``: int (o ``None`` si fue error de red previo).
      * ``body``: cuerpo de la respuesta truncado, para diagnóstico.
      * ``service``: nombre del servicio (apiperu, apis.net.pe, ...).
    """

    def __init__(self, message, status_code=None, body='', service=''):
        super().__init__(message)
        self.status_code = status_code
        self.body = (body or '')[:300]
        self.service = service


def request(method, url, *, service='', headers=None, params=None,
            data=None, json=None, timeout=DEFAULT_TIMEOUT,
            retries=2, backoff=1.5, session=None):
    """Llamada HTTP con timeout y reintentos.

    Args:
        method: ``'GET'`` / ``'POST'`` / ...
        url: endpoint completo.
        service: nombre del servicio para logging/errors.
        headers, params, data, json: pasados a ``requests``.
        timeout: tupla ``(conexión, lectura)`` o int.
        retries: número de reintentos en errores transitorios
            (5xx, 429, ConnectionError, Timeout). Default 2.
        backoff: factor multiplicativo entre reintentos (1.5 → 1s, 1.5s, 2.25s).
        session: ``requests.Session`` opcional para reutilizar
            conexiones / cookies dentro de un flujo (p.ej. SUNAT).

    Returns:
        ``requests.Response``.

    Raises:
        ``HttpError`` con detalles si tras los reintentos sigue
        fallando. El llamador puede inspeccionar ``status_code`` y
        ``body``.
    """
    headers = {'User-Agent': DEFAULT_USER_AGENT, **(headers or {})}
    do_get = (session or requests).request

    delay = 0.7
    last_exc = None
    for attempt in range(retries + 1):
        try:
            response = do_get(
                method=method, url=url,
                headers=headers, params=params, data=data, json=json,
                timeout=timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            _logger.warning(
                '[%s] %s %s: error de red (intento %d/%d): %s',
                service or 'http', method, url, attempt + 1,
                retries + 1, exc,
            )
            if attempt >= retries:
                raise HttpError(
                    'Error de red contactando a %s: %s' % (service, exc),
                    status_code=None, service=service,
                ) from exc
            time.sleep(delay)
            delay *= backoff
            continue

        if response.status_code in RETRYABLE_STATUS and attempt < retries:
            _logger.warning(
                '[%s] %s %s → HTTP %s, reintentando (%d/%d)',
                service or 'http', method, url, response.status_code,
                attempt + 1, retries,
            )
            time.sleep(delay)
            delay *= backoff
            continue

        return response

    # Inalcanzable pero defensivo.
    raise HttpError(
        'Error inesperado al contactar a %s' % service,
        service=service,
    ) from last_exc


def get(url, **kwargs):
    return request('GET', url, **kwargs)


def post(url, **kwargs):
    return request('POST', url, **kwargs)
