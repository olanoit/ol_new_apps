# -*- coding: utf-8 -*-
"""Archivos TXT de pago masivo a proveedores por banco (funciones puras, sin
``env``: se prueban sin base de datos).

Los bancos peruanos no publican la especificación de sus archivos: la
entregan al cliente afiliado (Telecrédito, net cash, Interbank Empresas,
Scotiabank Telebanking, Banco de la Nación). La de BCP es la de pago a
proveedores de Telecrédito (marca del ITF, modalidad de pago y comprobantes
pagados), distinta de la de haberes; las de BBVA, Interbank y Scotiabank
parten de los formatos de pago masivo que la suite ya usa en producción para
planillas (al_hr_pe_reports), adaptados a proveedores; la del Banco de la
Nación es una estructura propia. Todas deben
validarse con el banco antes del primer pago real (ver la documentación del
módulo). Cada función recibe:

``header``: dict con
    ``currency`` ('PEN'/'USD'), ``payment_date`` (date), ``now`` (datetime
    local), ``charge_acc`` (cuenta de cargo), ``company_name``,
    ``company_vat``, ``reference`` (glosa del lote) y ``options`` (dict con
    los parámetros del diario: ``service_code``, ``process_type``…).
``lines``: lista de dicts con
    ``doc_type`` (código SUNAT del documento: 1 DNI, 4 carné de extranjería,
    6 RUC, 7 pasaporte), ``doc_number``, ``name``, ``account`` (número de
    cuenta en el mismo banco o CCI), ``is_cci`` (bool), ``account_kind``
    ('checking'/'savings'), ``amount`` (en la moneda del lote) y
    ``reference`` (comprobantes que se pagan) y ``documents`` (lista de dicts
    ``type`` F/B/N/C, ``number`` y ``amount``: lo que el pago salda de cada
    comprobante; vacía si no se conoce).

Devuelven el texto del archivo (líneas terminadas en CRLF).
"""
from odoo.tools.float_utils import float_round

_SPECIAL_CHARS = {
    'Ñ': 'N', 'ñ': 'n', 'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'Ü': 'U', 'ü': 'u',
}
EOL = '\r\n'


def clean_text(text):
    """Solo letras sin tilde, dígitos y espacios: los bancos rechazan el
    resto de caracteres."""
    out = []
    for char in str(text or ''):
        char = _SPECIAL_CHARS.get(char, char)
        if char.isascii() and (char.isalnum() or char == ' '):
            out.append(char)
    return ''.join(out)


def alpha(value, width):
    """Texto a la izquierda, relleno con espacios y truncado."""
    return clean_text(value)[:width].ljust(width)


def number(value, width):
    """Entero a la derecha con ceros."""
    return clean_text(value)[-width:].rjust(width, '0')


def amount(value, width, point=False):
    """Importe con dos decimales a la derecha con ceros; sin punto salvo
    ``point``."""
    text = '%.2f' % float_round(value, precision_digits=2)
    if not point:
        text = text.replace('.', '')
    return text[-width:].rjust(width, '0')


def digits(value):
    return ''.join(char for char in str(value or '') if char.isdigit())


def total(lines):
    return float_round(sum(line['amount'] for line in lines), precision_digits=2)


def group_by_beneficiary(lines):
    """Un abono por proveedor y cuenta: suma los pagos y junta sus
    comprobantes. Si algún pago no trae comprobantes, el abono va sin
    detalle (el banco exige que el detalle sume el abono)."""
    groups = {}
    for line in lines:
        key = (line['doc_type'], line['doc_number'], line['account'], line['is_cci'])
        group = groups.get(key)
        if group is None:
            groups[key] = dict(line, documents=list(line.get('documents') or []),
                               _complete=bool(line.get('documents')))
            continue
        group['amount'] = float_round(group['amount'] + line['amount'], precision_digits=2)
        group['reference'] = ' '.join(filter(None, (group['reference'], line['reference'])))
        group['documents'] += line.get('documents') or []
        group['_complete'] = group['_complete'] and bool(line.get('documents'))
    result = []
    for group in groups.values():
        complete = group.pop('_complete')
        if not complete or float_round(
                sum(doc['amount'] for doc in group['documents']) - group['amount'],
                precision_digits=2):
            group['documents'] = []
        result.append(group)
    return result


