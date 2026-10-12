# -*- coding: utf-8 -*-
"""Cliente del servicio web «Consulta integrada de comprobante de pago» de SUNAT.

Fuente: Manual de Consulta Integrada de Comprobante de Pago por Servicio Web
v2.0 (https://cpe.sunat.gob.pe/sites/default/files/inline-files/
Manual-de-Consulta-Integrada-de-Comprobante-de-Pago-por-ServicioWEB_v2_0.pdf).

1. Token: POST a ``TOKEN_URL`` (formulario) con grant_type client_credentials,
   el scope fijo y el client_id / client_secret generados en SOL ▸ Credenciales
   de API SUNAT. Devuelve access_token y expires_in (segundos).
2. Consulta: POST JSON a ``VALIDATE_URL`` (con el RUC de quien consulta) con
   ``Authorization: Bearer <token>`` y numRuc, codComp, numeroSerie, numero,
   fechaEmision (dd/mm/aaaa) y monto (solo comprobantes electrónicos).
"""
import requests

TOKEN_URL = 'https://api-seguridad.sunat.gob.pe/v1/clientesextranet/%s/oauth2/token/'
SCOPE = 'https://api.sunat.gob.pe/v1/contribuyente/contribuyentes'
VALIDATE_URL = 'https://api.sunat.gob.pe/v1/contribuyente/contribuyentes/%s/validarcomprobante'
TIMEOUT = 20

# Tablas del manual (página 10).
CP_STATES = {
    '0': 'No existe (no informado)',
    '1': 'Aceptado',
    '2': 'Anulado (comunicado en una baja)',
    '3': 'Autorizado (imprenta)',
    '4': 'No autorizado (imprenta)',
}
RUC_STATES = {
    '00': 'Activo',
    '01': 'Baja provisional',
    '02': 'Baja provisional por oficio',
    '03': 'Suspensión temporal',
    '10': 'Baja definitiva',
    '11': 'Baja de oficio',
    '22': 'Inhabilitado - vent. única',
}
DOMICILE_STATES = {
    '00': 'Habido',
    '09': 'Pendiente',
    '11': 'Por verificar',
    '12': 'No habido',
    '20': 'No hallado',
}


class SunatCpeError(Exception):
    """Error de la consulta (credenciales, red o respuesta de SUNAT)."""


def get_token(client_id, client_secret):
    """``(access_token, expires_in)``."""
    try:
        response = requests.post(TOKEN_URL % client_id, data={
            'grant_type': 'client_credentials',
            'scope': SCOPE,
            'client_id': client_id,
            'client_secret': client_secret,
        }, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise SunatCpeError('SUNAT no respondió al pedir el token: %s' % exc) from exc
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    token = payload.get('access_token')
    if response.status_code != 200 or not token:
        detail = payload.get('error_description') or payload.get('error') or response.text[:200]
        raise SunatCpeError('SUNAT rechazó las credenciales (HTTP %s): %s'
                            % (response.status_code, detail))
    return token, int(payload.get('expires_in') or 3600)


def validate(token, consultant_ruc, values):
    """Consulta un comprobante. ``values``: numRuc, codComp, numeroSerie,
    numero, fechaEmision y, si es electrónico, monto. Devuelve ``data`` de la
    respuesta (estadoCp, estadoRuc, condDomiRuc, observaciones)."""
    try:
        response = requests.post(VALIDATE_URL % consultant_ruc, json=values, headers={
            'Authorization': 'Bearer %s' % token,
            'Content-Type': 'application/json',
        }, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise SunatCpeError('SUNAT no respondió a la consulta: %s' % exc) from exc
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code == 401:
        raise SunatCpeError('El token de SUNAT venció o no es válido.')
    if response.status_code != 200 or not payload.get('success'):
        detail = payload.get('message') or payload.get('errorCode') or response.text[:200]
        raise SunatCpeError('SUNAT no pudo consultar el comprobante (HTTP %s): %s'
                            % (response.status_code, detail))
    data = payload.get('data') or {}
    # El manual escribe «Observaciones»; la respuesta real usa minúscula.
    data['observaciones'] = data.get('observaciones') or data.get('Observaciones') or []
    return data
