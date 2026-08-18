# -*- coding: utf-8 -*-
"""Archivo de depósito masivo de detracciones del Banco de la Nación.

Fuente: «Depósito Masivo de Detracciones por Internet y Banco de la Nación»
(instructivo oficial, febrero 2021), apartados 5.1 a 5.9.

A diferencia de los libros de SUNAT, este archivo es de **ancho fijo**: cada
campo ocupa unas posiciones exactas y se rellena con espacios. La cabecera mide
68 caracteres y cada línea de detalle 107.

Hay dos modalidades, según quién deposita:

* **Adquiriente** (caso 1): la cabecera empieza por ``*`` y lleva el RUC del
  adquiriente; el detalle identifica a cada proveedor.
* **Proveedor** (caso 2): la cabecera empieza por ``P`` y lleva el RUC del
  proveedor; el detalle identifica a cada adquiriente.

Lógica pura (sin ORM): testeable de forma aislada.
"""

HEADER_LENGTH = 68
DETAIL_LENGTH = 107

# Indicador de maestra (posición 1 de la cabecera).
MASTER_ACQUIRER = '*'
MASTER_SUPPLIER = 'P'

# Tipo de documento de identidad: 6 = RUC (tabla 5.8 del instructivo).
DOC_TYPE_RUC = '6'


def text(value, length):
    """Texto ajustado a ``length``: recortado o rellenado con espacios."""
    return (value or '')[:length].ljust(length)


def number(value, length):
    """Número ajustado a ``length`` con ceros a la izquierda."""
    digits = ''.join(char for char in str(value or '') if char.isdigit())
    return digits[-length:].rjust(length, '0')


def amount(value, length=15):
    """Importe sin punto decimal: 13 enteros y 2 decimales.

    El instructivo pide reservar los dos últimos caracteres para los decimales
    y omitir el separador, de modo que 1234.56 se escribe como
    ``000000000123456``.
    """
    cents = int(round((value or 0.0) * 100))
    return str(abs(cents)).rjust(length, '0')[-length:]


def period(value):
    """Periodo tributario ``aaaamm`` de una fecha."""
    return value.strftime('%Y%m') if value else ' ' * 6


def build_header(master, vat, name, batch_number, total):
    """Primera línea del archivo (68 caracteres).

    ``master`` es ``*`` para el adquiriente y ``P`` para el proveedor.
    """
    line = (
        text(master, 1)
        + number(vat, 11)
        + text(name, 35)
        + text(batch_number, 6)
        + amount(total)
    )
    return line[:HEADER_LENGTH].ljust(HEADER_LENGTH)


def build_detail(doc_type, vat, name, service_code, bank_account, deposit,
                 operation_type, tax_period, invoice_type, invoice_serie,
                 invoice_number, proforma=''):
    """Línea de detalle de un depósito (107 caracteres).

    ``name`` va en blanco cuando el depositante es el adquiriente: el
    instructivo reserva las 35 posiciones pero pide dejarlas vacías, porque el
    banco recupera el nombre desde el RUC.
    """
    line = (
        text(doc_type, 1)                    # 01     tipo de documento
        + number(vat, 11)                    # 02-12  número de documento
        + text(name, 35)                     # 13-47  nombre o razón social
        + text(proforma, 9)                  # 48-56  nº de proforma
        + number(service_code, 3)            # 57-59  bien o servicio
        + number(bank_account, 11)           # 60-70  cuenta del proveedor
        + amount(deposit)                    # 71-85  importe del depósito
        + number(operation_type, 2)          # 86-87  tipo de operación
        + text(tax_period, 6)                # 88-93  periodo tributario
        + number(invoice_type, 2)            # 94-95  tipo de comprobante
        + text(invoice_serie, 4)             # 96-99  serie
        + number(invoice_number, 8)          # 100-107 número
    )
    return line[:DETAIL_LENGTH].ljust(DETAIL_LENGTH)


def build_file(header, details):
    """Une cabecera y detalle. El banco espera fin de línea Windows."""
    return '\r\n'.join([header] + list(details)) + '\r\n'


def check_structure(content):
    """Comprueba las longitudes de un archivo ya construido.

    Devuelve la lista de problemas encontrados; vacía si el archivo es válido.
    Se usa antes de entregar el fichero: el banco rechaza el lote completo si
    una sola línea no mide lo que debe.
    """
    problems = []
    lines = [line for line in content.split('\r\n') if line]
    if not lines:
        return ['El archivo está vacío.']
    if len(lines[0]) != HEADER_LENGTH:
        problems.append(
            'La cabecera mide %d caracteres y debe medir %d.'
            % (len(lines[0]), HEADER_LENGTH))
    if lines[0][0] not in (MASTER_ACQUIRER, MASTER_SUPPLIER):
        problems.append(
            'La cabecera debe empezar por «%s» (adquiriente) o «%s» '
            '(proveedor).' % (MASTER_ACQUIRER, MASTER_SUPPLIER))
    for index, line in enumerate(lines[1:], start=1):
        if len(line) != DETAIL_LENGTH:
            problems.append(
                'La línea %d mide %d caracteres y debe medir %d.'
                % (index, len(line), DETAIL_LENGTH))
    return problems
