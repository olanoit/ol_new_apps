# -*- coding: utf-8 -*-
"""Constantes de la integración con Culqi (API v2).

Fuentes: especificación OpenAPI oficial (https://apidocs.culqi.com/apiculqi.yaml)
y documentación de Checkout Custom y Culqi 3DS (https://docs.culqi.com).
"""

API_URL = 'https://api.culqi.com/v2/'
# Checkout Custom: Checkout v4 está en desuso según la documentación oficial.
CHECKOUT_JS_URL = 'https://js.culqi.com/checkout-js'
THREEDS_JS_URL = 'https://3ds.culqi.com'

SUPPORTED_CURRENCIES = ('PEN', 'USD')

# Código del método de pago en Odoo → clave de ``options.paymentMethods`` del
# Checkout Custom.
PAYMENT_METHODS_MAPPING = {
    'card': 'tarjeta',
    'yape': 'yape',
}
DEFAULT_PAYMENT_METHOD_CODES = set(PAYMENT_METHODS_MAPPING)

# Respuesta HTTP 200 del cargo: el banco pide autenticación 3DS.
ACTION_CODE_REVIEW = 'REVIEW'

# Motivo de las devoluciones enviadas desde Odoo (enum de POST /v2/refunds).
REFUND_REASON = 'solicitud_comprador'

# Culqi 3DS: monto del cargo admitido, en céntimos.
THREEDS_MIN_AMOUNT = 300
THREEDS_MAX_AMOUNT = 999900