# ---------------------------------------------------------------------------
# BCP — Telecrédito, pago a proveedores: cabecera «1», abono «2» por
# beneficiario y, debajo de cada abono, un «3» por comprobante pagado
# ---------------------------------------------------------------------------
BCP_DOC_TYPES = {'1': '1', '4': '3', '7': '4', '6': '6'}
BCP_ACCOUNT_TYPES = {'checking': 'C', 'savings': 'A'}
BCP_PAYMENT_MODE = '1'  # abono en cuenta


def bcp_txt(header, lines):
    """``lines`` ya agrupadas por beneficiario (``group_by_beneficiary``).

    Opciones del diario: ``itf_exempt`` (marca de exoneración del ITF de la
    cabecera), ``validate_idc`` (el banco comprueba que el documento del
    beneficiario sea el titular de la cuenta) y ``documents`` (registros
    «3» con los comprobantes de cada abono).

    Suma de control de la cabecera: las cuentas de abono (la CCI desde la
    posición 11 y las demás desde la 4) más la cuenta de cargo (desde la
    4), a 15 posiciones."""
    options = header['options']
    currency = '0001' if header['currency'] == 'PEN' else '1001'
    accounts = [int(digits(line['account'])[10 if line['is_cci'] else 3:] or 0)
                for line in lines]
    accounts.append(int(digits(header['charge_acc'])[3:] or 0))
    out = ['1' + number(len(lines), 6) + header['payment_date'].strftime('%Y%m%d')
           + 'C' + currency + alpha(header['charge_acc'], 20)
           + amount(total(lines), 17, point=True) + alpha(header['reference'], 40)
           + ('S' if options.get('itf_exempt') else 'N')
           + number(sum(accounts), 15) + EOL]
    idc = 'S' if options.get('validate_idc', True) else 'N'
    for line in lines:
        kind = 'B' if line['is_cci'] else BCP_ACCOUNT_TYPES.get(line['account_kind'], 'C')
        out.append('2' + kind + alpha(digits(line['account']), 20) + BCP_PAYMENT_MODE
                   + BCP_DOC_TYPES.get(line['doc_type'], '6') + alpha(line['doc_number'], 12)
                   + '   ' + alpha(line['name'], 75) + alpha(line['reference'], 40)
                   + alpha(header['company_name'], 20) + currency
                   + amount(line['amount'], 17, point=True) + idc + EOL)
        if options.get('documents', True):
            for doc in line.get('documents') or []:
                out.append('3' + doc['type'][:1] + number(doc['number'], 15)
                           + amount(doc['amount'], 17, point=True) + EOL)
    return ''.join(out)


# ---------------------------------------------------------------------------
# BBVA — net cash, pago a proveedores (cabecera «700» y detalle «002»)
# ---------------------------------------------------------------------------
BBVA_DOC_TYPES = {'1': 'L', '4': 'E', '7': 'P', '6': 'R'}


def bbva_txt(header, lines):
    options = header['options']
    process = options.get('process_type') or 'A'
    out = ['700' + alpha(digits(header['charge_acc']), 20) + header['currency']
           + amount(total(lines), 15) + process
           + (header['payment_date'].strftime('%Y%m%d') if process == 'F' else ' ' * 8)
           + ' ' + alpha(header['reference'], 25) + number(len(lines), 6) + 'S'
           + '0' * 18 + ' ' * 50 + EOL]
    for line in lines:
        out.append('002' + BBVA_DOC_TYPES.get(line['doc_type'], 'R')
                   + alpha(line['doc_number'], 12) + ('I' if line['is_cci'] else 'P')
                   + alpha(digits(line['account']), 20) + alpha(line['name'], 40)
                   + amount(line['amount'], 15) + alpha(line['reference'], 40)
                   + ' ' + ' ' * 50 + ' ' * 50 + EOL)
    return ''.join(out)


