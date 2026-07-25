# -*- coding: utf-8 -*-
"""Pago masivo bancario (TXT propietarios BCP/BBVA/Interbank/Scotiabank/BanBif).

Port v18 → v19 de ``al_hr_payroll/hr_automate_multipayment`` (modelo
central ``hr.automate.multipayment``). Los bancos peruanos NO aceptan
ISO 20022 para el abono de haberes/CTS: cada banco define su propio
layout TXT de ancho fijo y aquí se conservan **byte a byte** (incluidas
las rarezas heredadas: tabs literales en BBVA/Interbank CTS, cero-padding
a la izquierda del total USD de Interbank con relleno a la derecha, etc.).

Estructura del port:

* **Funciones puras de formato** a nivel de módulo (una por banco y
  proceso): reciben un dict de cabecera + lista de dicts de línea y
  devuelven el ``str`` completo del TXT. Sin ``env``: testeables sin BD.
* **Modelo central** ``hr.automate.multipayment`` con líneas propias
  (``hr.automate.multipayment.line``): en v18 las líneas eran los
  registros del origen (boletas / líneas CTS...) contaminados con
  ``multipayment_id``/``is_txt``; aquí el origen queda intacto.
* **Orígenes**: lote de nómina (``hr.payslip.run``), quincena
  (``hr.fortnightly``), CTS (``hr.cts``), gratificación
  (``hr.gratification``) y liquidación vacacional (``hr.vacation``)
  ganan ``generate_multipayments()`` (un registro por diario bancario
  con formato presente en las cuentas destino).
* **Archivos**: ``ir.attachment`` + acción de descarga (patrón de
  ``al_hr_pe/models/hr_payslip_run_export.py``); nada de escribir a
  disco (v18 usaba ``hr.main.parameter.dir_create_file``).

Cambios de datos v18 → v19:

* ``hr.type.document.{bbva,bcp,interbank,banbif}_code`` →
  ``l10n_latam.identification.type.l10n_pe_hr_*_code`` (extensión aquí;
  data en ``data/bank_codes_data.xml``).
* Cuenta de haberes: ``employee.wage_bank_account_id`` (v18) →
  ``employee.primary_bank_account_id`` (nativo v19, primera cuenta de
  ``bank_account_ids``). La CTS sigue en ``cts_bank_account_id``
  (al_hr_pe).

No portado (veredictos):

* ``wizard/hr_import_wizard`` (importador xlrd de cuentas): framework
  de importación → Fase 8.
* ``get_utilities_txt`` y variantes ``*_utility``: el TXT de utilidades
  leía la regla ``hr_input_for_results`` de boletas de un lote; el
  proceso de utilidades v19 (``hr.utilities``) aún no expone ese flujo.
  TODO(fase7-revisar): portar cuando hr.utilities genere boletas.
* ``get_scotiabank_hr_txt`` (variante 1 con RUC de cabecera): muerta en
  v18 — el dispatcher solo llamaba a la variante 2. Solo se porta la 2.
"""
import re

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from odoo.addons.al_hr_pe_benefits.models.hr_benefits_engine import \
    notify_success


# ======================================================================
# Funciones puras de formato (sin env — testeables sin BD)
# ======================================================================
#
# Cabecera (dict ``header``) — claves usadas según banco/proceso:
#   charge_acc:        cuenta de cargo (str, tal cual en res.partner.bank)
#   charge_acc_type:   tipo de la cuenta de cargo ('0'/'1'/'3')
#   charge_branch:     sucursal BBVA (str) — se inserta en la posición 8
#   currency:          moneda de la cuenta de cargo ('PEN'/'USD')
#   payment_date:      fecha de pago (datetime.date)
#   now:               fecha-hora local (datetime.datetime) — Interbank
#   glosa:             referencia libre (str)
#   company_name:      razón social de la compañía
#   company_vat:       RUC de la compañía
#   process_type / process_hour / owner_validation / alert_indicator: BBVA
#   idc_flag / subtype:                                               BCP
#   person_type:                                                Interbank
#   payment_way:                                               Scotiabank
#   subtype_banbif:                                                BanBif
#   cts_dollars:       True si el depósito CTS se abona en USD
#   cts_name:          nombre del registro CTS (referencia/concepto)
#   cts_checksum_accs: nros. de cuenta destino para el checksum BCP CTS
#
# Línea (dict por elemento de ``lines``):
#   doc_bbva/doc_bcp/doc_interbank/doc_banbif: código del tipo de doc
#   doc_sunat:        código SUNAT del tipo de doc (Scotiabank)
#   doc_number:       número de documento
#   name:             nombre completo del beneficiario
#   last_name / m_last_name / names: nombre descompuesto
#   acc_number:       cuenta destino
#   acc_type:         tipo de la cuenta destino ('0'/'1'/'3')
#   acc_bic:          BIC del banco de la cuenta destino (BanBif)
#   amount:           monto a abonar (float, en la moneda del proceso)
#   amount_soles:     monto en soles (Scotiabank CTS, campo rem_amount)
#   computable_base:  (sueldo + asig. familiar) × 4 (BCP/Interbank CTS)
#   reference:        referencia de la línea (nro. boleta / doc / CTS)
#   email / phone:    aviso BBVA (indicador E/C)
#   street / mobile:  dirección y celular (BanBif)

_SPECIAL_CHARS = {
    'Ñ': 'N', 'ñ': 'n', 'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'Ü': 'U', 'ü': 'u',
    '@': 'a', ':': '', 'Ã': 'A', '`': '', '“': '',
}


def clean_text(text):
    """Sustituye/elimina caracteres fuera de [A-Za-z0-9 ] (port de
    ``delete_special_chars`` v18: tildes → vocal simple, Ñ → N, resto
    se descarta)."""
    result = []
    for char in text or '':
        if char in _SPECIAL_CHARS:
            result.append(_SPECIAL_CHARS[char])
        elif char.isascii() and (char.isalnum() or char == ' '):
            result.append(char)
    return ''.join(result)


def txt_field(value, kind, width=1, left=True, decimal_point=False):
    """Port puro de ``parse_to_txt`` v18: campo de ancho fijo.

    :param value: valor a formatear (str/int/float/date/datetime).
    :param kind: 'str'/'int' (limpia caracteres y rellena con espacios/
        con la MISMA lógica v18: espacios para str, '0' para el resto),
        'float' (2 decimales, relleno '0'), 'date' (AAAAMMDD),
        'datetime' (AAAAMMDDHHMMSS — debe venir ya localizado),
        'txt' (sin limpieza de caracteres).
    :param width: ancho total del campo.
    :param left: True = alinea a la izquierda (padding a la derecha).
    :param decimal_point: en 'float', emite el punto decimal.
    """
    if kind not in ('date', 'datetime') and len(str(value)) > width:
        value = str(value)[0:width]
    spacer = ' ' if kind in ('str', 'txt') else '0'
    aux = spacer * width
    if kind in ('int', 'str'):
        text = clean_text(str(value))
        return text + aux[len(text):] if left else aux[:-len(text)] + text
    if kind == 'float':
        amount = custom_round(value, 2)
        parts = str(amount).split('.')
        integer = parts[0]
        decimals = parts[1] if len(parts) > 1 else '0'
        if len(decimals) == 1:
            decimals += '0'
        dp = '.' if decimal_point else ''
        text = integer + dp + decimals
        return text + aux[len(text):] if left else aux[:-len(text)] + text
    if kind == 'date':
        return '%04d%02d%02d' % (value.year, value.month, value.day)
    if kind == 'datetime':
        return value.strftime('%Y%m%d%H%M%S')
    # kind == 'txt'
    text = str(value)
    return text + aux[len(text):] if left else aux[:-len(text)] + text


