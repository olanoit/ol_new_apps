"""Reglas de validación de las filas del SIRE, sin dependencias del ORM.

Se aplican a las líneas del sistema antes de enviarlas a SUNAT: un
reemplazo con un RUC mal escrito o un IGV que no cuadra lo rechaza SUNAT
entero, y el error llega horas después en el ticket.
"""
import re

#: Pesos del dígito verificador del RUC (módulo 11).
RUC_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
#: Prefijos válidos del RUC: 10 persona natural, 15/16/17 casos especiales
#: (no domiciliados, sucesiones…), 20 persona jurídica.
RUC_PREFIXES = ('10', '15', '16', '17', '20')

#: Tabla 10 SUNAT — tipos de comprobante de pago o documento.
DOC_TYPES_TABLE_10 = frozenset(
    ['%02d' % code for code in range(0, 38)]
    + ['%02d' % code for code in range(40, 47)]
    + ['%02d' % code for code in range(48, 57)]
    + ['87', '88', '89', '91', '96', '97', '98', '99'])

#: Comprobantes con serie de 4 caracteres y número de hasta 8 dígitos
#: (factura, boleta, liquidación de compra, notas de crédito y débito).
STRICT_NUMBERING_DOC_TYPES = ('01', '03', '04', '07', '08')
STRICT_SERIE_RE = re.compile(r'^[A-Z0-9]{4}$')
STRICT_NUMBER_RE = re.compile(r'^\d{1,8}$')
GENERIC_SERIE_RE = re.compile(r'^[A-Za-z0-9-]{1,20}$')
GENERIC_NUMBER_RE = re.compile(r'^\d{1,20}$')
CURRENCY_RE = re.compile(r'^[A-Z]{3}$')

#: Tasas del IGV admitidas: 18 % general y 10 % (8 % + 2 % IPM) de la
#: Ley 31556 para restaurantes y hoteles MYPE.
IGV_RATES = (0.18, 0.10)
IVAP_RATES = (0.04,)
#: Tolerancia por comprobante: el IGV se redondea línea a línea.
AMOUNT_TOLERANCE = 1.0


def ruc_is_valid(ruc):
    """``True`` si ``ruc`` tiene 11 dígitos, prefijo válido y dígito verificador correcto."""
    ruc = (ruc or '').strip()
    if len(ruc) != 11 or not ruc.isdigit() or ruc[:2] not in RUC_PREFIXES:
        return False
    total = sum(int(digit) * weight for digit, weight in zip(ruc, RUC_WEIGHTS))
    check = 11 - total % 11
    check = {10: 0, 11: 1}.get(check, check)
    return int(ruc[-1]) == check


def tax_mismatch(base, tax, rates):
    """``True`` si el impuesto no corresponde a la base con ninguna de las tasas."""
    base, tax = base or 0.0, tax or 0.0
    if not base and not tax:
        return False
    if not base:
        return True
    return min(abs(abs(tax) - abs(base) * rate) for rate in rates) > AMOUNT_TOLERANCE


#: Boletas: por encima de este importe el comprador se identifica con su
#: documento y nombre (art. 8, num. 3.10 del Reglamento de Comprobantes).
BOLETA_IDENTIFY_LIMIT = 700.0
#: Documentos de identidad que no identifican a nadie: «0» (sin documento)
#: y los números de relleno que usan algunos TPV para el cliente varios.
ANONYMOUS_ID_TYPES = ('', '0', '-')
ANONYMOUS_ID_NUMBERS = ('', '0', '-', '00000000', '99999999')
#: Plazo para anotar una compra con derecho a crédito fiscal: los 12
#: periodos siguientes al de emisión (art. 2 de la Ley 29215).
RCE_CREDIT_MONTHS = 12


def is_anonymous(id_type, id_number):
    """``True`` si el tipo y número de documento no identifican al cliente."""
    return (id_type or '').strip() in ANONYMOUS_ID_TYPES \
        or (id_number or '').strip() in ANONYMOUS_ID_NUMBERS


def months_between(earlier, later):
    """Periodos (meses) que van de ``earlier`` a ``later``; 0 si es el mismo mes."""
    return (later.year - earlier.year) * 12 + later.month - earlier.month
