"""
Comprobación de un XML UBL 2.1 (factura, boleta o nota de crédito) contra
las reglas de cuadre de SUNAT sobre anticipos, cargos/descuentos y totales.

Fuente: «Reglas de validación - actualizado al 26.08.2026» (hojas Factura2_0,
Boleta2_0, NotaCredito2_0), resumidas en REGLAS_SUNAT_ANTICIPOS_DESCUENTOS.md.
Cada incumplimiento se devuelve con el código de retorno de SUNAT para poder
contrastarlo con el CDR real. Tolerancia de ±1 donde la regla la admite.

Uso::

    from validador_sunat import validar
    errores = validar(xml_bytes)        # [('3277', 'texto'), ...]
"""
import re
from decimal import Decimal

from lxml import etree

NS = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}
TOL = Decimal('1')
IGV_RATES = (Decimal('0.18'), Decimal('0.105'))
# Catálogo 53: códigos de cargos/descuentos (los usados aquí y los demás válidos).
CATALOGO_53 = {'00', '01', '02', '03', '04', '05', '06', '07', '20', '45', '46', '47', '48',
               '49', '50', '51', '52', '53', '61', '62', '63', '64', '65', '66', '67', '68', '69'}
CARGOS = {'45', '46', '47', '48', '49', '50', '51', '52', '53'}
DESCUENTOS_GLOBALES = {'02', '03', '04', '05', '06', '20'}
ANTICIPOS = {'04', '05', '06'}


def _d(node, path):
    value = node.findtext(path, namespaces=NS)
    return Decimal(value.strip()) if value not in (None, '') else Decimal('0')


def _acs(node):
    """(código, es_cargo, monto, base, factor) de los AllowanceCharge directos."""
    result = []
    for ac in node.findall('cac:AllowanceCharge', NS):
        factor = ac.findtext('cbc:MultiplierFactorNumeric', namespaces=NS)
        result.append((
            (ac.findtext('cbc:AllowanceChargeReasonCode', namespaces=NS) or '').strip(),
            (ac.findtext('cbc:ChargeIndicator', namespaces=NS) or '').strip(),
            _d(ac, 'cbc:Amount'), _d(ac, 'cbc:BaseAmount'),
            Decimal(factor) if factor else None,
        ))
    return result


def _suma(acs, codigos):
    return sum((a[2] for a in acs if a[0] in codigos), Decimal('0'))