def _banbif_amount(amount):
    """Monto BanBif: 2 decimales sin punto, 14 posiciones con espacios a
    la izquierda (port literal del bloque ``ap/apf`` v18)."""
    text = str(round(amount, 2))
    if '.' in text:
        integer, decimals = text.split('.')
        if len(decimals) < 2:
            text = integer + '.' + decimals.ljust(2, '0')
    else:
        text += '.00'
    return text.replace('.', '').rjust(14, ' ')


def _bbva_charge_account(header):
    """Cuenta de cargo BBVA: la sucursal se inserta tras la posición 8."""
    acc = header['charge_acc']
    return acc[:8] + (header.get('charge_branch') or '') + acc[8:]


# ----------------------------------------------------------------------
# Haberes (también gratificación, quincena y vacaciones — v18 reutilizaba
# el mismo layout cambiando solo el monto y la referencia por línea)
# ----------------------------------------------------------------------
def bbva_haberes_txt(header, lines):
    """TXT BBVA haberes (port de ``get_bbva_hr_txt``).

    Cabecera '700' + detalle '002'; la cabecera cuenta TODAS las líneas
    (aunque el detalle omite montos ≤ 0 — rareza v18 conservada)."""
    total = sum(custom_round(line['amount'], 2) for line in lines)
    out = ['700{account}{currency}{total}{process}{date}{hour}{reference}'
           '{count}{valid}{cero}'.format(
               account=_bbva_charge_account(header),
               currency=header['currency'],
               total=txt_field(total, 'float', 15, left=False),
               process=header['process_type'],
               date=txt_field(header['payment_date'], 'date')
               if header['process_type'] == 'F' else ' ' * 8,
               hour=header['process_hour']
               if header['process_type'] == 'H' else ' ',
               reference=txt_field(header['glosa'], 'str', 25)
               if header['glosa'] else ' ' * 25,
               count=txt_field(len(lines), 'int', 6, left=False),
               valid=header['owner_validation'],
               cero='0' * 18,
           ) + ' ' * 50 + '\r\n']
    for line in lines:
        if line['amount'] <= 0:
            continue
        if header.get('alert_indicator') == 'E':
            alert_val = line.get('email') or ''
        elif header.get('alert_indicator') == 'C':
            alert_val = line.get('phone') or ''
        else:
            alert_val = ''
        out.append('002{p_doc_type}{p_doc_num}{charge_type}{payment_doc}'
                   '{beneficiary_name}{amount}{reference}{alert_indicator}'
                   '{alert_val}'.format(
                       p_doc_type=line['doc_bbva'],
                       p_doc_num=txt_field(line['doc_number'], 'str', 12),
                       charge_type='I' if line['acc_type'] == '3' else 'P',
                       payment_doc=txt_field(line['acc_number'], 'str', 20),
                       beneficiary_name=txt_field(line['name'], 'str', 40),
                       amount=txt_field(line['amount'], 'float', 15,
                                        left=False),
                       reference=txt_field(line['reference'], 'str', 40),
                       alert_indicator=header.get('alert_indicator') or ' ',
                       alert_val=txt_field(alert_val, 'str', 50),
                   ) + ' ' * 50 + '\r\n')
    return ''.join(out)


def bcp_haberes_txt(header, lines):
    """TXT BCP haberes (port de ``get_bcp_hr_txt``).

    Checksum de cabecera: suma de las cuentas destino con monto > 0
    (CCI: dígitos desde la posición 10; resto: desde la 3) más la cuenta
    de cargo (desde la 3), a 15 posiciones con ceros."""
    account_type = {'0': 'C', '1': 'A', '3': 'B'}
    acc_numbers, count = [], 0
    for line in lines:
        if line['amount'] > 0:
            start = 10 if line['acc_type'] == '3' else 3
            acc_numbers.append(int(line['acc_number'][start:]))
            count += 1
    acc_numbers.append(int(header['charge_acc'][3:]))
    checksum = str(sum(acc_numbers)).strip().rjust(15, '0')
    total = sum(custom_round(line['amount'], 2) for line in lines)
    currency = '0001' if header['currency'] == 'PEN' else '1001'
    out = ['1{count}{date}{subtype}{charge_type}{currency}{account}{total}'
           '{reference}{check_sum}\r\n'.format(
               count=txt_field(count, 'int', 6, left=False),
               date=txt_field(header['payment_date'], 'date'),
               subtype=header['subtype'],
               charge_type='C',
               currency=currency,
               account=txt_field(header['charge_acc'], 'str', 20),
               total=txt_field(total, 'float', 17, left=False,
                               decimal_point=True),
               reference=txt_field(header['glosa'] or '', 'str', 40),
               check_sum=checksum,
           )]
    for line in lines:
        if line['amount'] <= 0:
            continue
        out.append('2{account_type}{payment_doc}{p_doc_type}{p_doc_num}   '
                   '{beneficiary_name}{beneficiary_ref}{company_ref}'
                   '{currency}{amount}{flag}\r\n'.format(
                       account_type=account_type.get(line['acc_type'], ' '),
                       payment_doc=txt_field(line['acc_number'], 'str', 20),
                       p_doc_type=line['doc_bcp'],
                       p_doc_num=txt_field(line['doc_number'], 'str', 12),
                       beneficiary_name=txt_field(line['name'], 'str', 75),
                       beneficiary_ref=txt_field(line['reference'],
                                                 'str', 40),
                       company_ref=txt_field(header['company_name'],
                                             'str', 20),
                       currency=currency,
                       amount=txt_field(line['amount'], 'float', 17,
                                        left=False, decimal_point=True),
                       flag='S' if header['idc_flag'] else 'N',
                   ))
    return ''.join(out)


def interbank_haberes_txt(header, lines):
    """TXT Interbank haberes (port de ``get_interbank_hr_txt``).

    Rarezas v18 conservadas: el total USD de la cabecera se rellena a la
    DERECHA (``left=True``) mientras el de soles va a la izquierda; el
    detalle deja celular/email en blanco fijo."""
    total = sum(custom_round(line['amount'], 2) for line in lines)
    out = ['0104{espacios}{date}{espacios2}{count}{soles_total}{usd_total}'
           'MC001\r\n'.format(
               espacios=' ' * 36,
               date=txt_field(header['now'], 'datetime'),
               espacios2=' ' * 9,
               count=txt_field(len(lines), 'int', 6, left=False),
               soles_total=txt_field(total, 'float', 15, left=False)
               if header['currency'] == 'PEN' else '0' * 15,
               usd_total=txt_field(total, 'float', 15)
               if header['currency'] == 'USD' else '0' * 15,
           )]
    account_type = {'0': '001', '1': '002', '3': ' ' * 3}
    charge_currency = '01' if header['currency'] == 'PEN' else '10'
    for line in lines:
        if line['amount'] <= 0:
            continue
        if header['person_type'] == 'P':
            benef_name = (txt_field(line.get('last_name') or '', 'str', 20)
                          + txt_field(line.get('m_last_name') or '',
                                      'str', 20)
                          + txt_field(line.get('names') or '', 'str', 20))
        else:
            benef_name = txt_field(line['name'], 'str', 60)
        is_cci = line['acc_type'] == '3'
        out.append('02{doc_type}{benef_code}{doc_number}{date_to}'
                   '{charge_currency}{amount} {charge_type}{account_type}'
                   '{account_currency}{acc_number}{person_type}{p_doc_type}'
                   '{p_doc_num}{benef_name}{currency_cts}{amount_cts}'
                   '{filler}{cell_phone}{email}\r\n'.format(
                       doc_type=line['doc_interbank'],
                       benef_code=txt_field(line['doc_number'], 'str', 20),
                       doc_number=' ' * 19,
                       date_to=' ' * 8,
                       charge_currency=charge_currency,
                       amount=txt_field(line['amount'], 'float', 15,
                                        left=False),
                       charge_type='99' if is_cci else '09',
                       account_type=account_type.get(line['acc_type'],
                                                     ' ' * 3),
                       account_currency=' ' * 2 if is_cci
                       else charge_currency,
                       acc_number=(' ' * 3) + txt_field(
                           line['acc_number'], 'str', 20) if is_cci
                       else txt_field(line['acc_number'], 'str', 23),
                       person_type=header['person_type'] or ' ',
                       p_doc_type=line['doc_interbank'],
                       p_doc_num=txt_field(line['doc_number'], 'str', 15),
                       benef_name=benef_name,
                       currency_cts=' ' * 2,
                       amount_cts='0' * 15,
                       filler=' ' * 6,
                       cell_phone=' ' * 40,
                       email=' ' * 140,
                   ))
    return ''.join(out)


