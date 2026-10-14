# -*- coding: utf-8 -*-
"""Constantes de la integración con Izipay (API REST V4 de micuentaweb.pe).

Fuentes: documentación oficial (https://secure.micuentaweb.pe/doc/es-PE/rest/V4.0/)
y ejemplos de Izipay (https://github.com/izipay-pe). Las respuestas se
comprobaron contra la tienda de prueba pública de la documentación.
"""

API_URL = 'https://api.micuentaweb.pe/api-payment/V4/'
# Dominio del cliente JavaScript (krypton-client V4.0) que muestra el formulario.
STATIC_URL = 'https://static.micuentaweb.pe'

SUPPORTED_CURRENCIES = ('PEN', 'USD')
DEFAULT_PAYMENT_METHOD_CODES = {'card'}

# Marca de la tarjeta (``effectiveBrand``) → código del método de pago en Odoo.
PAYMENT_METHODS_MAPPING = {
    'visa': 'VISA',
    'mastercard': 'MASTERCARD',
    'amex': 'AMEX',
    'diners': 'DINERS',
    'maestro': 'MAESTRO',
}

# ``orderId`` admite solo letras sin tilde, cifras, «_» y «-» (64 como máximo).
ORDER_ID_MAX_LENGTH = 64

# Estado simplificado de la transacción (``status``).
STATUS_PAID = 'PAID'
STATUS_RUNNING = 'RUNNING'
STATUS_UNPAID = 'UNPAID'
STATUS_ABANDONED = 'ABANDONED'

# ``detailedStatus`` de una transacción autorizada que aún no se capturó (el
# lote se cierra por la noche): se anula o se reduce el importe, no se reembolsa.
NOT_CAPTURED_STATUSES = (
    'AUTHORISED', 'AUTHORISED_TO_VALIDATE', 'WAITING_AUTHORISATION',
    'WAITING_AUTHORISATION_TO_VALIDATE',
)
CAPTURED_STATUS = 'CAPTURED'

# La IPN se firma con la contraseña de la API (``kr-hash-key = password``).
IPN_HASH_KEY = 'password'
HASH_ALGORITHM = 'sha256_hmac'

# Rango de IP desde el que Izipay envía la IPN (para el cortafuegos).
IPN_IP_RANGE = '194.50.38.0/24'