def validar(xml):
    root = etree.fromstring(xml) if isinstance(xml, (bytes, str)) else xml
    kind = etree.QName(root).localname        # Invoice / CreditNote
    line_tag = 'cac:InvoiceLine' if kind == 'Invoice' else 'cac:CreditNoteLine'
    qty_tag = 'cbc:InvoicedQuantity' if kind == 'Invoice' else 'cbc:CreditedQuantity'
    errores = []

    def err(code, msg):
        errores.append((code, msg))

    # ------------------------------------------------------------------ líneas
    sum_lea_onerosas = Decimal('0')        # tributos 1000/1016/9995/9997/9998
    base_por_tributo = {}
    lines_ac = []
    for line in root.findall(line_tag, NS):
        lid = line.findtext('cbc:ID', namespaces=NS)
        lea = _d(line, 'cbc:LineExtensionAmount')
        qty = _d(line, qty_tag)
        price = _d(line, 'cac:Price/cbc:PriceAmount')
        acs = _acs(line)
        lines_ac.extend(acs)
        for code, ind, amount, base, factor in acs:
            if code not in CATALOGO_53:
                err('2954', f'línea {lid}: código {code} fuera del catálogo 53')
            if (code in ('00', '01') and ind != 'false') or (code in ('47', '48') and ind != 'true'):
                err('3114', f'línea {lid}: ChargeIndicator {ind} no corresponde al código {code}')
            if factor and abs(base * factor - amount) > TOL:
                err('3290', f'línea {lid}: monto {amount} ≠ base {base} × factor {factor}')
        gratuita = False
        for sub in line.findall('cac:TaxTotal/cac:TaxSubtotal', NS):
            tributo = sub.findtext('cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=NS)
            taxable = _d(sub, 'cbc:TaxableAmount')
            if tributo == '9996' and taxable > 0:
                gratuita = True
            if taxable > 0:
                base_por_tributo[tributo] = base_por_tributo.get(tributo, Decimal('0')) + taxable
            if tributo in ('1000', '1016', '9995', '9997', '9998') and taxable > 0:
                sum_lea_onerosas += lea
            if tributo in ('1000', '1016') and taxable > 0 and abs(taxable - lea) > Decimal('0.0001') \
                    and not any(s.findtext('cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=NS) == '2000'
                                for s in line.findall('cac:TaxTotal/cac:TaxSubtotal', NS)):
                err('3272', f'línea {lid}: base {taxable} ≠ valor de venta {lea}')
        if not gratuita:
            # Factura/boleta: precio × cantidad − desc. 00 + cargos 47. Nota de
            # crédito: precio × cantidad, sin cargos ni descuentos de línea.
            if kind == 'Invoice':
                esperado = price * qty - _suma(acs, {'00'}) + _suma(acs, {'47'})
            else:
                esperado = price * qty
            if abs(esperado - lea) > TOL:
                err('3271', f'línea {lid}: valor de venta {lea} ≠ precio {price} × {qty} (± desc./cargos) = {esperado}')

    # --------------------------------------------------------- cargos globales
    gacs = _acs(root)
    for code, ind, amount, base, factor in gacs:
        if code not in CATALOGO_53:
            err('3071', f'global: código {code} fuera del catálogo 53')
        if code in ('00', '01', '47', '48'):
            err('4291', f'global: código de línea {code} usado a nivel documento (observación)')
        if (code in DESCUENTOS_GLOBALES and ind != 'false') or (code in CARGOS and ind != 'true'):
            err('3114', f'global: ChargeIndicator {ind} no corresponde al código {code}')
        if amount <= 0:
            err('2968', f'global {code}: monto {amount} debe ser mayor a cero')
        if base <= 0:
            err('3016', f'global {code}: base {base} debe ser mayor a cero')
        if factor is not None:
            if factor <= 0 or factor >= 1000 or factor.as_tuple().exponent < -5:
                err('3025', f'global {code}: factor {factor} con formato inválido')
            elif abs(base * factor - amount) > TOL:
                err('3307', f'global {code}: monto {amount} ≠ base {base} × factor {factor}')

    # ------------------------------------------------------------- anticipos
    lmt = root.find('cac:LegalMonetaryTotal', NS)
    prepaid_total = _d(lmt, 'cbc:PrepaidAmount') if lmt is not None else Decimal('0')
    pagos = root.findall('cac:PrepaidPayment', NS)
    ids_pago = [p.findtext('cbc:ID', namespaces=NS) for p in pagos]
    for p in pagos:
        if not (p.findtext('cbc:ID', namespaces=NS) or '').strip():
            err('3211', 'PrepaidPayment sin identificador')
        if _d(p, 'cbc:PaidAmount') <= 0:
            err('2503', 'PrepaidPayment con importe ≤ 0')
    if len(ids_pago) != len(set(ids_pago)):
        err('3212', 'identificadores de PrepaidPayment repetidos')
    todas = [(r.findtext('cbc:DocumentTypeCode', namespaces=NS), r.findtext('cbc:ID', namespaces=NS))
             for r in root.findall('cac:AdditionalDocumentReference', NS)]
    for repetido in {x for x in todas if todas.count(x) > 1}:
        err('2365', f'documento relacionado {repetido[0]} {repetido[1]} repetido')
    refs = [r for r in root.findall('cac:AdditionalDocumentReference', NS)
            if r.findtext('cbc:DocumentStatusCode', namespaces=NS)]
    status = [r.findtext('cbc:DocumentStatusCode', namespaces=NS) for r in refs]
    for r in refs:
        st = r.findtext('cbc:DocumentStatusCode', namespaces=NS)
        dtype = r.findtext('cbc:DocumentTypeCode', namespaces=NS)
        num = r.findtext('cbc:ID', namespaces=NS) or ''
        if dtype not in ('02', '03'):
            err('2505', f'anticipo {num}: tipo {dtype} distinto de 02/03')
        if st not in ids_pago:
            err('3214', f'anticipo {num}: identificador {st} sin PrepaidPayment')
        scheme = r.find('cac:IssuerParty/cac:PartyIdentification/cbc:ID', NS)
        if scheme is None or not (scheme.text or '').strip():
            err('3217', f'anticipo {num}: sin RUC del emisor')
        elif scheme.get('schemeID') != '6':
            err('2520', f'anticipo {num}: schemeID {scheme.get("schemeID")} distinto de 6')
        pattern = r'^([F][A-Z0-9]{3}|E001|[0-9]{1,4})-[0-9]{1,8}$' if dtype == '02' \
            else r'^([B][A-Z0-9]{3}|EB01|[0-9]{1,4})-[0-9]{1,8}$'
        if not re.match(pattern, num):
            err('2521', f'anticipo {num}: serie-número inválido para el tipo {dtype}')
    if len(status) != len(set(status)):
        err('3215', 'más de un anticipo con el mismo identificador de pago')
    for pid in ids_pago:
        if pid not in status:
            err('3213', f'PrepaidPayment {pid} sin documento de anticipo relacionado')
    if pagos and prepaid_total <= 0:
        err('3220', 'hay PrepaidPayment pero el total de anticipos es cero')
    if prepaid_total > 0:
        suma_pagos = sum((_d(p, 'cbc:PaidAmount') for p in pagos), Decimal('0'))
        if suma_pagos != prepaid_total:
            err('2509', f'PrepaidAmount {prepaid_total} ≠ suma de PaidAmount {suma_pagos}')
        if not any(a[0] in ANTICIPOS and a[2] > 0 for a in gacs):
            err('3287', 'hay anticipos pero ningún AllowanceCharge 04/05/06')
    if any(a[0] in ANTICIPOS | {'20'} and a[2] > 0 for a in gacs) and prepaid_total <= 0:
        err('3282', 'AllowanceCharge de anticipo sin total de anticipos')

    # ------------------------------------------------- subtotales de tributos
    tax_total = root.find('cac:TaxTotal', NS)
    subtotales = {}
    if tax_total is not None:
        for sub in tax_total.findall('cac:TaxSubtotal', NS):
            tributo = sub.findtext('cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=NS)
            subtotales[tributo] = (_d(sub, 'cbc:TaxableAmount'), _d(sub, 'cbc:TaxAmount'))
        suma = sum((v[1] for k, v in subtotales.items() if k in ('1000', '1016', '2000', '7152', '9999')), Decimal('0'))
        if abs(suma - _d(tax_total, 'cbc:TaxAmount')) > TOL:
            err('3294', f'TaxTotal {_d(tax_total, "cbc:TaxAmount")} ≠ suma de tributos {suma}')
    for tributo in base_por_tributo:
        if tributo in ('1000', '1016', '9995', '9996', '9997', '9998') and tributo not in subtotales:
            err('2638', f'falta el subtotal global del tributo {tributo}')
    if '1000' in subtotales:
        esperado = base_por_tributo.get('1000', Decimal('0')) - _suma(gacs, {'02', '04'}) + _suma(gacs, {'49'})
        taxable, amount = subtotales['1000']
        if abs(taxable - esperado) > TOL:
            err('3277', f'base gravada {taxable} ≠ líneas − desc. 02/04 + cargos 49 = {esperado}')
        base_igv = esperado - _suma(gacs, {'20'})
        if not any(abs(base_igv * r - amount) <= TOL for r in IGV_RATES):
            err('3291', f'IGV {amount} ≠ ({base_igv}) × tasa')
    for tributo, codigo, regla in (('9997', '05', '3275'), ('9998', '06', '3274')):
        if tributo in subtotales:
            esperado = base_por_tributo.get(tributo, Decimal('0')) - _suma(gacs, {codigo})
            if abs(subtotales[tributo][0] - esperado) > TOL:
                err(regla, f'base {tributo} {subtotales[tributo][0]} ≠ líneas − anticipos {codigo} = {esperado}')

    # ------------------------------------------------------- totales globales
    if lmt is not None:
        lea_total = _d(lmt, 'cbc:LineExtensionAmount')
        esperado = sum_lea_onerosas - _suma(gacs, {'02'}) + _suma(gacs, {'49'})
        if abs(lea_total - esperado) > TOL:
            err('3278', f'LineExtensionAmount {lea_total} ≠ líneas − desc. 02 + cargos 49 = {esperado}')
        allowance_total = _d(lmt, 'cbc:AllowanceTotalAmount')
        esperado = _suma(lines_ac, {'01'}) + _suma(gacs, {'03', '63'})
        if abs(allowance_total - esperado) > TOL:
            err('3300', f'AllowanceTotalAmount {allowance_total} ≠ desc. 01 + 03/63 = {esperado}')
        charge_total = _d(lmt, 'cbc:ChargeTotalAmount')
        esperado = _suma(lines_ac, {'48'}) + _suma(gacs, {'45', '46', '50'})
        if abs(charge_total - esperado) > TOL:
            err('3301', f'ChargeTotalAmount {charge_total} ≠ cargos 48 + 45/46/50 = {esperado}')
        inclusive = _d(lmt, 'cbc:TaxInclusiveAmount')
        isc = subtotales.get('2000', (0, Decimal('0')))[1]
        otros = subtotales.get('9999', (0, Decimal('0')))[1]
        icbper = subtotales.get('7152', (0, Decimal('0')))[1]
        base_igv = base_por_tributo.get('1000', Decimal('0')) - _suma(gacs, {'02'}) + _suma(gacs, {'49'})
        candidatos = [lea_total + isc + _suma(gacs, {'20'}) + otros + icbper + base_igv * r for r in IGV_RATES]
        if not any(abs(inclusive - c) <= TOL for c in candidatos):
            err('3279', f'TaxInclusiveAmount {inclusive} ≠ valor de venta + IGV sin restar anticipos ({candidatos[0]})')
        payable = _d(lmt, 'cbc:PayableAmount')
        rounding = _d(lmt, 'cbc:PayableRoundingAmount')
        esperado = inclusive + charge_total - allowance_total - prepaid_total + rounding
        if abs(payable - esperado) > TOL:
            err('3280', f'PayableAmount {payable} ≠ total + cargos − descuentos − anticipos = {esperado}')
    return errores