def scotiabank_haberes_txt(header, lines):
    """TXT Scotiabank haberes (port de ``get_scotiabank_hr_txt_2``, la
    variante viva del v18 — sin línea de cabecera)."""
    doc_type = {'1': '1', '4': '2', '7': '3'}
    out = []
    for line in lines:
        if line['amount'] <= 0:
            continue
        is_cci = line['acc_type'] == '3'
        out.append('{doc_type}{doc_number}{employee_name}{payment_way}'
                   '{acc_number}{acc_number_cci}{amount}{labor_regime}'
                   '{currency}{concept}{payment_type}\r\n'.format(
                       doc_type=doc_type.get(line['doc_sunat'], ' '),
                       doc_number=txt_field(
                           (line['doc_number'] or '').strip(), 'str', 12),
                       employee_name=txt_field(line['name'], 'str', 60),
                       payment_way=header['payment_way'],
                       acc_number=txt_field(
                           line['acc_number'] if not is_cci else '',
                           'str', 10),
                       acc_number_cci=txt_field(
                           line['acc_number'] if is_cci else '', 'str', 20),
                       amount=txt_field(line['amount'], 'float', 11,
                                        left=False),
                       labor_regime='1',
                       currency='00' if header['currency'] == 'PEN'
                       else '01',
                       concept=txt_field('HABERES', 'str', 20),
                       payment_type='02',
                   ))
    return ''.join(out)


def banbif_haberes_txt(header, lines):
    """TXT BanBif haberes (port de ``get_banbif_hr_txt``): el correlativo
    solo avanza con las líneas emitidas (monto > 0)."""
    out, n = [], 0
    for line in lines:
        if line['amount'] <= 0:
            continue
        n += 1
        out.append('{numcor}{p_doc_type}{p_doc_num}{apepat}{apemat}{names}'
                   '{street}{phone}{platype}{codbank}{account_number}'
                   '{currency_type}{amount}{motdep}'.format(
                       numcor=str(n).rjust(7, ' '),
                       p_doc_type=line['doc_banbif'],
                       p_doc_num=txt_field(line['doc_number'], 'str', 11),
                       apepat=txt_field(line.get('last_name') or '',
                                        'str', 20),
                       apemat=txt_field(line.get('m_last_name') or '',
                                        'str', 20),
                       names=txt_field(line.get('names') or '', 'str', 44),
                       street=txt_field(line.get('street')
                                        or 'SIN DIRECCION', 'str', 60),
                       phone=txt_field(line.get('mobile') or 'SINTELEFON',
                                       'str', 10),
                       platype='H',
                       codbank=line.get('acc_bic') or '038',
                       account_number=line['acc_number'].rjust(20, ' '),
                       currency_type='1',
                       amount=_banbif_amount(line['amount']),
                       motdep=header['subtype_banbif'],
                   ) + '\r\n')
    return ''.join(out)


# ----------------------------------------------------------------------
# CTS
# ----------------------------------------------------------------------
def bbva_cts_txt(header, lines):
    """TXT BBVA CTS (port de ``get_bbva_cts_txt``): cabecera 600 (PEN) /
    610 (USD); el detalle conserva el TAB literal del v18 entre el monto
    y la referencia."""
    dollars = header['cts_dollars']
    total = sum(custom_round(line['amount'], 2) for line in lines)
    out = ['{code}{account}{currency}{total}{process}{date}{hour}'
           '{reference}{count}{valid}'.format(
               code=610 if dollars else 600,
               account=_bbva_charge_account(header),
               currency='USD' if dollars else 'PEN',
               total=txt_field(total, 'float', 15, left=False),
               process='F',
               date=txt_field(header['payment_date'], 'date')
               if header['process_type'] == 'F' else ' ' * 8,
               hour='D',
               reference=txt_field(header['glosa'], 'str', 25)
               if header['glosa'] else ' ' * 25,
               count=str(len(lines)).zfill(6),
               valid=header['owner_validation'],
           ) + ' ' * 68 + '\r\n']
    for line in lines:
        if line['amount'] <= 0:
            continue
        if header.get('alert_indicator') == 'E':
            alert_val = line.get('email') or ''
        elif header.get('alert_indicator') == 'C':
            alert_val = line.get('phone') or ''
        else:
            alert_val = ''
        out.append('002{p_doc_type}{p_doc_num}{charge_type}{payment_doc}'
                   '{beneficiary_name}{amount}\t{reference}'
                   '{alert_indicator}{alert_val}{whites}{last_6_rem}'
                   '{amount_currency}{filler}\r\n'.format(
                       p_doc_type=line['doc_bbva'],
                       p_doc_num=txt_field(line['doc_number'], 'str', 12),
                       charge_type='I' if line['acc_type'] == '3' else 'P',
                       payment_doc=txt_field(line['acc_number'], 'str', 20),
                       beneficiary_name=txt_field(line['name'], 'str', 40),
                       amount=txt_field(line['amount'], 'float', 15,
                                        left=False),
                       reference=txt_field(header['cts_name'], 'str', 40),
                       alert_indicator=header.get('alert_indicator') or ' ',
                       alert_val=txt_field(alert_val, 'str', 50),
                       whites=' ' * 53,
                       last_6_rem=' ' * 15,
                       amount_currency='USD' if dollars else 'PEN',
                       filler=' ' * 18,
                   ))
    return ''.join(out)


def bcp_cts_txt(header, lines):
    """TXT BCP CTS (port de ``get_bcp_cts_txt``).

    El checksum usa TODAS las cuentas destino del registro con monto > 0
    en cualquiera de las dos monedas (``cts_checksum_accs``), no solo las
    de la moneda emitida — rareza v18 conservada. El campo de monto del
    detalle concatena monto + moneda + base computable ×4."""
    dollars = header['cts_dollars']
    currency = '1001' if dollars else '0001'
    total = sum(custom_round(line['amount'], 2) for line in lines)
    checksum = str(
        int(header['charge_acc'][3:])
        + sum(int(acc[3:]) for acc in header['cts_checksum_accs'])
    ).rjust(15, '0')
    out = ['1{count}{date}{charge_type}{currency}{account}{company_doc}'
           '{company_ruc}{total}{reference}{check_sum}\r\n'.format(
               count=txt_field(len(lines), 'int', 6, left=False),
               date=txt_field(header['payment_date'], 'date'),
               charge_type='C',
               currency=currency,
               account=txt_field(header['charge_acc'], 'str', 20),
               company_doc=6,
               company_ruc=txt_field(header['company_vat'], 'str', 12),
               total=txt_field(total, 'float', 17, left=False,
                               decimal_point=True),
               reference=txt_field(header['glosa'] or '', 'str', 40),
               check_sum=checksum,
           )]
    for line in lines:
        if line['amount'] <= 0:
            continue
        out.append('2{payment_doc}{p_doc_type}{p_doc_num}'
                   '{beneficiary_name}{beneficiary_ref}{company_ref}'
                   '{currency}{amount}\r\n'.format(
                       payment_doc=txt_field(line['acc_number'], 'str', 20),
                       p_doc_type=line['doc_bcp'],
                       p_doc_num=txt_field(line['doc_number'], 'str', 15),
                       beneficiary_name=txt_field(line['name'], 'str', 75),
                       beneficiary_ref=txt_field(header['cts_name'],
                                                 'str', 40),
                       company_ref=txt_field(header['company_name'],
                                             'str', 20),
                       currency=currency,
                       amount=txt_field(line['amount'], 'float', 17,
                                        left=False, decimal_point=True)
                       + currency
                       + txt_field(line['computable_base'], 'float', 17,
                                   left=False, decimal_point=True),
                   ))
    return ''.join(out)


