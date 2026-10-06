SANDBOX_URLS = {
    'security': 'https://apisandbox.vnforappstest.com/api.security/v1/security',
    'session': 'https://apisandbox.vnforappstest.com/api.ecommerce/v2/ecommerce/token/session/{merchant_id}',
    'authorization': 'https://apisandbox.vnforappstest.com/api.authorization/v3/authorization/ecommerce/{merchant_id}',
    'reversa': 'https://apisandbox.vnforappstest.com/api.authorization/v3/reverse/ecommerce/{merchant_id}',
    'refund': 'https://apitestenv.vnforapps.com/api.refund/v1/refund/{merchant_id}/{transaction_id}',
    'pagoefectivo': 'https://apisandbox.vnforappstest.com/api.pagoefectivo/v1/create/{merchant_id}',
    'checkout_js': 'https://static-content-qas.vnforapps.com/v2/js/checkout.js?qa=true',
}

PROD_URLS = {
    'security': 'https://apiprod.vnforapps.com/api.security/v1/security',
    'session': 'https://apiprod.vnforapps.com/api.ecommerce/v2/ecommerce/token/session/{merchant_id}',
    'authorization': 'https://apiprod.vnforapps.com/api.authorization/v3/authorization/ecommerce/{merchant_id}',
    'reversa': 'https://apiprod.vnforapps.com/api.authorization/v3/reverse/ecommerce/{merchant_id}',
    'refund': 'https://apiprod.vnforapps.com/api.refund/v1/refund/{merchant_id}/{transaction_id}',
    'pagoefectivo': 'https://apiprod.vnforapps.com/api.pagoefectivo/v1/create/{merchant_id}',
    'checkout_js': 'https://static-content.vnforapps.com/v2/js/checkout.js',
}

PAYMENT_RETURN_ROUTE = '/payment/niubiz/return'
PAYMENT_LANDING_ROUTE = '/payment/niubiz/landing'

APPROVED_ACTION_CODES = ('000', '010')

# Anulación (reversa) aceptada: Niubiz responde actionCode 400 y STATUS
# «Voided» (código ISO 8583 de reverso aceptado; comprobado contra el sandbox).
REVERSAL_APPROVED_ACTION_CODES = ('400',)
REVERSAL_APPROVED_STATUS = 'Voided'

# dataMap.BRAND → Odoo payment.method code
# Alternative methods (yape, plin, etc.) fall back to 'card' if no specific Odoo method exists
PAYMENT_METHODS_MAPPING = {
    'visa': 'visa',
    'mastercard': 'mastercard',
    'amex': 'amex',
    'dinersclub': 'diners',
    'unionpay': 'unionpay',
    'yape': 'card',
    'plin': 'card',
    'cuotealo': 'card',
    'pagofectivo': 'card',
}

DEFAULT_PAYMENT_METHOD_CODES = {
    'card',
    'visa',
    'mastercard',
    'amex',
}

# actionCode → human-readable error message
ACTION_CODE_MESSAGES = {
    '101': "Tarjeta vencida. Por favor use otra tarjeta.",
    '102': "Contacte a su banco emisor.",
    '116': "Fondos insuficientes. Por favor use otra tarjeta o intente con otro monto.",
    '118': "Número de tarjeta inválido.",
    '129': "Tarjeta no operativa.",
    '190': "Contacte a su banco emisor.",
    '191': "Contacte a su banco emisor.",
    '207': "Contacte a su banco emisor.",
    '208': "Tarjeta reportada como perdida.",
    '209': "Tarjeta reportada como robada.",
    '265': "Clave secreta incorrecta.",
    '280': "Contraseña incorrecta.",
    '290': "Contacte a su banco emisor (directiva permanente).",
    '300': "Número de pedido duplicado. Intente nuevamente.",
    '401': "Cuenta de comercio deshabilitada.",
    '666': "Error de comunicación. Intente nuevamente.",
    '667': "La transacción requiere autenticación.",
    '670': "Rechazo por seguridad. Intente nuevamente o llame al soporte.",
    '678': "Falla en autenticación Verified by Visa.",
    '683': "Error de comunicación. Intente nuevamente.",
    '690': "Pagos QR no permitidos para este comercio.",
    '904': "Formato de mensaje inválido.",
    '909': "Error de comunicación. Intente nuevamente.",
}

# Sandbox test credentials
SANDBOX_ACCESS_KEY = 'integraciones@niubiz.com.pe'
SANDBOX_SECRET_KEY = '_7z3@8fF'

# Sandbox test merchants
SANDBOX_MERCHANTS = {
    'PEN': '456879852',
    'USD': '456879853',
}

# Supported currencies
SUPPORTED_CURRENCIES = ('PEN', 'USD')

# Session token expiry in minutes
SESSION_EXPIRY_MINUTES = '20'