# ---------------------------------------------------------------------------
# Interbank — pagos masivos a proveedores (cabecera «01» y detalle «02»)
# ---------------------------------------------------------------------------
INTERBANK_DOC_TYPES = {'1': '01', '4': '03', '7': '05', '6': '02'}


def interbank_txt(header, lines):
    options = header['options']
    pen = header['currency'] == 'PEN'
    currency = '01' if pen else '10'
    out = ['01' + alpha(options.get('service_code') or '04', 2) + ' ' * 36
           + header['now'].strftime('%Y%m%d%H%M%S') + ' ' * 9 + number(len(lines), 6)
           + (amount(total(lines), 15) if pen else '0' * 15)
           + (amount(total(lines), 15) if not pen else '0' * 15)
           + alpha(options.get('company_code') or 'MC001', 5) + EOL]
    for line in lines:
        person = 'C' if line['doc_type'] == '6' else 'P'
        doc_type = INTERBANK_DOC_TYPES.get(line['doc_type'], '02')
        if line['is_cci']:
            account = '99' + '   ' + '  ' + ' ' * 3 + alpha(digits(line['account']), 20)
        else:
            kind = '001' if line['account_kind'] == 'checking' else '002'
            account = '09' + kind + currency + alpha(digits(line['account']), 23)
        out.append('02' + doc_type + alpha(line['doc_number'], 20)
                   + alpha(line['reference'], 19) + ' ' * 8 + currency
                   + amount(line['amount'], 15) + ' ' + account + person + doc_type
                   + alpha(line['doc_number'], 15) + alpha(line['name'], 60) + EOL)
    return ''.join(out)


# ---------------------------------------------------------------------------
# Scotiabank — pago a proveedores (solo detalle)
# ---------------------------------------------------------------------------
SCOTIABANK_DOC_TYPES = {'1': '1', '4': '2', '7': '3', '6': '4'}


def scotiabank_txt(header, lines):
    currency = '00' if header['currency'] == 'PEN' else '01'
    way = header['options'].get('service_code') or '1'
    out = []
    for line in lines:
        account = digits(line['account'])
        out.append(SCOTIABANK_DOC_TYPES.get(line['doc_type'], '4')
                   + alpha(line['doc_number'], 12) + alpha(line['name'], 60) + way[:1]
                   + alpha('' if line['is_cci'] else account, 10)
                   + alpha(account if line['is_cci'] else '', 20)
                   + amount(line['amount'], 11) + currency
                   + alpha(line['reference'] or 'PROVEEDORES', 20) + '01' + EOL)
    return ''.join(out)


# ---------------------------------------------------------------------------
# Banco de la Nación — pago a proveedores (estructura propia: confirmar con
# el banco antes de usarla)
# ---------------------------------------------------------------------------
def bn_txt(header, lines):
    currency = '01' if header['currency'] == 'PEN' else '02'
    out = ['C' + number(header['company_vat'], 11) + header['payment_date'].strftime('%Y%m%d')
           + currency + alpha(digits(header['charge_acc']), 20) + number(len(lines), 6)
           + amount(total(lines), 15) + alpha(header['reference'], 40) + EOL]
    for line in lines:
        out.append('D' + line['doc_type'][:1] + alpha(line['doc_number'], 12)
                   + alpha(line['name'], 60) + ('I' if line['is_cci'] else 'P')
                   + alpha(digits(line['account']), 20) + amount(line['amount'], 15)
                   + alpha(line['reference'], 40) + EOL)
    return ''.join(out)


# Formato: (función, etiqueta del archivo, agrupa los pagos por beneficiario)
FORMATS = {
    'bcp': (bcp_txt, 'BCP', True),
    'bbva': (bbva_txt, 'BBVA', False),
    'interbank': (interbank_txt, 'Interbank', False),
    'scotiabank': (scotiabank_txt, 'Scotiabank', False),
    'bn': (bn_txt, 'BN', False),
}