def interbank_cts_txt(header, lines):
    """TXT Interbank CTS (port de ``get_interbank_cts_txt``): cabecera
    '0106'; el detalle conserva los 7 TABs literales del v18 entre el
    tipo de cuenta y la moneda de la cuenta."""
    total = sum(custom_round(line['amount'], 2) for line in lines)
    out = ['0106{espacios}{date}{espacios2}{count}{soles_total}{usd_total}'
           'MC001\r\n'.format(
               espacios=' ' * 36,
               date=txt_field(header['now'], 'datetime'),
               espacios2=' ' * 9,
               count=txt_field(len(lines), 'int', 6, left=False),
               soles_total=txt_field(total, 'float', 15, left=False)
               if header['currency'] == 'PEN' else '0' * 15,
               usd_total=txt_field(total, 'float', 15)
               if header['currency'] == 'USD' else '0' * 15,
           )]
    account_type = {'0': '001', '1': '007', '3': ' ' * 3}
    charge_currency = '01' if header['currency'] == 'PEN' else '10'
    for line in lines:
        if line['amount'] <= 0:
            continue
        if header['person_type'] == 'P':
            benef_name = (txt_field(line.get('last_name') or '', 'str', 20)
                          + txt_field(line.get('m_last_name') or '',
                                      'str', 20)
                          + txt_field(line.get('names') or '', 'str', 20))
        else:
            benef_name = txt_field(line['name'], 'str', 60)
        is_cci = line['acc_type'] == '3'
        out.append('02{doc_type}{benef_code}{doc_number}{date_to}'
                   '{charge_currency}{amount} {charge_type}{account_type}'
                   '\t\t\t\t\t\t\t{account_currency}{acc_number}'
                   '{person_type}{p_doc_type}{p_doc_num}{benef_name}'
                   '{currency_cts}{amount_cts}{espacios}\r\n'.format(
                       doc_type=line['doc_interbank'],
                       benef_code=txt_field(line['doc_number'], 'str', 20),
                       doc_number=' ' * 19,
                       date_to=' ' * 8,
                       charge_currency=charge_currency,
                       amount=txt_field(line['amount'], 'float', 15,
                                        left=False),
                       charge_type='99' if is_cci else '09',
                       account_type=account_type.get(line['acc_type'],
                                                     ' ' * 3),
                       account_currency=' ' * 2 if is_cci
                       else charge_currency,
                       acc_number=(' ' * 3) + txt_field(
                           line['acc_number'], 'str', 20) if is_cci
                       else txt_field(line['acc_number'], 'str', 23),
                       person_type=header['person_type'] or ' ',
                       p_doc_type=line['doc_interbank'],
                       p_doc_num=txt_field(line['doc_number'], 'str', 15),
                       benef_name=benef_name,
                       currency_cts=charge_currency,
                       amount_cts=txt_field(line['computable_base'],
                                            'float', 15, left=False),
                       espacios=' ' * 186,
                   ))
    return ''.join(out)


def scotiabank_cts_txt(header, lines):
    """TXT Scotiabank CTS (port de ``get_scotiabank_cts_txt``).

    Rarezas v18 conservadas: el nro. de documento va con ``ljust(12)``
    SIN limpieza; ``rem_amount`` siempre sale de ``amount_soles`` aunque
    el abono sea en USD; el concepto es un slice crudo de 20 sin pad."""
    dollars = header['cts_dollars']
    out = []
    for line in lines:
        if line['amount'] <= 0:
            continue
        is_cci = line['acc_type'] == '3'
        out.append('{type_document}{number_document}{emp_name}'
                   '{payment_method}{cts_acc}{cci_acc}{rem_amount}'
                   '{cts_currency}{concept}{type_payment}\r\n'.format(
                       type_document=line['doc_sunat'],
                       number_document=(line['doc_number'] or '').ljust(12),
                       emp_name=clean_text((line['name'] or '').ljust(60)),
                       cts_currency='01' if dollars else '00',
                       payment_method='1',  # abono en cuenta CTS (CCI=2)
                       cts_acc=line['acc_number'][0:10],
                       cci_acc=txt_field(
                           line['acc_number'] if is_cci else '', 'str', 20),
                       rem_amount='{0:.2f}'.format(
                           line['amount_soles']).replace('.', '')
                       .zfill(11),
                       type_payment='05',  # CTS
                       concept=(header['cts_name'] or '')[0:20],
                   ))
    return ''.join(out)


def banbif_cts_txt(header, lines):
    """TXT BanBif CTS (port de ``get_banbif_cts_txt``): sin filtro de
    monto > 0 (rareza v18 conservada) y correlativo sobre todas las
    líneas."""
    dollars = header['cts_dollars']
    out = []
    for n, line in enumerate(lines, start=1):
        out.append('{numcor}{p_doc_type}{p_doc_num}{apepat}{apemat}{names}'
                   '{street}{phone}{platype}{codbank}{account_number}'
                   '{currency_type}{amount}{motdep}'.format(
                       numcor=str(n).rjust(7, ' '),
                       p_doc_type=line['doc_banbif'],
                       p_doc_num=txt_field(line['doc_number'], 'str', 11),
                       apepat=txt_field(line.get('last_name') or '',
                                        'str', 20),
                       apemat=txt_field(line.get('m_last_name') or '',
                                        'str', 20),
                       names=txt_field(line.get('names') or '', 'str', 44),
                       street=txt_field(line.get('street')
                                        or 'SIN DIRECCION', 'str', 60),
                       phone=txt_field(line.get('mobile') or 'SINTELEFON',
                                       'str', 10),
                       platype='C',
                       codbank=line.get('acc_bic') or '038',
                       account_number=line['acc_number'].strip()
                       .rjust(20, ' '),
                       currency_type='2' if dollars else '1',
                       amount=_banbif_amount(line['amount']),
                       motdep='0',
                   ) + '\r\n')
    return ''.join(out)


# Dispatcher formato → (función haberes, función CTS, etiqueta archivo)
_BANK_FORMATS = {
    'bbva': (bbva_haberes_txt, bbva_cts_txt, 'BBVA'),
    'bcp': (bcp_haberes_txt, bcp_cts_txt, 'BCP'),
    'interbank': (interbank_haberes_txt, interbank_cts_txt, 'Interbank'),
    'scotiabank': (scotiabank_haberes_txt, scotiabank_cts_txt,
                   'Scotiabank'),
    'banbif': (banbif_haberes_txt, banbif_cts_txt, 'BanBif'),
}


# ======================================================================
# Extensiones de catálogos
# ======================================================================
class ResBank(models.Model):
    """Formato de TXT de pago masivo del banco (port de
    ``hr_automate_multipayment/models/res_bank.py``)."""
    _inherit = 'res.bank'

    format_bank = fields.Selection(
        selection=[
            ('bbva', 'Formato BBVA'),
            ('bcp', 'Formato BCP'),
            ('interbank', 'Formato Interbank'),
            ('scotiabank', 'Formato Scotiabank'),
            ('banbif', 'Formato BanBif'),
        ],
        string='Formato de TXT',
        help='Layout propietario del TXT de pago masivo de haberes/CTS '
             'que genera este banco.')


