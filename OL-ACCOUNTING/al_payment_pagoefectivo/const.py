# -*- coding: utf-8 -*-
"""Constantes de la integración con PagoEfectivo (API REST v1 de generación de CIP).

PagoEfectivo entrega su ficha técnica al comercio afiliado. La forma de la API
(autorización, CIP y notificación firmada) se contrastó con el entorno de
prueba público ``pre1a.services.pagoefectivo.pe``, que valida las solicitudes
sin credenciales y devuelve sus códigos de error.
"""

API_URL_TEST = 'https://pre1a.services.pagoefectivo.pe/v1/'
API_URL_PROD = 'https://services.pagoefectivo.pe/v1/'

SUPPORTED_CURRENCIES = ('PEN', 'USD')
DEFAULT_PAYMENT_METHOD_CODES = {'pagoefectivo'}

# Código de respuesta de una solicitud aceptada (autorización y CIP).
CODE_SUCCESS = '100'

# La autorización firma la fecha con la hora de Lima y su desfase (+/-hh:mm).
TIMEZONE = 'America/Lima'

# Vigencia del CIP por omisión, en horas.
DEFAULT_EXPIRY_HOURS = 48

# Tras el vencimiento del CIP se espera este margen antes de cancelar la
# transacción, por si la notificación de un pago hecho al límite llega tarde.
EXPIRY_GRACE_HOURS = 2

# ``transactionCode`` debe ser único por servicio: letras, cifras y «-».
TRANSACTION_CODE_MAX_LENGTH = 40
PAYMENT_CONCEPT_MAX_LENGTH = 120

# Tipos de documento que acepta ``userDocumentType``. El RUC no está: se omite.
DOCUMENT_TYPES = {'DNI', 'PAS', 'LMI', 'PAR', 'NAN'}

# Eventos de la notificación (``eventType``).
EVENT_PAID = 'cip.paid'
EVENT_EXPIRED = 'cip.expired'

# Cabecera con el HMAC-SHA256 (hexadecimal) del cuerpo, con la clave secreta.
SIGNATURE_HEADER = 'PE-Signature'