class ResPartnerBank(models.Model):
    """Tipo de cuenta peruano (port de ``res_partner_bank.py`` v18: la
    validación pasa de onchange a constraint real)."""
    _inherit = 'res.partner.bank'

    type_of_account = fields.Selection(
        selection=[
            ('0', 'Corriente'),
            ('1', 'Ahorros'),
            ('2', 'Detracciones'),
            ('3', 'CCI'),
            ('4', 'Otros'),
        ],
        string='Tipo de cuenta',
        help='Clasificación peruana: la CCI (Código de Cuenta '
             'Interbancario) tiene 20 dígitos; la cuenta de '
             'detracciones SUNAT, 11.')
    branch_name = fields.Char(
        string='Sucursal BBVA',
        help='Código de oficina que el layout BBVA intercala en la '
             'cuenta de cargo (posición 9).')

    @api.constrains('type_of_account', 'acc_number')
    def _check_type_of_account_length(self):
        """Valida la longitud (solo dígitos) según el tipo de cuenta:
        11 para detracciones, 20 para CCI."""
        for account in self.filtered('acc_number'):
            digits = re.sub(r'[^0-9]', '', account.acc_number)
            if account.type_of_account == '2' and len(digits) != 11:
                raise UserError(self.env._(
                    'El número de dígitos para una cuenta de detracción '
                    'debe ser 11.'))
            if account.type_of_account == '3' and len(digits) != 20:
                raise UserError(self.env._(
                    'El número de dígitos para una cuenta CCI debe '
                    'ser 20.'))


class L10nLatamIdentificationType(models.Model):
    """Códigos del tipo de documento por banco (port de
    ``hr.type.document.{bbva,bcp,interbank,banbif}_code`` v18 sobre el
    catálogo latam nativo; data en ``data/bank_codes_data.xml``)."""
    _inherit = 'l10n_latam.identification.type'

    l10n_pe_hr_bbva_code = fields.Char(string='Código BBVA')
    l10n_pe_hr_bcp_code = fields.Char(string='Código BCP')
    l10n_pe_hr_interbank_code = fields.Char(string='Código Interbank')
    l10n_pe_hr_banbif_code = fields.Char(string='Código BanBif')


class HrMainParameter(models.Model):
    """Diarios de banco habilitados para el pago masivo (port de
    ``journals_banks`` v18)."""
    _inherit = 'hr.main.parameter'

    journals_banks = fields.Many2many(
        'account.journal', string='Diarios de pago masivo',
        domain=[('type', '=', 'bank')], check_company=True,
        help='Diarios bancarios desde los que se cargan los sueldos y '
             'la CTS; al generar los pagos se crea un registro por '
             'diario cuyo banco tenga formato TXT presente en las '
             'cuentas destino.')


# ======================================================================
# Modelo central
# ======================================================================
class HrAutomateMultipayment(models.Model):
    """Generador de archivos TXT bancarios para pago masivo a empleados
    (nombre de modelo v18 conservado).

    Flujo: el origen (lote de nómina / quincena / CTS / gratificación /
    vacaciones) crea un registro por diario bancario, se cargan las
    líneas cuya cuenta destino pertenece a un banco con ese formato, se
    genera el TXT (adjunto descargable) y al finalizar se marca el
    origen con ``txt_generated``. Estados: ``draft`` → ``done``.
    """
    _name = 'hr.automate.multipayment'
    _description = 'Pago masivo bancario (TXT)'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre', readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    journal_id = fields.Many2one(
        'account.journal', string='Diario (banco de cargo)',
        required=True, check_company=True,
        domain=[('type', 'in', ('bank', 'cash'))])
    format_bank = fields.Selection(
        related='journal_id.bank_id.format_bank', string='Formato')
    charge_account_id = fields.Many2one(
        related='journal_id.bank_account_id', string='Cuenta de cargo')
    payment_date = fields.Date(
        string='Fecha de pago', required=True,
        default=fields.Date.context_today)
    glosa = fields.Char(string='Glosa')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('done', 'Finalizado')],
        string='Estado', default='draft', copy=False)

    # Origen del pago (uno solo por registro, como en v18)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', ondelete='cascade',
        check_company=True)
    fortnightly_id = fields.Many2one(
        'hr.fortnightly', string='Adelanto quincenal', ondelete='cascade',
        check_company=True)
    cts_id = fields.Many2one(
        'hr.cts', string='Depósito CTS', ondelete='cascade',
        check_company=True)
    gratification_id = fields.Many2one(
        'hr.gratification', string='Gratificación', ondelete='cascade',
        check_company=True)
    vacation_id = fields.Many2one(
        'hr.vacation', string='Liquidación vacacional',
        ondelete='cascade', check_company=True)
    cts_dollars = fields.Boolean(string='CTS en dólares', default=False)

    line_ids = fields.One2many(
        'hr.automate.multipayment.line', 'multipayment_id',
        string='Líneas')

    # --- Configuración BBVA ---
    process_type = fields.Selection(
        selection=[('A', 'Inmediato'), ('H', 'Hora de proceso'),
                   ('F', 'Fecha futura')],
        string='Tipo de proceso (BBVA)', default='A')
    process_hour = fields.Selection(
        selection=[('B', '11:00 a.m.'), ('C', '03:00 p.m.'),
                   ('D', '07:00 p.m.')],
        string='Hora de proceso')
    owner_validation = fields.Selection(
        selection=[('S', 'Valida, si hay error rechaza el abono'),
                   ('N', 'No valida')],
        string='Validación de pertenencia', default='S')
    alert_indicator = fields.Selection(
        selection=[('E', 'Email'), ('C', 'Celular')],
        string='Indicador de aviso')
    # --- Configuración BCP ---
    idc_flag = fields.Boolean(
        string='Validar IDC vs cuenta', default=True)
    subtype = fields.Selection(
        selection=[('G', 'Gratificación'), ('V', 'Vacaciones'),
                   ('M', 'Movilidad'), ('P', 'Pensionista'),
                   ('T', 'Préstamos'), ('4', 'Cuarta categoría'),
                   ('O', 'Otros afectos'), ('X', 'Quinta categoría'),
                   ('Z', 'Otros inafectos')],
        string='Subtipo de planilla (BCP)', default='O', required=True)
    # --- Configuración Interbank ---
    company_code = fields.Char(
        string='Código de la empresa (Interbank)', default='EE01')
    service_code = fields.Char(
        string='Código del servicio (Interbank)', default='01')
    process_type_interbank = fields.Selection(
        selection=[('0', 'En línea'), ('1', 'En diferido')],
        string='Tipo de proceso (Interbank)', default='0')
    person_type = fields.Selection(
        selection=[('P', 'Persona natural'),
                   ('C', 'Comercial o jurídica')],
        string='Tipo de persona', default='P')
    # --- Configuración Scotiabank ---
    charge_way = fields.Selection(
        selection=[('1', 'Cargo en cuenta'),
                   ('2', 'Cobro por cajero, ventanilla o medios '
                         'virtuales'),
                   ('5', 'Afiliado a planilla'),
                   ('6', 'Desafiliado a planilla')],
        string='Modalidad de cobro', default='1')
    charge_type = fields.Selection(
        selection=[('DU', 'Urgencia'), ('NO', 'Normal')],
        string='Tipo de abono', default='DU')
    payment_way = fields.Selection(
        selection=[('2', 'Abono cuenta cte.'),
                   ('3', 'Abono cuenta ahorro'),
                   ('4', 'Abono CCI')],
        string='Forma de pago', default='3')
    # --- Configuración BanBif ---
    subtype_banbif = fields.Selection(
        selection=[('4', 'Cuarta categoría'), ('5', 'Quinta categoría')],
        string='Subtipo de planilla (BanBif)', default='5', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Numera con la secuencia ``PM-`` por compañía (port del
        create v18; la secuencia se crea al vuelo si no existe)."""
        for vals in vals_list:
            company_id = vals.get('company_id') or self.env.company.id
            sequence = self.env['ir.sequence'].sudo().search([
                ('code', '=', 'hr.automate.multipayment'),
                ('company_id', '=', company_id),
            ], limit=1)
            if not sequence:
                sequence = self.env['ir.sequence'].sudo().create({
                    'name': 'Pagos múltiples planillas',
                    'code': 'hr.automate.multipayment',
                    'company_id': company_id,
                    'implementation': 'no_gap',
                    'prefix': 'PM-',
                    'padding': 6,
                })
            vals['name'] = sequence._next()
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Origen
    # ------------------------------------------------------------------
    def _get_origin(self):
        """Devuelve (registro origen, nombre del campo m2o)."""
        self.ensure_one()
        for field_name in ('payslip_run_id', 'fortnightly_id', 'cts_id',
                           'gratification_id', 'vacation_id'):
            origin = self[field_name]
            if origin:
                return origin, field_name
        return None, None

    @staticmethod
    def _get_wage_account(employee):
        """Cuenta de haberes del empleado: la principal nativa v19
        (primera de ``bank_account_ids``); v18: wage_bank_account_id."""
        sudo_employee = employee.sudo()
        return (sudo_employee.primary_bank_account_id
                or sudo_employee.bank_account_ids[:1])

    def _iter_origin_lines(self):
        """Genera dicts crudos (empleado, cuenta destino, montos,
        referencia) del origen, SIN filtrar por banco."""
        self.ensure_one()
        origin, field_name = self._get_origin()
        if not origin:
            return
        if field_name in ('payslip_run_id', 'fortnightly_id'):
            for slip in origin.slip_ids:
                yield {
                    'employee': slip.employee_id,
                    'account': self._get_wage_account(slip.employee_id),
                    'amount': slip.net_wage,
                    'reference': slip.number or '',
                }
        elif field_name == 'gratification_id':
            for line in origin.line_ids:
                yield {
                    'employee': line.employee_id,
                    'account': self._get_wage_account(line.employee_id),
                    'amount': line.total,
                    # v18: en gratificación/vacaciones la referencia de
                    # la línea era el nro. de documento del empleado.
                    'reference': line.employee_id.identification_id or '',
                }
        elif field_name == 'vacation_id':
            for line in origin.line_ids:
                yield {
                    'employee': line.employee_id,
                    'account': self._get_wage_account(line.employee_id),
                    'amount': line.total,
                    'reference': line.employee_id.identification_id or '',
                }
        elif field_name == 'cts_id':
            for line in origin.line_ids:
                if line.less_than_one_month:
                    continue
                yield {
                    'employee': line.employee_id,
                    'account': line.employee_id.sudo().cts_bank_account_id,
                    'amount': line.cts_soles,
                    'amount_usd': line.cts_dollars,
                    'computable_base':
                        (line.wage + line.household_allowance) * 4,
                    'reference': origin.name or '',
                }

    def action_load_lines(self):
        """(Re)carga las líneas del origen cuya cuenta destino pertenece
        a un banco con el formato del diario (port de los onchange
        ``get_slip_ids`` / ``get_cts_line_ids`` / ... v18)."""
        for record in self:
            if record.state != 'draft':
                raise UserError(self.env._(
                    'Solo se pueden recargar líneas en borrador.'))
            record.line_ids.unlink()
            vals_list = []
            for raw in record._iter_origin_lines():
                account = raw['account']
                if account.bank_id.format_bank != record.format_bank:
                    continue
                vals_list.append({
                    'multipayment_id': record.id,
                    'employee_id': raw['employee'].id,
                    'bank_account_id': account.id,
                    'amount': raw['amount'],
                    'amount_usd': raw.get('amount_usd', 0.0),
                    'computable_base': raw.get('computable_base', 0.0),
                    'reference': raw['reference'],
                })
            self.env['hr.automate.multipayment.line'].create(vals_list)
        return True

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------
    def action_done(self):
        """Finaliza y marca el origen como TXT generado (port de
        ``procesing_payments`` v18)."""
        for record in self:
            origin, _field = record._get_origin()
            if not origin:
                raise UserError(self.env._(
                    'Para finalizar debe tener un origen de pago '
                    '(lote, quincena, CTS, gratificación o vacaciones).'))
            origin.txt_generated = True
            record.state = 'done'
        return True

    def action_draft(self):
        """Vuelve a borrador y desmarca el origen (port de
        ``turn_draft`` v18)."""
        for record in self:
            origin, _field = record._get_origin()
            if origin:
                origin.txt_generated = False
            record.state = 'draft'
        return True

    # ------------------------------------------------------------------
    # Validaciones (port de check_account_type / verify_* v18)
    # ------------------------------------------------------------------
    @api.model
    def _check_account(self, account, bank):
        """Valida moneda/tipo/longitud de una cuenta según el banco;
        devuelve el log de errores (str)."""
        log = ''
        if not account:
            return self.env._('Falta una cuenta bancaria\n')
        if not account.currency_id:
            log += self.env._(
                'No se ha especificado una moneda en la cuenta %s\n'
            ) % account.acc_number
        elif not account.type_of_account:
            log += self.env._(
                'No se ha especificado un tipo de cuenta en la cuenta '
                '%s\n') % account.acc_number
        elif account.type_of_account not in ('0', '1', '3'):
            log += self.env._(
                'La cuenta %s tiene un tipo de cuenta diferente a '
                'Corriente, Ahorros o Interbancaria\n'
            ) % account.acc_number
        if account.type_of_account == '3' \
                and len(account.acc_number) != 20:
            log += self.env._(
                'La cuenta %s debe tener 20 dígitos\n'
            ) % account.acc_number
        if bank == 'bbva':
            if account.type_of_account in ('0', '1') \
                    and len(account.acc_number) != 20:
                log += self.env._(
                    'La cuenta %s debe tener 20 dígitos\n'
                ) % account.acc_number
        elif bank == 'bcp':
            if account.type_of_account == '0' \
                    and len(account.acc_number) != 13:
                log += self.env._(
                    'La cuenta %s debe tener 13 dígitos\n'
                ) % account.acc_number
            if account.type_of_account == '1' \
                    and len(account.acc_number) != 14:
                log += self.env._(
                    'La cuenta %s debe tener 14 dígitos\n'
                ) % account.acc_number
        elif bank == 'interbank':
            if account.type_of_account in ('0', '1') \
                    and len(account.acc_number) != 13:
                log += self.env._(
                    'La cuenta %s debe tener 13 dígitos\n'
                ) % account.acc_number
        elif bank == 'scotiabank':
            if account.type_of_account in ('0', '1') \
                    and len(account.acc_number) > 14:
                log += self.env._(
                    'La cuenta %s debe tener menos de 14 dígitos\n'
                ) % account.acc_number
        return log

    _BANK_DOC_FIELD = {
        'bbva': 'l10n_pe_hr_bbva_code',
        'bcp': 'l10n_pe_hr_bcp_code',
        'interbank': 'l10n_pe_hr_interbank_code',
        'banbif': 'l10n_pe_hr_banbif_code',
    }

    def _verify_fields(self, lines):
        """Consolida las verificaciones v18 (``verify_<banco>_*_fields``)
        para las líneas a emitir."""
        self.ensure_one()
        bank = self.format_bank
        log = ''
        charge_account = self.journal_id.bank_account_id
        if bank != 'banbif':
            log += self._check_account(charge_account, bank)
            if charge_account.type_of_account == '3':
                log += self.env._(
                    'No se puede utilizar la cuenta %s de tipo '
                    'interbancaria como cuenta de cargo\n'
                ) % charge_account.acc_number
        if bank == 'bbva':
            if not self.cts_id and not charge_account.branch_name:
                log += self.env._(
                    'No se ha especificado una sucursal en la cuenta '
                    'del banco\n')
            if not self.process_type:
                log += self.env._(
                    'Necesita especificar un tipo de proceso\n')
        elif bank == 'bcp':
            if self.cts_id and not self.company_id.vat:
                log += self.env._(
                    'La compañía %s no tiene un número de RUC '
                    'configurado\n') % self.company_id.name
        elif bank == 'interbank':
            for field_name, label in [
                    ('company_code', 'El código de compañía'),
                    ('service_code', 'El código de servicio'),
                    ('process_type_interbank', 'El tipo de proceso'),
                    ('person_type', 'El tipo de persona')]:
                if not self[field_name]:
                    log += self.env._(
                        '%s es un campo obligatorio\n') % label
        elif bank == 'scotiabank':
            if not self.cts_id and not self.charge_way:
                log += self.env._(
                    'La Modalidad de Cobro es un campo obligatorio\n')
            if self.cts_id and not self.charge_type:
                log += self.env._(
                    'El Tipo de Abono es un campo obligatorio\n')
        doc_field = self._BANK_DOC_FIELD.get(bank)
        for line in lines:
            employee = line.employee_id
            if doc_field and not \
                    employee.l10n_latam_identification_type_id[doc_field]:
                log += self.env._(
                    'El tipo de documento de %(employee)s no tiene su '
                    'código %(bank)s\n') % {
                        'employee': employee.name,
                        'bank': _BANK_FORMATS[bank][2]}
            if not employee.identification_id:
                log += self.env._(
                    '%s no tiene un número de documento asignado\n'
                ) % employee.name
            log += self._check_account(line.bank_account_id, bank)
        if log:
            raise UserError(self.env._(
                'Se han detectado los siguientes errores\n') + log)

    # ------------------------------------------------------------------
    # Generación del TXT
    # ------------------------------------------------------------------
    def _header_dict(self):
        """Cabecera para las funciones puras de formato."""
        self.ensure_one()
        charge_account = self.journal_id.bank_account_id
        cts_all_lines = self.line_ids.filtered(
            lambda l: l.is_txt) if self.cts_id else \
            self.env['hr.automate.multipayment.line']
        return {
            'charge_acc': charge_account.acc_number or '',
            'charge_acc_type': charge_account.type_of_account or '',
            'charge_branch': charge_account.branch_name or '',
            'currency': charge_account.currency_id.name or '',
            'payment_date': self.payment_date,
            'now': fields.Datetime.context_timestamp(
                self, fields.Datetime.now()),
            'glosa': self.glosa or '',
            'company_name': self.company_id.name or '',
            'company_vat': self.company_id.vat or '',
            'process_type': self.process_type,
            'process_hour': self.process_hour or ' ',
            'owner_validation': self.owner_validation,
            'alert_indicator': self.alert_indicator or '',
            'idc_flag': self.idc_flag,
            'subtype': self.subtype,
            'person_type': self.person_type,
            'payment_way': self.payment_way,
            'subtype_banbif': self.subtype_banbif,
            'cts_dollars': self.cts_dollars,
            'cts_name': self.cts_id.name or '',
            'cts_checksum_accs': [
                line.bank_account_id.acc_number for line in cts_all_lines
                if line.amount > 0 or line.amount_usd > 0],
        }

    def _line_dict(self, line):
        """Línea para las funciones puras de formato."""
        employee = line.employee_id
        doc_type = employee.l10n_latam_identification_type_id
        account = line.bank_account_id
        if self.cts_id and self.cts_dollars:
            amount = line.amount_usd
        else:
            amount = line.amount
        # TODO(fase7-revisar): dirección/celular BanBif — v18 leía
        # user_partner_id.street/.mobile; aquí work_contact_id y el
        # mobile_phone del empleado. Validar con datos reales.
        contact = employee.sudo().work_contact_id
        return {
            'doc_bbva': doc_type.l10n_pe_hr_bbva_code or '',
            'doc_bcp': doc_type.l10n_pe_hr_bcp_code or '',
            'doc_interbank': doc_type.l10n_pe_hr_interbank_code or '',
            'doc_banbif': doc_type.l10n_pe_hr_banbif_code or '',
            'doc_sunat': doc_type.l10n_pe_hr_sunat_code or '',
            'doc_number': employee.identification_id or '',
            'name': employee.name or '',
            'last_name': employee.last_name or '',
            'm_last_name': employee.m_last_name or '',
            'names': employee.names or '',
            'acc_number': account.acc_number or '',
            'acc_type': account.type_of_account or '',
            'acc_bic': account.bank_id.bic or '',
            'amount': amount,
            'amount_soles': line.amount,
            'computable_base': line.computable_base,
            'reference': line.reference or '',
            'email': employee.work_email or '',
            'phone': employee.work_phone or '',
            'street': contact.street or '',
            'mobile': employee.mobile_phone or '',
        }

    def _get_txt_lines(self):
        """Líneas a emitir: marcadas ``is_txt`` y, en CTS, con cuenta en
        la moneda del proceso (port de ``get_cts_lines`` v18)."""
        self.ensure_one()
        lines = self.line_ids.filtered('is_txt')
        if self.cts_id:
            currency = 'USD' if self.cts_dollars else 'PEN'
            lines = lines.filtered(
                lambda l: l.bank_account_id.currency_id.name == currency)
        return lines

    def _download_attachment(self, filename, content):
        """Publica el TXT como adjunto del registro y lo descarga
        (mismo patrón que los exportadores PLAME de al_hr_pe)."""
        self.ensure_one()
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'raw': content,
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def action_generate_txt(self):
        """Genera el TXT según el formato del banco del diario (port del
        dispatcher ``get_hr_txt`` / ``get_cts_txt`` v18)."""
        self.ensure_one()
        if not self.journal_id.bank_account_id:
            raise UserError(self.env._(
                'El diario seleccionado no tiene una cuenta bancaria '
                'definida'))
        if self.format_bank not in _BANK_FORMATS:
            raise UserError(self.env._(
                'El diario no tiene un banco con formato definido'))
        haberes_fn, cts_fn, label = _BANK_FORMATS[self.format_bank]
        lines = self._get_txt_lines()
        self._verify_fields(lines)
        header = self._header_dict()
        line_dicts = [self._line_dict(line) for line in lines]
        if self.cts_id:
            content = cts_fn(header, line_dicts)
            filename = '%s_CTS.txt' % label
        else:
            # v18 usaba el mismo layout de haberes para gratificación,
            # quincena y vacaciones (cambian monto y referencia).
            content = haberes_fn(header, line_dicts)
            filename = '%s_Haberes.txt' % label
        return self._download_attachment(
            filename, content.encode('utf-8'))

    # ------------------------------------------------------------------
    # Creación desde los orígenes
    # ------------------------------------------------------------------
    @api.model
    def _generate_for_origin(self, origin, field_name, glosa):
        """Crea un registro por diario bancario configurado cuyo banco
        tenga un formato presente en las cuentas destino del origen
        (port del ``generate_multipayments`` v18, compartido por los 5
        orígenes)."""
        if origin.multipayment_ids.filtered(lambda m: m.state == 'done'):
            raise UserError(self.env._(
                'No se puede generar pagos si ya existen registros de '
                'pago en estado finalizado'))
        origin.multipayment_ids.unlink()
        company = origin.company_id
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        journals = param.journals_banks.filtered(
            lambda j: j.company_id == company)
        if not journals:
            raise UserError(self.env._(
                'Falta configurar los diarios de pago masivo en los '
                'Parámetros Principales de Nómina'))
        template = self.with_company(company).new({
            field_name: origin.id, 'company_id': company.id})
        raw_lines = list(template._iter_origin_lines())
        formats = {raw['account'].bank_id.format_bank
                   for raw in raw_lines if raw['account']}
        for journal in journals:
            if journal.bank_id.format_bank not in formats:
                continue
            multipayment = self.with_company(company).create({
                'company_id': company.id,
                'journal_id': journal.id,
                'payment_date': fields.Date.context_today(self),
                'glosa': glosa,
                field_name: origin.id,
            })
            multipayment.action_load_lines()
        excluded = [raw['employee'].name for raw in raw_lines
                    if not raw['account'].bank_id.format_bank]
        if excluded:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning', 'sticky': True,
                    'message': self.env._(
                        'Se generó exitosamente, excepto los siguientes '
                        'empleados sin banco con formato:\n%s'
                    ) % '\n'.join(excluded),
                },
            }
        return notify_success(self.env._('Se generó exitosamente.'))

    @api.model
    def _origin_action_view(self, origin, title):
        """Acción de ventana con los pagos del origen."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.automate.multipayment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', origin.multipayment_ids.ids)],
            'name': title,
        }


class HrAutomateMultipaymentLine(models.Model):
    """Línea del pago masivo: beneficiario, cuenta destino y monto.

    Sustituye al patrón v18 de escribir ``multipayment_id``/``is_txt``
    sobre las boletas y líneas del origen."""
    _name = 'hr.automate.multipayment.line'
    _description = 'Línea de pago masivo bancario'
    _order = 'employee_id'
    _check_company_auto = True

    multipayment_id = fields.Many2one(
        'hr.automate.multipayment', string='Pago masivo', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='multipayment_id.company_id', string='Compañía',
        store=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True,
        check_company=True)
    identification_id = fields.Char(
        related='employee_id.identification_id', string='Nro. documento')
    bank_account_id = fields.Many2one(
        'res.partner.bank', string='Cuenta destino')
    bank_id = fields.Many2one(
        related='bank_account_id.bank_id', string='Banco')
    amount = fields.Float(string='Monto (S/)')
    amount_usd = fields.Float(
        string='Monto (USD)',
        help='Solo CTS: importe si el depósito se abona en dólares.')
    computable_base = fields.Float(
        string='Base computable ×4',
        help='Solo CTS: (sueldo + asignación familiar) × 4, exigido por '
             'los layouts BCP e Interbank.')
    reference = fields.Char(string='Referencia')
    is_txt = fields.Boolean(string='Incluir en TXT', default=True)


# ======================================================================
# Orígenes: botones «Generar TXT banco»
# ======================================================================
class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    txt_generated = fields.Boolean(
        string='TXT generado', default=False, copy=False)
    multipayment_ids = fields.One2many(
        'hr.automate.multipayment', 'payslip_run_id',
        string='Pagos masivos')
    multipayment_count = fields.Integer(
        compute='_compute_multipayment_count')

    @api.depends('multipayment_ids')
    def _compute_multipayment_count(self):
        for record in self:
            record.multipayment_count = len(record.multipayment_ids)

    def generate_multipayments(self):
        """Crea los pagos masivos del lote (uno por diario/banco)."""
        self.ensure_one()
        periodo = self.periodo_id
        glosa = '%s-%s' % (periodo.code[4:6], periodo.code[0:4]) \
            if periodo and periodo.code else \
            (self.date_end and self.date_end.strftime('%m-%Y') or '')
        return self.env['hr.automate.multipayment']._generate_for_origin(
            self, 'payslip_run_id', glosa)

    def get_multipayments_view(self):
        self.ensure_one()
        return self.env['hr.automate.multipayment']._origin_action_view(
            self, self.env._('Pagos de haberes'))


class HrFortnightly(models.Model):
    _inherit = 'hr.fortnightly'

    txt_generated = fields.Boolean(
        string='TXT generado', default=False, copy=False)
    multipayment_ids = fields.One2many(
        'hr.automate.multipayment', 'fortnightly_id',
        string='Pagos masivos')
    multipayment_count = fields.Integer(
        compute='_compute_multipayment_count')

    @api.depends('multipayment_ids')
    def _compute_multipayment_count(self):
        for record in self:
            record.multipayment_count = len(record.multipayment_ids)

    def generate_multipayments(self):
        """Crea los pagos masivos de la quincena."""
        self.ensure_one()
        glosa = self.date_start.strftime('%m%Y') if self.date_start else ''
        return self.env['hr.automate.multipayment']._generate_for_origin(
            self, 'fortnightly_id', glosa)

    def get_multipayments_view(self):
        self.ensure_one()
        return self.env['hr.automate.multipayment']._origin_action_view(
            self, self.env._('Pagos de quincena'))


class HrCts(models.Model):
    _inherit = 'hr.cts'

    txt_generated = fields.Boolean(
        string='TXT generado', default=False, copy=False)
    multipayment_ids = fields.One2many(
        'hr.automate.multipayment', 'cts_id', string='Pagos masivos')
    multipayment_count = fields.Integer(
        compute='_compute_multipayment_count')

    @api.depends('multipayment_ids')
    def _compute_multipayment_count(self):
        for record in self:
            record.multipayment_count = len(record.multipayment_ids)

    def generate_multipayments(self):
        """Crea los pagos masivos del depósito CTS (la cuenta destino es
        ``cts_bank_account_id``, normalmente en otro banco)."""
        self.ensure_one()
        periodo = self.payslip_run_id.periodo_id
        glosa = '%s-%s' % (periodo.code[4:6], periodo.code[0:4]) \
            if periodo and periodo.code else (self.name or '')
        return self.env['hr.automate.multipayment']._generate_for_origin(
            self, 'cts_id', glosa)

    def get_multipayments_view(self):
        self.ensure_one()
        return self.env['hr.automate.multipayment']._origin_action_view(
            self, self.env._('Pagos de CTS'))


class HrGratification(models.Model):
    _inherit = 'hr.gratification'

    txt_generated = fields.Boolean(
        string='TXT generado', default=False, copy=False)
    multipayment_ids = fields.One2many(
        'hr.automate.multipayment', 'gratification_id',
        string='Pagos masivos')
    multipayment_count = fields.Integer(
        compute='_compute_multipayment_count')

    @api.depends('multipayment_ids')
    def _compute_multipayment_count(self):
        for record in self:
            record.multipayment_count = len(record.multipayment_ids)

    def generate_multipayments(self):
        """Crea los pagos masivos de la gratificación."""
        self.ensure_one()
        periodo = self.payslip_run_id.periodo_id
        glosa = '%s-%s' % (periodo.code[4:6], periodo.code[0:4]) \
            if periodo and periodo.code else (self.name or '')
        return self.env['hr.automate.multipayment']._generate_for_origin(
            self, 'gratification_id', glosa)

    def get_multipayments_view(self):
        self.ensure_one()
        return self.env['hr.automate.multipayment']._origin_action_view(
            self, self.env._('Pagos de gratificación'))


class HrVacation(models.Model):
    _inherit = 'hr.vacation'

    txt_generated = fields.Boolean(
        string='TXT generado', default=False, copy=False)
    multipayment_ids = fields.One2many(
        'hr.automate.multipayment', 'vacation_id', string='Pagos masivos')
    multipayment_count = fields.Integer(
        compute='_compute_multipayment_count')

    @api.depends('multipayment_ids')
    def _compute_multipayment_count(self):
        for record in self:
            record.multipayment_count = len(record.multipayment_ids)

    def generate_multipayments(self):
        """Crea los pagos masivos de la liquidación vacacional."""
        self.ensure_one()
        date_start = self.payslip_run_id.date_start
        glosa = date_start.strftime('%m%Y') if date_start else ''
        return self.env['hr.automate.multipayment']._generate_for_origin(
            self, 'vacation_id', glosa)

    def get_multipayments_view(self):
        self.ensure_one()
        return self.env['hr.automate.multipayment']._origin_action_view(
            self, self.env._('Pagos de vacaciones'))
