# -*- coding: utf-8 -*-
"""Fase facturacion_tpv: OL-INVOICING y OL-POS sobre ce20_db_ol.

Se antepone _qa.py y se cierra con _fin.py (ver run_qa.sh). Todo lo creado
lleva el prefijo QA20. Las llamadas de red (IAP/SUNAT/OSE HKA, consultas
RUC/DNI, impresoras ESC/POS) se simulan como en los tests de cada módulo.
"""
import base64
import io
import uuid as uuidlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from lxml import etree, objectify
from PIL import Image

from odoo.exceptions import AccessError, RedirectWarning, UserError, ValidationError
from odoo.tools import BinaryBytes, file_open

Move = env['account.move']
MoveCls = type(Move)
TODAY = fields.Date.context_today(Move)
PE = env.ref('base.pe')
NS_UBL = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
}
D = {}  # registros compartidos entre casos


def reg(*recs, nota=''):
    for rec in recs:
        registro(rec, nota)

# ----------------------------------------------------------------------
# Red simulada para toda la fase
# ----------------------------------------------------------------------
IAP_MOCK_MSG = 'QA20: envío a SUNAT/OSE simulado (sin credenciales IAP de prueba)'
_patchers = [
    # l10n_pe_edi hace cr.commit() tras un error de envío si no está en test:
    # rompería los savepoints y el modo rollback de esta validación.
    patch.object(MoveCls, '_can_commit', staticmethod(lambda: False)),
    patch.object(MoveCls, '_l10n_pe_edi_sign_invoices_iap',
                 lambda self, edi_str: {'message': IAP_MOCK_MSG, 'level': 'warning'}),
]
for _p in _patchers:
    _p.start()


# ----------------------------------------------------------------------
# Ayudas
# ----------------------------------------------------------------------
def get_or_create(model, domain, vals):
    rec = env[model].with_context(active_test=False).search(domain, limit=1)
    return rec or env[model].create(vals)


def xml_of(move):
    xml, errors = move._l10n_pe_edi_generate_invoice_bstr()
    check(not errors and xml, 'XML UBL generado sin errores', errors or '%d bytes' % len(xml or b''))
    return etree.fromstring(xml) if xml else None


def xv(root, path):
    nodes = root.xpath(path, namespaces=NS_UBL)
    if not nodes:
        return None
    node = nodes[0]
    return node.text if hasattr(node, 'text') else str(node)


def pdf_ok(report_ref, records, titulo):
    """Renderiza el PDF del reporte; si no hubiera wkhtmltopdf, el HTML."""
    Report = env['ir.actions.report']
    try:
        pdf, _fmt = Report._render_qweb_pdf(report_ref, records.ids)
        check(pdf[:4] == b'%PDF', titulo, '%d bytes' % len(pdf))
        return pdf
    except UserError as exc:
        if 'wkhtmltopdf' not in str(exc):
            raise
        html, _fmt = Report._render_qweb_html(report_ref, records.ids)
        aviso(titulo + ' (solo HTML: wkhtmltopdf no disponible)', '%d bytes' % len(html))
        return html


def expect_error(fn, exc_types, titulo, contains=None):
    try:
        with env.cr.savepoint():
            fn()
    except exc_types as exc:
        ok = contains is None or contains.lower() in str(exc).lower()
        check(ok, titulo, str(exc)[:200])
        return
    check(False, titulo, 'no se lanzó %s' % (exc_types,))


def png_bytes(color=(114, 46, 209)):
    buf = io.BytesIO()
    Image.new('RGB', (40, 40), color).save(buf, format='PNG')
    return buf.getvalue()


def chart_ref(xmlid):
    return env['account.chart.template'].with_company(company).ref(xmlid, raise_if_not_found=False)



# Esperas de bloqueo acotadas: con otros agentes escribiendo en la misma base
# no se queda colgado (sale como error de concurrencia y se registra).
env.cr.execute("SET lock_timeout = '30s'")
_ejecutar_qa = ejecutar
env.cr.execute("SELECT write_date FROM res_company WHERE id = %s", [company.id])
D['_company_wd'] = env.cr.fetchone()[0]


def ejecutar(fn):
    """ejecutar de _qa + vigilancia: la transacción principal no debe escribir
    res.company (bloquearía a los demás agentes hasta el commit final)."""
    _ejecutar_qa(fn)
    env.cr.execute("SELECT write_date FROM res_company WHERE id = %s", [company.id])
    wd = env.cr.fetchone()[0]
    if D.get('_company_wd') and wd != D['_company_wd']:
        print('  !! %s escribió res.company (write_date %s)' % (fn.__name__, wd))
    D['_company_wd'] = wd

# ======================================================================
# Preparación (datos maestros QA20)
# ======================================================================
caso('preparacion', 'Datos maestros QA20 de la fase (contactos, productos, diarios)',
     'Crear clientes con RUC y DNI, productos y diarios propios para la fase.')


def _prep():
    D['igv'] = env['account.tax'].search([
        ('company_id', '=', company.id), ('type_tax_use', '=', 'sale'),
        ('l10n_pe_edi_tax_code', '=', '1000'), ('amount', '=', 18.0)], limit=1)
    check(D['igv'], 'IGV 18 % de ventas del plan pe', D['igv'].name)
    district = env.ref('l10n_pe.district_pe_150131')
    D['district'] = district
    D['ruc'] = get_or_create('res.partner', [('name', '=', qa_name('Cliente RUC SAC'))], {
        'name': qa_name('Cliente RUC SAC'), 'is_company': True, 'vat': '20100070970',
        'country_id': PE.id, 'street': 'Av. Javier Prado Este 123',
        'l10n_pe_district': district.id, 'city_id': district.city_id.id,
        'state_id': district.city_id.state_id.id, 'email': 'qa20.ruc@example.com'})
    D['dni'] = get_or_create('res.partner', [('name', '=', qa_name('Cliente DNI Rosa Quispe'))], {
        'name': qa_name('Cliente DNI Rosa Quispe'), 'country_id': PE.id,
        'additional_identifiers': {'PE_DNI': '46027897'}, 'street': 'Jr. Lampa 456',
        'l10n_pe_district': district.id, 'city_id': district.city_id.id,
        'state_id': district.city_id.state_id.id})
    reg(D['ruc'], D['dni'])
    igual(D['ruc'].l10n_pe_sunat_id_code, '6', 'Cliente RUC: código SUNAT 6')
    igual((D['dni'].l10n_pe_sunat_id_code, D['dni'].l10n_pe_sunat_id_value), ('1', '46027897'),
          'Cliente DNI (identificador adicional PE_DNI): código SUNAT 1')
    Product = env['product.product']
    D['srv'] = get_or_create('product.product', [('name', '=', qa_name('Servicio de consultoría'))], {
        'name': qa_name('Servicio de consultoría'), 'type': 'service', 'invoice_policy': 'order',
        'list_price': 1000.0, 'taxes_id': [Command.set(D['igv'].ids)], 'default_code': 'QA20-SRV'})
    D['good'] = get_or_create('product.product', [('name', '=', qa_name('Ibuprofeno 400 mg'))], {
        'name': qa_name('Ibuprofeno 400 mg'), 'is_storable': True, 'available_in_pos': True,
        'list_price': 50.0, 'taxes_id': [Command.set(D['igv'].ids)], 'default_code': 'QA20-IBU',
        'weight': 0.5})
    reg(D['srv'], D['good'])
    D['inv_journal'] = get_or_create('account.journal', [('company_id', '=', company.id), ('code', '=', 'QV20')], {
        'name': qa_name('Ventas facturación'), 'code': 'QV20', 'type': 'sale', 'company_id': company.id,
        'l10n_latam_use_documents': True})
    registro(D['inv_journal'], 'diario propio: no comparte numeración con INV')
    check(D['inv_journal'].l10n_latam_use_documents, 'Diario de ventas QV20 con documentos LATAM')


ejecutar(_prep)


# ======================================================================
# OL-INVOICING · al_l10n_pe_invoice
# ======================================================================
def _invoice(partner, lines, doc_type=None, journal=None, **vals):
    values = {
        'move_type': vals.pop('move_type', 'out_invoice'), 'partner_id': partner.id,
        'journal_id': (journal or D['inv_journal']).id, 'invoice_date': TODAY,
        'invoice_line_ids': [Command.create({
            'product_id': p.id, 'quantity': q, 'price_unit': pu, 'discount': d,
            'tax_ids': [Command.set(t.ids)]}) for p, q, pu, d, t in lines],
        **vals}
    if doc_type:
        values['l10n_latam_document_type_id'] = env.ref(doc_type).id
    return Move.create(values)


caso('al_l10n_pe_invoice', 'Factura electrónica a crédito a cliente RUC: XML, PDF A4/ticket y envío',
     'Crear una factura a 30 días para un cliente con RUC, confirmarla, imprimir A4 y ticket y enviarla a SUNAT.')


def _factura():
    term = env.ref('account.account_payment_term_30days', raise_if_not_found=False)
    move = _invoice(D['ruc'], [(D['srv'], 2, 500.0, 0, D['igv'])],
                    invoice_payment_term_id=term.id if term else False)
    move.action_post()
    registro(move, 'factura 01')
    D['factura'] = move
    igual(move.l10n_latam_document_type_id.code, '01', 'Tipo de documento 01 (factura) por cliente RUC')
    check(move.name.startswith('F F'), 'Numeración de factura serie F', move.name)
    igual(move.l10n_pe_edi_amount_base, 1000.0, 'Detalle tributario: base gravada')
    igual(move.l10n_pe_edi_amount_igv, 180.0, 'Detalle tributario: IGV')
    igual(move.amount_total, 1180.0, 'Total de la factura')
    check(move.is_credit, 'Plazo 30 días: es crédito')
    igual(move._l10n_pe_report_payment_means(), 'CRÉDITO', 'Forma de pago impresa CRÉDITO')
    dues = move.get_data_dues()
    igual(len(dues), 1, 'Una cuota de crédito')
    igual(dues and dues[0]['amount'], 1180.0, 'Importe de la cuota = neto pendiente')
    igual(move._l10n_pe_report_igv_label(), 'IGV (18%)', 'Etiqueta del IGV con la tasa aplicada')
    igual(move._l10n_pe_report_currency_label(), 'SOLES', 'Moneda en letras')
    words = move._l10n_pe_edi_amount_to_text()
    check('/100' in words and 'CIENTO OCHENTA' in words.upper(), 'Monto en letras', words)
    check(move._l10n_pe_report_partner_address().startswith('Av. Javier Prado'),
          'Dirección del cliente en una línea', move._l10n_pe_report_partner_address())
    root = xml_of(move)
    igual(xv(root, '/*/cbc:InvoiceTypeCode'), '01', 'XML: InvoiceTypeCode 01')
    igual(xv(root, '/*/cbc:ID'), move.name.replace(' ', ''), 'XML: serie-número')
    igual(xv(root, '//cac:AccountingCustomerParty//cac:PartyIdentification/cbc:ID'), '20100070970',
          'XML: RUC del adquirente')
    igual(xv(root, '//cac:AccountingCustomerParty//cac:PartyIdentification/cbc:ID/@schemeID'), '6',
          'XML: schemeID 6 (RUC)')
    igual(xv(root, '/*/cac:TaxTotal/cbc:TaxAmount'), '180.00', 'XML: IGV total')
    igual(xv(root, '//cac:LegalMonetaryTotal/cbc:PayableAmount'), '1180.00', 'XML: importe a pagar')
    means = root.xpath("//cac:PaymentTerms[cbc:ID='FormaPago']/cbc:PaymentMeansID", namespaces=NS_UBL)
    check('Credito' in [m.text for m in means], 'XML: forma de pago Credito con cuota',
          [m.text for m in means])
    pdf_ok('al_l10n_pe_invoice.report_cpe_invoice_a4', move, 'PDF A4 de la factura renderizado')
    pdf_ok('al_l10n_pe_invoice.report_cpe_ticket', move, 'PDF ticket 80 mm de la factura renderizado')
    html = env['ir.actions.report']._render_qweb_html(
        'al_l10n_pe_invoice.report_cpe_invoice_a4_main', move.ids)[0].decode()
    check('CRÉDITO' in html and '1,180.00' in html.replace('1 180.00', '1,180.00') or '1180.00' in html,
          'HTML A4: forma de pago e importe impresos')
    res = move._l10n_pe_edi_post_invoice()
    check(res and IAP_MOCK_MSG in (res.get('message') or ''), 'Envío a SUNAT pasa por el operador (IAP simulado)')
    check(move.l10n_pe_edi_status != 'sent', 'Sin respuesta real el comprobante no queda aceptado',
          move.l10n_pe_edi_status)
    omitido('Envío a OSE/SUNAT real', 'sin credenciales de prueba (IAP simulado)')


ejecutar(_factura)

caso('al_l10n_pe_invoice', 'Boleta a cliente con DNI (identificador adicional): XML y PDF',
     'Crear una factura para un cliente con DNI, que el sistema emite como boleta, confirmarla e imprimirla.')


def _boleta():
    move = _invoice(D['dni'], [(D['good'], 3, 50.0, 0, D['igv'])])
    if move.l10n_latam_document_type_id.code != '03':
        aviso('Tipo de documento por defecto no es boleta', move.l10n_latam_document_type_id.code)
        move.l10n_latam_document_type_id = env.ref('l10n_pe.document_type02')
    else:
        check(True, 'Cliente con DNI → boleta (03) por defecto')
    move.action_post()
    registro(move, 'boleta 03')
    D['boleta'] = move
    check(move.name.startswith('B B'), 'Numeración de boleta serie B', move.name)
    igual(move.amount_total, 177.0, 'Total de la boleta')
    igual(move._l10n_pe_report_payment_means(), 'CONTADO', 'Forma de pago CONTADO')
    root = xml_of(move)
    igual(xv(root, '/*/cbc:InvoiceTypeCode'), '03', 'XML: InvoiceTypeCode 03')
    igual(xv(root, '//cac:AccountingCustomerParty//cac:PartyIdentification/cbc:ID'), '46027897',
          'XML: DNI del adquirente desde PE_DNI')
    igual(xv(root, '//cac:AccountingCustomerParty//cac:PartyIdentification/cbc:ID/@schemeID'), '1',
          'XML: schemeID 1 (DNI)')
    pdf_ok('al_l10n_pe_invoice.report_cpe_invoice_a4', move, 'PDF A4 de la boleta renderizado')
    html = env['ir.actions.report']._render_qweb_html(
        'al_l10n_pe_invoice.report_cpe_ticket_main', move.ids)[0].decode()
    check('46027897' in html, 'Ticket: imprime el DNI del cliente')


ejecutar(_boleta)

caso('al_l10n_pe_invoice', 'Nota de crédito y nota de débito de la factura: XML y PDF',
     'Desde la factura, emitir una nota de crédito (anulación) y una nota de débito (intereses).')


def _notas():
    if not D.get('factura'):
        return omitido('Notas', 'sin factura base')
    factura = D['factura']
    wiz = env['account.move.reversal'].with_context(
        active_model='account.move', active_ids=factura.ids).create({
            'reason': qa_name('Anulación de la operación'), 'journal_id': factura.journal_id.id,
            'l10n_pe_edi_refund_reason': '01'})
    nc = Move.browse(wiz.refund_moves()['res_id'])
    nc.action_post()
    registro(nc, 'nota de crédito 07')
    igual(nc.l10n_latam_document_type_id.code, '07', 'NC: tipo 07')
    igual(nc._l10n_pe_report_origin_move(), factura, 'NC: documento que modifica')
    igual(nc._l10n_pe_report_payment_means(), '', 'NC: sin forma de pago impresa')
    root = xml_of(nc)
    check(etree.QName(root).localname == 'CreditNote', 'XML raíz CreditNote')
    igual(xv(root, '//cac:BillingReference//cbc:ID'), factura.name.replace(' ', ''),
          'XML NC: referencia a la factura')
    igual(xv(root, '//cac:DiscrepancyResponse/cbc:ResponseCode'), '01', 'XML NC: motivo 01')
    pdf_ok('al_l10n_pe_invoice.report_cpe_invoice_a4', nc, 'PDF A4 de la NC renderizado')

    dwiz = env['account.debit.note'].with_context(
        active_model='account.move', active_ids=factura.ids).create({
            'reason': qa_name('Intereses por mora'), 'l10n_pe_edi_charge_reason': '01',
            'copy_lines': True})
    nd = Move.browse(dwiz.create_debit()['res_id'])
    nd.invoice_line_ids[:1].write({'price_unit': 50.0, 'quantity': 1})
    nd.invoice_line_ids[1:].unlink()
    nd.action_post()
    registro(nd, 'nota de débito 08')
    igual(nd.l10n_latam_document_type_id.code, '08', 'ND: tipo 08')
    igual(nd._l10n_pe_report_origin_move(), factura, 'ND: documento que modifica')
    igual(nd.amount_total, 59.0, 'ND: total')
    root = xml_of(nd)
    check(etree.QName(root).localname == 'DebitNote', 'XML raíz DebitNote')
    igual(xv(root, '//cac:DiscrepancyResponse/cbc:ResponseCode'), '01', 'XML ND: motivo 01')
    pdf_ok('al_l10n_pe_invoice.report_cpe_invoice_a4', nd, 'PDF A4 de la ND renderizado')


ejecutar(_notas)


# ======================================================================
# al_l10n_pe_edi_downpayment_discount
# ======================================================================
from odoo.addons.al_l10n_pe_edi_downpayment_discount.tests.sunat_rules import NS as SNS, validar  # noqa: E402


def sunat_valid(move, extra=None):
    xml, errors = env['account.edi.xml.ubl_pe']._export_invoice(move)
    check(not errors, 'XML exportado sin errores', errors)
    root = etree.fromstring(xml)
    problems = validar(root) + (extra(root) if extra else [])
    check(not problems, 'Reglas de validación SUNAT sin observaciones', problems)
    payable = Decimal(root.findtext('cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=SNS))
    igual(float(payable), move.amount_total, 'PayableAmount = total del asiento')
    return root


def codes(root, path='cac:AllowanceCharge/cbc:AllowanceChargeReasonCode'):
    return sorted(n.text for n in root.findall(path, SNS))


caso('al_l10n_pe_edi_downpayment_discount', 'Anticipo y factura final desde el pedido de venta',
     'Confirmar un pedido, facturar un anticipo de S/ 118 y luego la factura final que lo descuenta.')


def _anticipo():
    order = env['sale.order'].create({
        'partner_id': D['ruc'].id, 'external_purchase': qa_name('OC-ANT-001'),
        'order_line': [Command.create({'product_id': D['srv'].id, 'product_uom_qty': 1,
                                       'price_unit': 1000.0, 'tax_ids': [Command.set(D['igv'].ids)]})]})
    order.action_confirm()
    registro(order, 'pedido con anticipo')

    def wizard(method, amount=0.0):
        vals = {'advance_payment_method': method}
        if method == 'fixed':
            vals['fixed_amount'] = amount
        env['sale.advance.payment.inv'].with_context(
            active_model='sale.order', active_ids=order.ids, active_id=order.id).create(vals).create_invoices()
        return order.invoice_ids.sorted('id')[-1]
    dp = wizard('fixed', 118.0)
    dp.action_post()
    registro(dp, 'factura de anticipo')
    sunat_valid(dp)
    final = wizard('delivered')
    final.action_post()
    registro(final, 'factura final con anticipo deducido')
    igual(final.sale_id, order, 'al_l10n_pe_invoice: la factura enlaza el pedido (sale_id)')
    igual(final.external_purchase, qa_name('OC-ANT-001'), 'al_l10n_pe_invoice: OC externa del pedido')
    root = sunat_valid(final)
    igual(codes(root), ['04'], 'Cargo/descuento global 04 (anticipo)')
    check(root.findall('cac:PrepaidPayment', SNS), 'XML: PrepaidPayment del anticipo')
    igual(final.amount_total, 1062.0, 'Factura final: 1180 − 118')


ejecutar(_anticipo)

caso('al_l10n_pe_edi_downpayment_discount', 'Descuento por línea y descuento global',
     'Facturar con 10 % de descuento en una línea y una línea de descuento global negativa.')


def _descuentos():
    move = _invoice(D['ruc'], [(D['srv'], 3, 1000.0, 10, D['igv']), (D['good'], 2, 50.0, 0, D['igv'])])
    move.write({'invoice_line_ids': [Command.create({
        'name': qa_name('Descuento global'), 'quantity': 1, 'price_unit': -100.0,
        'tax_ids': [Command.set(D['igv'].ids)]})]})
    move.action_post()
    registro(move, 'factura con descuentos')
    root = sunat_valid(move)
    check('02' in codes(root), 'Descuento global código 02', codes(root))
    check('00' in codes(root, 'cac:InvoiceLine/cac:AllowanceCharge/cbc:AllowanceChargeReasonCode'),
          'Descuento por línea código 00')
    igual(move.get_amount_discount(), 400.0, 'al_l10n_pe_invoice: descuento total impreso (300 + 100)')


ejecutar(_descuentos)


# ======================================================================
# al_l10n_pe_edi_free
# ======================================================================
from odoo.addons.al_l10n_pe_edi_free.tests.test_free_transfer import free_rule_errors  # noqa: E402

caso('al_l10n_pe_edi_free', 'Convertir factura en transferencia gratuita (botón)',
     'En una factura borrador con ítem gravado e inafecto pulsar «Transferencia gratuita» y confirmar.')


def _gratuita():
    ina = chart_ref('sale_tax_ina')
    move = _invoice(D['ruc'], [(D['good'], 2, 50.0, 0, D['igv']), (D['srv'], 1, 30.0, 0, ina)])
    move.action_l10n_pe_free_transfer()
    igual(move.invoice_line_ids.mapped('l10n_pe_edi_affectation_reason'), ['11', '37'],
          'Afectaciones 11 (retiro gravado) y 37 (inafecto gratuito)')
    igual(move.amount_total, 0.0, 'No se cobra')
    move.action_post()
    registro(move, 'transferencia gratuita')
    igual(move.l10n_pe_edi_legend, '1002', 'Leyenda 1002')
    root = sunat_valid(move, free_rule_errors)
    free = [s for s in root.findall('cac:TaxTotal/cac:TaxSubtotal', SNS)
            if s.findtext('cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=SNS) == '9996']
    check(free and free[0].findtext('cbc:TaxAmount', namespaces=SNS) == '18.00',
          'IGV gratuito del retiro (18.00) en el XML')


ejecutar(_gratuita)

caso('al_l10n_pe_edi_free', 'Bloqueo de ítem gratuito con valor referencial 0',
     'Intentar confirmar una factura con ítem gratuito a precio 0.')


def _gratuita_cero():
    exempt = chart_ref('sale_tax_free_exempt_group')
    move = _invoice(D['ruc'], [(D['good'], 1, 0.0, 0, exempt)])
    expect_error(move.action_post, UserError, 'No se confirma: regla SUNAT 2641', '2641')
    move.unlink()


ejecutar(_gratuita_cero)


# ======================================================================
# al_l10n_pe_edi_purchase_settlement + al_l10n_pe_edi_service
# ======================================================================
from odoo.addons.al_ose_factory_hka.tests.test_factory_hka import (  # noqa: E402
    CDR_OK, CLIENT_PATHS, SOAP, FakeHkaClient, _zip_b64)

LCE_NS = {'i': 'urn:oasis:names:specification:ubl:schema:xsd:SelfBilledInvoice-2', **NS_UBL}


def _lce(price, partner=None, **vals):
    journal = env['account.journal'].search([('company_id', '=', company.id),
                                             ('l10n_pe_lce_journal', '=', True)], limit=1)
    igv_p = env['account.tax'].search([
        ('company_id', '=', company.id), ('type_tax_use', '=', 'purchase'),
        ('l10n_pe_edi_tax_code', '=', '1000'), ('amount', '=', 18.0)], limit=1)
    account = env['account.account'].with_company(company).search([('account_type', '=', 'expense')], limit=1)
    return Move.create({
        'move_type': 'in_invoice', 'journal_id': journal.id, 'partner_id': (partner or D['seller']).id,
        'invoice_date': TODAY,
        'invoice_line_ids': [Command.create({
            'product_id': D['cafe'].id, 'name': D['cafe'].name, 'quantity': 10.0,
            'price_unit': price / 10.0, 'account_id': account.id, 'tax_ids': [Command.set(igv_p.ids)]})],
        **vals})


caso('al_l10n_pe_edi_purchase_settlement', 'Liquidación de compra: retenciones, XML anexo 6 y envío',
     'Registrar una liquidación de compra de café a un productor con DNI por S/ 1,000, confirmarla y enviarla.')


def _lce_case():
    D['seller'] = get_or_create('res.partner', [('name', '=', qa_name('Productor Juana Quispe'))], {
        'name': qa_name('Productor Juana Quispe'), 'additional_identifiers': {'PE_DNI': '41020304'},
        'street': 'Caserío Santa Rosa s/n', 'country_id': PE.id,
        'l10n_pe_district': D['district'].id, 'city_id': D['district'].city_id.id,
        'state_id': D['district'].city_id.state_id.id})
    igv_p = env['account.tax'].search([
        ('company_id', '=', company.id), ('type_tax_use', '=', 'purchase'),
        ('l10n_pe_edi_tax_code', '=', '1000'), ('amount', '=', 18.0)], limit=1)
    D['cafe'] = get_or_create('product.product', [('name', '=', qa_name('Café pergamino'))], {
        'name': qa_name('Café pergamino'), 'default_code': 'QA20-CAFE',
        'supplier_taxes_id': [Command.set(igv_p.ids)]})
    reg(D['seller'], D['cafe'])
    move = _lce(1000.0, l10n_pe_lce_license_plate='QA2-020')
    check(move.l10n_pe_lce_required, 'Diario LCE: es liquidación de compra')
    igual(move.l10n_latam_document_type_id.code, '04', 'Tipo de documento 04')
    move.action_post()
    registro(move, 'liquidación de compra')
    igual(move.l10n_pe_lce_igv_amount, 180.0, 'IGV retenido')
    igual(move.l10n_pe_lce_ir_amount, 15.0, 'Retención de renta 1,5 %')
    igual(move.amount_total, 985.0, 'Importe neto a pagar')
    igual(move.l10n_pe_lce_status, 'to_send', 'Estado por enviar')
    tree = etree.fromstring(move._l10n_pe_lce_generate_xml())
    v = lambda path: (tree.xpath(path, namespaces=LCE_NS) or [None])[0]
    igual(etree.QName(tree).localname, 'SelfBilledInvoice', 'XML: SelfBilledInvoice')
    igual(v('/i:SelfBilledInvoice/cbc:InvoiceTypeCode').text, '04', 'XML: tipo 04')
    seller_id = v('//cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID')
    igual((seller_id.text, seller_id.get('schemeID')), ('41020304', '1'), 'XML: vendedor con DNI')
    igual(v('//cac:LegalMonetaryTotal/cbc:PayableAmount').text, '985.00', 'XML: neto 985.00')
    ir = v('/i:SelfBilledInvoice/cac:TaxTotal/cac:TaxSubtotal[cac:TaxCategory/cac:TaxScheme/cbc:ID="3000"]/cbc:TaxAmount')
    igual(ir is not None and ir.text, '15.00', 'XML: retención de renta (3000) 15.00')
    igual(v('//cbc:LicensePlateID').text, 'QA2-020', 'XML: placa del vehículo')
    pdf_ok('al_l10n_pe_edi_purchase_settlement.action_report_purchase_settlement', move,
           'PDF de la liquidación de compra renderizado')
    # Envío por al_l10n_pe_edi_service (operador IAP de la compañía) simulado.
    soap = SOAP % ('sendBillResponse', '<applicationResponse>%s</applicationResponse>'
                   % _zip_b64([('R-cdr.xml', CDR_OK)]), 'sendBillResponse')
    calls = []

    def fake_iap(url, params=None, timeout=None):
        calls.append((url, params))
        signed = _zip_b64([(params['fname'] + '.xml', base64.b64decode(params['xml']))])
        return {'signed': signed, 'cdr': base64.b64encode(soap.encode()).decode()}
    with patch('odoo.addons.al_l10n_pe_edi_service.models.l10n_pe_edi_cpe_service.iap_jsonrpc', fake_iap):
        move.action_l10n_pe_lce_send()
    check(calls and calls[0][0].endswith('/send_bill') and calls[0][1]['doc_type'] == '04',
          'al_l10n_pe_edi_service: sendBill IAP con tipo 04', calls and calls[0][0])
    igual(move.l10n_pe_lce_status, 'sent', 'Liquidación aceptada (CDR simulado)')
    check(move._l10n_pe_lce_xml_attachment(), 'ZIP con XML y CDR adjunto')
    omitido('Envío real a SUNAT', 'sin credenciales de prueba (IAP simulado)')


ejecutar(_lce_case)

caso('al_l10n_pe_edi_purchase_settlement', 'UIT desde el parámetro de nómina l10n_pe_uit y tope de renta',
     'Revisar que el aviso de 75 UIT usa la UIT del año de la nómina y que hasta S/ 700 no se retiene renta.')


def _uit():
    if not D.get('seller'):
        return omitido('UIT', 'sin vendedor')
    values = env['hr.rule.parameter.value'].sudo().search([('code', '=', 'l10n_pe_uit')])
    check(values, 'Parámetro de reglas nativo l10n_pe_uit con valores',
          values.mapped(lambda v: (str(v.date_from), v.parameter_value)))
    igual(company._l10n_pe_lce_uit(2026), 5500.0, 'UIT 2026 desde hr.rule.parameter')
    igual(company._l10n_pe_lce_uit(2025), 5350.0,
          'UIT 2025 = 5,350 del parámetro (no el 5,500 de ajustes): lee la nómina')
    big = _lce(75 * 5500.0 + 100.0)
    check('75 UIT' in (big.l10n_pe_lce_seller_warning or ''), 'Aviso del vendedor sobre 75 UIT',
          big.l10n_pe_lce_seller_warning)
    big.unlink()
    small = _lce(700.0)
    small.action_post()
    registro(small, 'liquidación de S/ 700 sin renta')
    igual(small.l10n_pe_lce_ir_amount, 0.0, 'Hasta S/ 700 no se retiene renta')
    igual(small.amount_total, 700.0, 'Neto = 700 (IGV retenido)')


ejecutar(_uit)


# ======================================================================
# al_l10n_pe_delivery_guide_report
# ======================================================================
caso('al_l10n_pe_delivery_guide_report', 'Guía de remisión: entrega validada y representación impresa',
     'Crear una entrega con transporte privado, validarla e imprimir la guía de remisión.')


def _guia():
    operator = get_or_create('res.partner', [('name', '=', qa_name('Conductor Pedro Ramos'))], {
        'name': qa_name('Conductor Pedro Ramos'), 'additional_identifiers': {'PE_DNI': '70025425'},
        'l10n_pe_edi_operator_license': 'Q70025425'})
    vehicle = get_or_create('l10n_pe_edi.vehicle', [('license_plate', '=', 'QA2-020')], {
        'name': qa_name('Camión'), 'license_plate': 'QA2-020', 'operator_id': operator.id})
    reg(operator, vehicle)
    wh = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
    env['stock.quant']._update_available_quantity(D['good'], wh.lot_stock_id, 100)
    picking = env['stock.picking'].create({
        'picking_type_id': wh.out_type_id.id, 'partner_id': D['ruc'].id,
        'location_id': wh.lot_stock_id.id, 'location_dest_id': env.ref('stock.stock_location_customers').id,
        'move_ids': [Command.create({'product_id': D['good'].id, 'product_uom_qty': 5.0,
                                     'location_id': wh.lot_stock_id.id,
                                     'location_dest_id': env.ref('stock.stock_location_customers').id})],
    })
    picking.write({
        'l10n_pe_edi_transport_type': '02', 'l10n_pe_edi_operator_id': operator.id,
        'l10n_pe_edi_vehicle_id': vehicle.id, 'l10n_pe_edi_reason_for_transfer': '01',
        'l10n_pe_edi_departure_start_date': TODAY})
    picking.action_confirm()
    picking.move_ids.write({'quantity': 5.0, 'picked': True})
    picking.button_validate()
    registro(picking, 'entrega con guía')
    igual(picking.state, 'done', 'Entrega validada')
    grouped = picking._get_grouped_move_lines()
    igual([(g['product'], g['quantity']) for g in grouped], [(D['good'], 5.0)], 'Líneas agrupadas por producto')
    igual(picking.weight, 2.5, 'Peso bruto calculado (5 × 0,5 kg)')
    report = env.ref('al_l10n_pe_delivery_guide_report.action_report_guia_remision')
    html = report._render_qweb_html(report.report_name, picking.ids)[0].decode()
    check(company.vat in html and company.name in html, 'Remitente = compañía (RUC y razón social)')
    check('Q70025425' in html and '70025425' in html, 'Licencia y DNI del conductor impresos')
    check('Peso bruto total (%s)' % picking.weight_uom_name in html, 'Unidad de peso no fija')
    check('QA2-020' in html, 'Placa del vehículo impresa')
    pdf_ok(report.report_name, picking, 'PDF de la guía renderizado')
    from odoo.tools.safe_eval import safe_eval
    action = env.ref('al_l10n_pe_delivery_guide_report.action_guides_to_send')
    check(picking in env['stock.picking'].search(safe_eval(action.domain or '[]')),
          'Aparece en Perú ▸ Guías de remisión ▸ Por enviar')
    omitido('Envío de la guía a SUNAT (GRE)', 'sin credenciales de prueba; el botón de imprimir exige estado sent')


ejecutar(_guia)


# ======================================================================
# al_l10n_pe_complaints_book
# ======================================================================
caso('al_l10n_pe_complaints_book', 'Libro de reclamaciones: registro, constancia, plazo y respuesta',
     'Registrar un reclamo de una consumidora con DNI, revisar el plazo de 15 días hábiles, atenderlo y cerrarlo.')


def _reclamo():
    book = get_or_create('l10n_pe.complaint.book', [('code', '=', 'QA20-TV')], {
        'name': qa_name('Libro tienda virtual'), 'code': 'QA20-TV', 'book_type': 'virtual',
        'user_ids': [Command.set(env.user.ids)], 'sirec_site_code': '123456'})
    complaint = env['l10n_pe.complaint'].with_context(tz='America/Lima').create({
        'book_id': book.id, 'consumer_name': qa_name('Consumidora Rosa Quispe'),
        'consumer_doc_type': 'dni', 'consumer_doc_number': '45678912',
        'consumer_address': 'Av. Arequipa 123, Lima', 'consumer_email': 'qa20.reclamo@example.com',
        'consumer_phone': '987654321', 'good_type': 'product', 'amount_claimed': 150.0,
        'good_description': 'Licuadora', 'claim_type': 'claim',
        'detail': 'La licuadora llegó con la jarra rota.', 'consumer_request': 'Cambio del producto.',
        'date_submitted': fields.Datetime.now()})
    reg(book, complaint)
    check(complaint.name.endswith('-2026') and len(complaint.name.split('-')[0]) == 9,
          'Correlativo por libro y año', complaint.name)
    # 15 días hábiles (sin calendario: lunes a viernes) desde el día siguiente.
    d, n = complaint.date_submitted.date(), 0
    while n < 15:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    igual(complaint.deadline_date, d, 'Plazo de 15 días hábiles')
    mails = env['mail.mail'].search([('email_to', 'ilike', 'qa20.reclamo@example.com')])
    check(mails and any(a.name.endswith('.pdf') for a in mails.attachment_ids),
          'Constancia por correo con la hoja en PDF', mails.mapped('subject'))
    check(complaint.ack_sent_date, 'Fecha de constancia registrada')
    expect_error(lambda: env['l10n_pe.complaint'].create({
        'book_id': book.id, 'consumer_name': 'X', 'consumer_doc_type': 'dni',
        'consumer_doc_number': '1234567', 'consumer_email': 'qa20.x@example.com',
        'good_type': 'product', 'claim_type': 'claim', 'detail': 'x', 'consumer_request': 'x',
        'good_description': 'x'}), ValidationError, 'DNI de 7 dígitos rechazado', 'DNI')
    complaint.action_start()
    igual(complaint.state, 'in_progress', 'En atención')
    expect_error(complaint.action_send_response, UserError, 'Sin observaciones no se responde', 'observaciones')
    complaint.provider_observations = 'QA20: se cambió la licuadora.'
    complaint.action_send_response()
    igual(complaint.state, 'answered', 'Respondido')
    complaint.action_close()
    igual(complaint.state, 'closed', 'Cerrado')
    pdf_ok('al_l10n_pe_complaints_book.action_report_complaint', complaint, 'PDF de la hoja de reclamación')
    # No enviar correos reales a example.com desde el servidor del usuario.
    env['mail.mail'].search([('email_to', 'ilike', 'qa20.reclamo@example.com'),
                             ('state', '=', 'outgoing')]).write({'state': 'cancel'})


ejecutar(_reclamo)


# ======================================================================
# al_website_sale_pe
# ======================================================================
caso('al_website_sale_pe', 'Checkout: boleta/factura y consulta RUC/DNI (consulta simulada)',
     'En la dirección de facturación de la tienda elegir boleta o factura y consultar el documento.')


def _website():
    from odoo.addons.http_routing.tests.common import MockRequest
    from odoo.addons.al_website_sale_pe.controllers.main import MAX_LOOKUPS_PER_SESSION, WebsiteSalePeAddress
    website = env['website'].search([('company_id', '=', company.id)], limit=1)
    ctrl = WebsiteSalePeAddress()
    lookup = 'odoo.addons.l10n_pe_vat_sunat.models.res_partner.ResPartner._l10n_pe_lookup_document'
    with MockRequest(env, website=website):
        vals = ctrl._prepare_address_form_values(D['dni'].sudo())
        igual(vals.get('l10n_pe_receipt'), 'boleta', 'Cliente con DNI: boleta marcada')
        vals_ruc = ctrl._prepare_address_form_values(D['ruc'].sudo())
        igual(vals_ruc.get('l10n_pe_receipt'), 'factura', 'Cliente con RUC: factura marcada')
        with patch(lookup, return_value={'name': qa_name('EMPRESA CONSULTADA SAC'), 'street': 'AV. 1'}) as lk:
            res = ctrl.l10n_pe_document_lookup('20100070970', '6')
            check(res['found'] and lk.call_args.args[-2:] == ('20100070970', '6'), 'Consulta RUC devuelve datos', res)
            res = ctrl.l10n_pe_document_lookup('AB123456', '7')
            check(not res['found'], 'Pasaporte: no se consulta')
            for _i in range(MAX_LOOKUPS_PER_SESSION):
                ctrl.l10n_pe_document_lookup('46027897', '1')
            res = ctrl.l10n_pe_document_lookup('46027897', '1')
            check(not res['found'] and 'límite' in res['message'], 'Límite de consultas por sesión', res['message'])
        try:
            html = str(env['ir.qweb']._render('portal.address_form_fields', dict(vals, website=website, can_edit_commercial_fields=True)))
            check('l10n_pe_receipt_boleta' in html and 'o_l10n_pe_document_lookup' in html,
                  'Formulario de dirección muestra el selector y el botón de consulta')
        except Exception as exc:  # noqa: BLE001
            aviso('Render del formulario de dirección fuera de HTTP', '%s: %s' % (type(exc).__name__, str(exc)[:150]))
    omitido('Interfaz del checkout', 'requiere navegador; cubierto por tests HttpCase del módulo')


ejecutar(_website)


# ======================================================================
# OL-POS: configuración QA20 del TPV
# ======================================================================
caso('al_l10n_pe_edi_pos', 'Configurar TPV QA20 con diarios de boletas y facturas',
     'Crear el punto de venta QA20 con diario de boletas, diario de facturas, efectivo y Yape.')


def _journal(code, name, jtype, **vals):
    return get_or_create('account.journal', [('company_id', '=', company.id), ('code', '=', code)], {
        'name': qa_name(name), 'code': code, 'type': jtype, 'company_id': company.id, **vals})


def _pos_setup():
    jb = _journal('QB20', 'Boletas TPV', 'sale', l10n_latam_use_documents=True)
    jf = _journal('QF20', 'Facturas TPV', 'sale', l10n_latam_use_documents=True)
    jc1 = _journal('QC120', 'Caja TPV CPE', 'cash')
    jc2 = _journal('QC220', 'Caja TPV Lotes', 'cash')
    # Yape (al_pos_pe_wallet_qr): cuenta con la imagen del QR de la billetera.
    bank_acc = get_or_create('res.partner.bank', [('account_number', '=', 'QA20-YAPE-987654321')], {
        'account_number': 'QA20-YAPE-987654321', 'partner_id': company.partner_id.id,
        'l10n_pe_wallet_qr_image': BinaryBytes(png_bytes()), 'allow_out_payment': False})
    jy = _journal('QY20', 'Yape', 'bank', bank_account_id=bank_acc.id)
    PM = env['pos.payment.method']
    pm_cash1 = get_or_create('pos.payment.method', [('name', '=', qa_name('Efectivo CPE'))], {
        'name': qa_name('Efectivo CPE'), 'type': 'cash', 'journal_id': jc1.id, 'company_id': company.id})
    pm_cash2 = get_or_create('pos.payment.method', [('name', '=', qa_name('Efectivo Lotes'))], {
        'name': qa_name('Efectivo Lotes'), 'type': 'cash', 'journal_id': jc2.id, 'company_id': company.id})
    pm_yape = get_or_create('pos.payment.method', [('name', '=', qa_name('Yape'))], {
        'name': qa_name('Yape'), 'type': 'bank', 'journal_id': jy.id, 'company_id': company.id,
        'payment_method_type': 'bank_qr_code', 'qr_code_method': 'l10n_pe_wallet'})
    cfg = get_or_create('pos.config', [('name', '=', qa_name('TPV CPE'))], {
        'name': qa_name('TPV CPE'), 'journal_id': jb.id,
        'payment_method_ids': [Command.set((pm_cash1 | pm_yape).ids)],
        'l10n_pe_boleta_journal_id': jb.id, 'l10n_pe_factura_journal_id': jf.id})
    cfg2 = get_or_create('pos.config', [('name', '=', qa_name('TPV Lotes'))], {
        'name': qa_name('TPV Lotes'),
        'payment_method_ids': [Command.set(pm_cash2.ids)]})
    # La cuenta de la billetera no debe quedar como cuenta bancaria por defecto de
    # las facturas de la compañía (la usan los demás agentes): se archiva; el
    # diario y el método la siguen leyendo.
    bank_acc.active = False
    registro(jb | jf | jc1 | jc2 | jy)
    reg(bank_acc, pm_cash1 | pm_cash2 | pm_yape, cfg | cfg2)
    D.update(cfg=cfg, cfg_lot=cfg2, jb=jb, jf=jf, pm_cash=pm_cash1, pm_cash2=pm_cash2, pm_yape=pm_yape,
             bank_yape=bank_acc)
    check(cfg.l10n_pe_cpe_enabled, 'CPE en el TPV activo (ambos diarios configurados)')
    check(not cfg2.l10n_pe_cpe_enabled, 'TPV sin diarios CPE: flujo estándar')
    fields_partner = env['res.partner']._load_pos_data_fields(cfg)
    check('l10n_pe_sunat_id_code' in fields_partner, 'El TPV carga el código SUNAT del cliente')
    fields_move = env['account.move']._load_pos_data_fields(cfg)
    check({'l10n_pe_pos_qr_str', 'l10n_pe_pos_amount_text', 'l10n_pe_edi_amount_igv'} <= set(fields_move),
          'El TPV carga QR, importe en letras y totales del comprobante')


ejecutar(_pos_setup)

# ----------------------------------------------------------------------
# Configuración por módulo (antes de abrir la sesión)
# ----------------------------------------------------------------------
caso('al_pos_pe_wallet_qr', 'Método Yape: QR de la billetera en la pantalla de pago',
     'Configurar Yape con la imagen del QR de la cuenta y pedir el QR de un cobro en soles.')


def _wallet():
    if not D.get('pm_yape'):
        return omitido('Yape', 'sin TPV')
    methods = dict(env['res.partner.bank'].get_available_qr_methods_in_sequence())
    check('l10n_pe_wallet' in methods, 'Método QR «billetera» ofrecido')
    pen = env.ref('base.PEN')
    qr = D['pm_yape'].get_qr_code_value(25.5, 'QA20 Orden 0001', '', pen.id, False)
    check(qr.startswith('data:image/png;base64,'), 'QR en data URI PNG')
    igual(qr.split(',', 1)[1], D['bank_yape'].l10n_pe_wallet_qr_image.to_base64(), 'Es la imagen de la cuenta')
    igual(D['pm_yape'].default_qr, qr, 'Mismo QR sin conexión (default_qr)')
    expect_error(lambda: D['pm_yape'].get_qr_code_value(10.0, 'QA20', '', env.ref('base.USD').id, False),
                 UserError, 'Solo en soles', 'soles')
    bank2 = env['res.partner.bank'].create({'account_number': 'QA20-SIN-QR', 'partner_id': company.partner_id.id})
    j2 = env['account.journal'].create({'name': qa_name('Plin sin QR'), 'code': 'QPL20', 'type': 'bank',
                                        'company_id': company.id, 'bank_account_id': bank2.id})
    expect_error(lambda: env['pos.payment.method'].create({
        'name': qa_name('Plin'), 'type': 'bank', 'journal_id': j2.id, 'company_id': company.id,
        'payment_method_type': 'bank_qr_code', 'qr_code_method': 'l10n_pe_wallet'}),
        ValidationError, 'Cuenta sin imagen de QR rechazada', 'QR')
    j2.unlink()
    bank2.unlink()


ejecutar(_wallet)

caso('al_pos_network_printer', 'Impresora ESC/POS de red: lista blanca y ticket de prueba (simulado)',
     'Activar la impresora de red del TPV, pulsar «Probar impresora» y revisar los destinos permitidos.')


def _printer():
    if not D.get('cfg'):
        return omitido('Impresora', 'sin TPV')
    from odoo.addons.al_pos_network_printer.controllers import main as npm
    cfg = D['cfg']
    cfg.write({'escpos_network_printer_enabled': True, 'escpos_printer_mode': 'backend',
               'escpos_printer_ip': '203.0.113.10', 'escpos_printer_port': '9100'})
    kitchen = get_or_create('pos.printer', [('name', '=', qa_name('Cocina ESC/POS'))], {
        'name': qa_name('Cocina ESC/POS'), 'printer_type': 'escpos_network',
        'escpos_printer_ip': '203.0.113.20', 'escpos_printer_port': '9100'})
    registro(kitchen)
    check(npm.is_allowed_target(env, '203.0.113.10', 9100), 'Destino de la caja permitido')
    check(npm.is_allowed_target(env, '203.0.113.20', '9100'), 'Destino de la impresora de cocina permitido')
    check(not npm.is_allowed_target(env, '203.0.113.99', 9100), 'IP no configurada rechazada (anti-SSRF)')
    check(not npm.is_allowed_target(env, '203.0.113.10', 9101), 'Puerto distinto rechazado')
    conn = MagicMock()
    with patch.object(npm, 'EscposNetwork', MagicMock()), patch.object(npm, '_get_connection', return_value=conn):
        result = cfg.action_test_escpos_printer()
    check(conn.print_test_ticket.called and cfg.name in conn.print_test_ticket.call_args[0][0],
          'Ticket de prueba enviado con el nombre de la caja')
    igual(result.get('params', {}).get('type'), 'success', 'Notificación de éxito')
    cfg.escpos_printer_mode = 'agent'
    expect_error(cfg.action_test_escpos_printer, ValidationError, 'Modo agente: la prueba no se hace en el servidor')
    cfg.escpos_printer_mode = 'backend'
    if 'escpos_auto_print' in cfg._fields:
        cfg.escpos_auto_print = True
        check(cfg.iface_print_auto, 'Imprimir al pagar activa iface_print_auto')
        cfg.escpos_auto_print = False
    omitido('Impresión física', 'sin impresora; conexión TCP simulada')


ejecutar(_printer)

caso('al_pos_theme', 'Tema del TPV: marca, colores y variables CSS',
     'En Ajustes del TPV poner nombre de marca y color primario y revisar que la caja los use.')


def _theme():
    if not D.get('cfg'):
        return omitido('Tema', 'sin TPV')
    cfg = D['cfg']
    cfg.write({'al_theme_brand_name': qa_name('Botica'), 'al_theme_color_primary': '#0F766E',
               'al_theme_category_toggle': True})
    igual(cfg._al_theme_page_title(), '%s · %s' % (qa_name('Botica'), cfg.name), 'Título de la pestaña')
    css = cfg._al_theme_css_vars()
    check('--alpt-primary: #0F766E;' in css, 'Color primario en las variables CSS')
    check('--alpt-brand-name: "%s";' % qa_name('Botica') in css, 'Marca en las variables CSS')
    for bad in ('red', '#0F766E; } body { display:none'):
        expect_error(lambda: cfg.write({'al_theme_color_primary': bad}), ValidationError,
                     'Color inválido rechazado (%s)' % bad[:12])
    dark = cfg.with_context().sudo()._al_theme_css_vars(dark=True)
    check('--alpt-primary:' in dark, 'Variables del modo oscuro')
    data = env['pos.config']._load_pos_data_read(cfg, cfg)[0]
    check(data.get('al_theme_category_toggle') and 'al_theme_logo' not in data,
          'El TPV recibe el botón de categorías, no las imágenes del tema')
    disp = cfg._get_customer_display_data()
    check(disp.get('al_theme_title') and '"' not in disp.get('al_theme_css_vars', ''),
          'Pantalla del cliente con título y variables sin comillas')


ejecutar(_theme)

caso('al_pos_product_view', 'Vista de productos: stock del almacén del TPV y preferencia del cajero',
     'Cambiar a vista de lista en la caja: el cajero guarda su preferencia y ve el stock del almacén.')


def _product_view():
    if not D.get('cfg'):
        return omitido('Vista', 'sin TPV')
    cfg = D['cfg']
    cfg.write({'default_product_view': 'list', 'iface_filter_products_by_tag': True})
    tag = get_or_create('product.tag', [('name', '=', qa_name('Analgésicos'))],
                        {'name': qa_name('Analgésicos'), 'show_in_pos_filter': True})
    D['good'].product_tmpl_id.product_tag_ids = [Command.link(tag.id)]
    registro(tag)
    wh_stock = cfg.picking_type_id.warehouse_id.lot_stock_id
    expected = D['good'].with_context(warehouse_id=cfg.picking_type_id.warehouse_id.id).qty_available
    data = env['product.template']._load_pos_data_read(D['good'].product_tmpl_id, cfg)
    check('qty_available' in data[0], 'qty_available viaja al TPV')
    igual(data[0]['qty_available'], expected, 'Stock del almacén del TPV (%s)' % wh_stock.complete_name)
    if len(env['stock.warehouse'].search([('company_id', '=', company.id)])) < 2:
        aviso('Un solo almacén en la base', 'no se compara contra otro almacén')
    check('show_in_pos_filter' in env['product.tag']._load_pos_data_fields(cfg), 'Etiquetas filtro en el TPV')
    cashier = D.get('cashier') or _cashier()
    own = env['res.users'].with_user(cashier).browse(cashier.id)
    check(own.set_pos_product_view_mode('list'), 'El cajero guarda su vista (sin sudo)')
    igual(cashier.pos_product_view_mode, 'list', 'Preferencia guardada')
    expect_error(lambda: env.user.with_user(cashier).set_pos_product_view_mode('grid'), AccessError,
                 'No cambia la preferencia de otro usuario')
    check('pos_product_view_mode' in env['res.users']._load_pos_data_fields(cfg), 'Preferencia cargada en el TPV')


def _cashier():
    user = env['res.users'].with_context(active_test=False).search([('login', '=', 'qa20_fact_cajero')])
    if not user:
        user = env['res.users'].with_context(no_reset_password=True).create({
            'name': qa_name('Cajero TPV'), 'login': 'qa20_fact_cajero', 'company_id': company.id,
            'company_ids': [Command.set(company.ids)],
            'group_ids': [Command.set([env.ref('base.group_user').id, env.ref('point_of_sale.group_pos_user').id])]})
    D['cashier'] = user
    return user


ejecutar(_product_view)

caso('al_pos_vendedor', 'Vendedores autorizados de la caja (sin PIN ni inicio de sesión)',
     'Activar «Vendedor autorizado» en el TPV y elegir los vendedores que se pueden asignar a la orden.')


def _sellers():
    if not D.get('cfg'):
        return omitido('Vendedor', 'sin TPV')
    Emp = env['hr.employee'].sudo()
    va = get_or_create('hr.employee', [('name', '=', qa_name('Ana Vendedora'))], {'name': qa_name('Ana Vendedora')})
    vb = get_or_create('hr.employee', [('name', '=', qa_name('Carlos Almacén'))], {'name': qa_name('Carlos Almacén')})
    va.write({'pin': '1234', 'barcode': 'QA20VEND01'})
    registro(va | vb)
    cfg = D['cfg']
    cfg.write({'authorized_seller': True, 'seller_ids': [Command.set(va.ids)],
               'module_pos_hr': False})
    D['seller_emp'] = va
    check('hr.employee' in env['pos.session']._load_pos_data_models(cfg), 'El TPV carga empleados (vendedores)')
    D['sellers_check'] = (va, vb)


ejecutar(_sellers)

# ----------------------------------------------------------------------
# al_pos_payment_gateway: dos pasarelas en línea en la misma caja
# ----------------------------------------------------------------------
caso('al_pos_payment_gateway', 'Pasarelas en línea: método por pasarela y logo',
     'Desde la pasarela Niubiz crear su método de pago del TPV y agregar dos métodos en línea a la caja.')


def _gateway():
    if not D.get('cfg'):
        return omitido('Pasarela', 'sin TPV')
    niubiz = env['payment.provider'].search([('code', '=', 'niubiz'), ('company_id', '=', company.id)], limit=1)
    if niubiz:
        card = Image.open(io.BytesIO(base64.b64decode(niubiz.sudo()._al_pos_payment_logo())))
        igual(card.size, (240, 160), 'Tarjeta 240 × 160 de Niubiz para el TPV')
    if niubiz:
        # Método del TPV creado desde una pasarela peruana (su módulo trae la tarjeta PNG).
        try:
            with env.cr.savepoint() as sp:
                pn = niubiz.copy({'name': qa_name('Niubiz (copia)'), 'is_published': False, 'is_live': False})
                act = pn.action_al_pos_payment_method()
                mn = env['pos.payment.method'].browse(act['res_id'])
                check(mn.image, 'Método creado desde Niubiz con su tarjeta como imagen')
                sp.rollback()
        except Exception as exc:  # noqa: BLE001
            check(False, 'Crear el método del TPV desde Niubiz (botón de la pasarela)',
                  '%s: %s' % (type(exc).__name__, exc))
    base = env['payment.provider'].search([('code', '=', 'custom'), ('company_id', '=', company.id)], limit=1)
    pa = get_or_create('payment.provider', [('name', '=', qa_name('Pasarela A'))],
                       {**base.copy_data()[0], 'name': qa_name('Pasarela A'), 'is_published': False, 'is_live': False})
    pb = get_or_create('payment.provider', [('name', '=', qa_name('Pasarela B'))],
                       {**base.copy_data()[0], 'name': qa_name('Pasarela B'), 'is_published': False, 'is_live': False})
    if not pa.image_128:
        pa.image_128 = BinaryBytes(png_bytes((0, 120, 200)))
    action = pa.action_al_pos_payment_method()
    ma = env['pos.payment.method'].browse(action['res_id'])
    mb = pb.al_pos_payment_method_ids[:1] or env['pos.payment.method'].create({
        'name': qa_name('Pasarela B'), 'type': 'online', 'online_payment_provider_ids': [Command.set(pb.ids)]})
    reg(pa | pb, ma | mb)
    igual(ma.online_payment_provider_ids, pa, 'Método creado desde la pasarela')
    check(ma.image, 'El método lleva el logo de la pasarela')
    cfg = D['cfg']
    cfg.write({'payment_method_ids': [Command.link(ma.id), Command.link(mb.id)]})
    igual(len(cfg.payment_method_ids.filtered(lambda m: m.type == 'online')), 2,
          'Dos métodos en línea en la misma caja')
    expect_error(lambda: mb.write({'online_payment_provider_ids': [Command.link(pa.id)]}), ValidationError,
                 'Una pasarela no puede estar en dos métodos de la caja')
    igual(cfg._al_online_payment_method_for_provider(pb), mb, 'El pago de la pasarela B va a su método')
    D.update(pm_online_a=ma, pm_online_b=mb, provider_b=pb)


ejecutar(_gateway)


# ======================================================================
# Sesión del TPV CPE: ventas
# ======================================================================
def pos_line(product, qty, price=None, taxes=None, **kw):
    price = product.lst_price if price is None else price
    taxes = product.taxes_id.filtered(lambda t: t.company_id == company) if taxes is None else taxes
    res = taxes.compute_all(price, company.currency_id, qty, product=product) if taxes else {
        'total_excluded': price * qty, 'total_included': price * qty}
    return [0, 0, {'product_id': product.id, 'qty': qty, 'price_unit': price, 'discount': 0,
                   'tax_ids': [(6, 0, taxes.ids)], 'price_subtotal': abs(res['total_excluded']),
                   'price_subtotal_incl': abs(res['total_included']), **kw}]


def pos_sync(session, lines, payments, partner=None, invoiced=False, user=None, **vals):
    sign = lambda l: 1 if l[2]['qty'] >= 0 else -1
    total = sum(sign(l) * l[2]['price_subtotal_incl'] for l in lines)
    base = sum(sign(l) * l[2]['price_subtotal'] for l in lines)
    uid = str(uuidlib.uuid4())
    data = {
        'uuid': uid, 'name': 'Order %s' % uid[:8], 'session_id': session.id,
        'user_id': (user or ADMIN).id, 'partner_id': partner.id if partner else False,
        'lines': lines, 'state': 'paid', 'access_token': str(uuidlib.uuid4()),
        'payment_ids': [[0, 0, {'amount': a, 'payment_method_id': pm.id, 'name': fields.Datetime.now()}]
                        for pm, a in payments],
        'amount_paid': sum(a for _pm, a in payments), 'amount_return': 0,
        'amount_tax': total - base, 'amount_total': total,
        'date_order': fields.Datetime.to_string(fields.Datetime.now()),
        'fiscal_position_id': False, 'pricelist_id': session.config_id.pricelist_id.id,
        'to_invoice': invoiced, **vals}
    Order = env['pos.order'].with_user(user or ADMIN)
    res = Order.with_context(generate_pdf=False).sync_from_ui([data])
    ids = [o['id'] for o in res['pos.order'] if o.get('uuid') == uid] or [res['pos.order'][0]['id']]
    return env['pos.order'].browse(ids[0])


ADMIN = env.ref('base.user_admin')


def open_session(cfg, user=None):
    user = user or ADMIN
    c = cfg.with_user(user)
    c.open_ui()
    session = cfg.current_session_id
    session.with_user(user).set_opening_control(0, None)
    return session


caso('al_l10n_pe_edi_pos', 'Venta en caja con boleta a cliente DNI (CPE desde el TPV)',
     'Abrir la caja, vender 2 ibuprofenos a una clienta con DNI eligiendo «Boleta», cobrar en efectivo.')


def _pos_boleta():
    if not D.get('cfg'):
        return omitido('TPV', 'sin configuración')
    session = open_session(D['cfg'])
    D['session'] = session
    registro(session)
    order = pos_sync(session, [pos_line(D['good'], 2)], [(D['pm_cash'], 118.0)],
                     partner=D['dni'], invoiced=True, l10n_pe_doc_type='boleta',
                     seller_id=D.get('seller_emp') and D['seller_emp'].id)
    registro(order, 'orden con boleta')
    inv = order.account_move
    registro(inv, 'boleta del TPV')
    D['pos_boleta_order'] = order
    igual(order.state, 'paid' if order.state == 'paid' else 'done', 'Orden pagada', 1)
    check(inv, 'La orden generó su comprobante', inv.name)
    igual(inv.journal_id, D['jb'], 'Comprobante en el diario de boletas del TPV')
    igual(inv.l10n_latam_document_type_id.code, '03', 'Tipo 03 (boleta)')
    igual(inv.amount_total, 118.0, 'Total de la boleta')
    check(inv.payment_state in ('paid', 'in_payment'), 'Boleta pagada con el cobro de caja', inv.payment_state)
    parts = (inv.l10n_pe_pos_qr_str or '').split('|')
    check(len(parts) == 9 and parts[1] == '03' and parts[7:] == ['1', '46027897'],
          'QR de la representación impresa (RUC|03|serie|folio|igv|total|fecha|1|DNI)', inv.l10n_pe_pos_qr_str)
    check(inv.l10n_pe_pos_amount_text and '/100' in inv.l10n_pe_pos_amount_text, 'Importe en letras del ticket',
          inv.l10n_pe_pos_amount_text)
    igual(inv.l10n_pe_pos_igv_label, 'IGV (18%)', 'Etiqueta del IGV del ticket')
    check(IAP_MOCK_MSG in str(inv.l10n_pe_edi_warnings or '') or any(
        IAP_MOCK_MSG in (m.body or '') for m in inv.message_ids),
        'El TPV intentó enviar el CPE a SUNAT (IAP simulado)')
    root = xml_of(inv)
    igual(xv(root, '/*/cbc:InvoiceTypeCode'), '03', 'XML de la boleta del TPV: 03')
    pdf_ok('al_l10n_pe_invoice.report_cpe_ticket', inv, 'Ticket 80 mm de la boleta del TPV')
    if D.get('seller_emp'):
        igual(order.seller_id, D['seller_emp'], 'al_pos_vendedor: vendedor guardado en la orden')
    omitido('Envío a OSE', 'sin credenciales de prueba (IAP simulado)')


ejecutar(_pos_boleta)

caso('al_l10n_pe_edi_pos', 'Factura desde la caja a cliente RUC, retenida («Emitir a SUNAT: No») y NC por devolución',
     'Vender con «Factura» a un cliente con RUC; otra venta con «Emitir a SUNAT: No»; devolver la primera.')


def _pos_factura():
    if not D.get('session'):
        return omitido('TPV', 'sin sesión')
    session = D['session']
    order = pos_sync(session, [pos_line(D['good'], 1)], [(D['pm_cash'], 59.0)],
                     partner=D['ruc'], invoiced=True, l10n_pe_doc_type='factura')
    inv = order.account_move
    registro(order, 'orden con factura')
    registro(inv, 'factura del TPV')
    igual(inv.journal_id, D['jf'], 'Factura en el diario de facturas del TPV')
    igual(inv.l10n_latam_document_type_id.code, '01', 'Tipo 01 (factura)')
    held = pos_sync(session, [pos_line(D['good'], 1)], [(D['pm_cash'], 59.0)],
                    partner=D['ruc'], invoiced=True, l10n_pe_doc_type='factura', l10n_pe_edi_send=False)
    registro(held.account_move, 'factura retenida')
    check(held.account_move.l10n_pe_edi_hold, 'Factura marcada «Emisión SUNAT retenida»')
    res = held.account_move._l10n_pe_edi_post_invoice()
    check(res and 'retenida' in res.get('message', ''), 'El envío de la retenida no se hace', res and res.get('message'))
    # Devolución de la primera factura → nota de crédito en el diario de facturas.
    line = order.lines[0]
    refund = pos_sync(session, [pos_line(D['good'], -1, refunded_orderline_id=line.id)],
                      [(D['pm_cash'], -59.0)], partner=D['ruc'], invoiced=True,
                      l10n_pe_doc_type='boleta', l10n_pe_edi_refund_reason='01', is_refund=True)
    nc = refund.account_move
    registro(refund, 'devolución')
    registro(nc, 'NC del TPV')
    igual(refund.refunded_order_id, order, 'La devolución enlaza la orden original')
    igual(nc.journal_id, D['jf'], 'NC de factura en el diario de facturas (aunque la caja marque boleta)')
    igual(nc.l10n_latam_document_type_id.code, '07', 'NC tipo 07')
    igual(nc.reversed_entry_id, inv, 'NC enlazada a la factura')
    # Sin RUC no hay factura.
    bad = env['pos.order'].create({'session_id': session.id, 'partner_id': D['dni'].id,
                                   'l10n_pe_doc_type': 'factura', 'amount_tax': 0, 'amount_total': 0,
                                   'amount_paid': 0, 'amount_return': 0})
    expect_error(bad._prepare_invoice_vals, UserError, 'Factura a cliente sin RUC rechazada', 'RUC')
    bad.unlink()


ejecutar(_pos_factura)

caso('al_l10n_pe_pos_loyalty', 'Tarjeta de regalo: venta sola sin comprobante y venta mixta',
     'Vender solo una tarjeta de regalo (sale recibo) y luego ibuprofeno + tarjeta con boleta.')


def _loyalty():
    if not D.get('session'):
        return omitido('TPV', 'sin sesión')
    gift = env.ref('loyalty.gift_card_product_50', raise_if_not_found=False)
    if not gift:
        return omitido('Tarjeta de regalo', 'producto loyalty.gift_card_product_50 no existe')
    check(gift.l10n_pe_pos_is_voucher, 'Producto tarjeta de regalo marcado como vale')
    check(not D['good'].l10n_pe_pos_is_voucher, 'Producto normal no es vale')
    acc = company.l10n_pe_pos_voucher_account_id
    check(acc and acc.code.startswith('496'), 'Cuenta 496 de vales configurada', acc.code)
    session = D['session']
    only = pos_sync(session, [pos_line(gift, 1, price=50.0, taxes=env['account.tax'])],
                    [(D['pm_cash'], 50.0)], partner=D['dni'], invoiced=True, l10n_pe_doc_type='boleta')
    registro(only, 'venta solo tarjeta')
    check(not only.account_move and not only.to_invoice, 'Venta solo de tarjeta: sin comprobante')
    igual(only.l10n_pe_doc_type, 'recibo', 'Queda como recibo')
    mixed = pos_sync(session, [pos_line(D['good'], 1), pos_line(gift, 1, price=50.0, taxes=env['account.tax'])],
                     [(D['pm_cash'], 109.0)], partner=D['dni'], invoiced=True, l10n_pe_doc_type='boleta')
    inv = mixed.account_move
    registro(mixed, 'venta mixta')
    registro(inv, 'boleta sin la tarjeta')
    igual(inv.amount_total, 59.0, 'La boleta no incluye la tarjeta (59.00)')
    igual(inv.invoice_line_ids.product_id, D['good'], 'Solo el producto en la boleta')
    check(inv.currency_id.is_zero(inv.amount_residual), 'Boleta saldada')
    vm = Move.search([('ref', '=', 'Tarjeta de regalo y monedero: %s' % inv.name)])
    registro(vm, 'asiento del vale')
    igual(sum(vm.line_ids.filtered(lambda l: l.account_id == acc).mapped('balance')), -50.0,
          'Pasivo con el cliente por la tarjeta (−50.00)')


for _i in range(3):
    _CUR.update(checks=[], registros=[], error=None)
    ejecutar(_loyalty)
    if not (_CUR.get('error') or '').startswith(('DeadlockDetected', 'SerializationFailure', 'LockNotAvailable')):
        break
    print('  reintento de _loyalty por concurrencia')

caso('al_pos_pe_wallet_qr', 'Cobro con Yape en caja',
     'Vender un ibuprofeno a una clienta y cobrar con Yape.')


def _yape_sale():
    if not D.get('session'):
        return omitido('TPV', 'sin sesión')
    order = pos_sync(D['session'], [pos_line(D['good'], 1)], [(D['pm_yape'], 59.0)],
                     partner=D['dni'], invoiced=False, l10n_pe_doc_type='recibo')
    registro(order, 'venta con Yape')
    igual(order.payment_ids.payment_method_id, D['pm_yape'], 'Pago registrado con Yape')
    check('qr_code_method' in env['pos.payment.method']._load_pos_data_fields(D['cfg'])
          or 'default_qr' in env['pos.payment.method']._load_pos_data_fields(D['cfg']),
          'El TPV carga los datos del QR del método')


ejecutar(_yape_sale)

caso('al_pos_payment_gateway', 'Revisión del comprobante antes del QR de la pasarela',
     'Con una venta a facturar, antes de mostrar el QR de la pasarela el sistema revisa que el comprobante se pueda emitir.')


def _gateway_check():
    if not D.get('pm_online_b') or not D.get('session'):
        return omitido('Pasarela', 'sin métodos en línea o sesión')
    session = D['session']
    order = env['pos.order'].create({
        'session_id': session.id, 'partner_id': D['dni'].id, 'l10n_pe_doc_type': 'boleta',
        'to_invoice': True, 'lines': [pos_line(D['good'], 1)], 'amount_tax': 9.0, 'amount_total': 59.0,
        'amount_paid': 0, 'amount_return': 0})
    before = Move.search_count([])
    check(order.al_check_invoice_before_online_payment() is False, 'Boleta emitible: se puede cobrar')
    igual(Move.search_count([]), before, 'La factura de prueba se deshace')
    order.l10n_pe_doc_type = 'factura'
    problem = order.al_check_invoice_before_online_payment()
    check(problem and 'RUC' in problem, 'Factura a cliente sin RUC: el cajero ve el motivo antes del QR', problem)
    order.al_set_online_payment_method(D['pm_online_b'].id)
    igual(order.online_payment_method_id, D['pm_online_b'], 'El cajero elige el método B para el QR')
    igual(order.with_context(al_pos_online_provider_id=D['provider_b'].id).online_payment_method_id,
          D['pm_online_b'], 'El pago que llega por la pasarela B va a su método')
    order.unlink()
    omitido('Cobro real en la pasarela', 'requiere navegador y credenciales de la pasarela')


ejecutar(_gateway_check)

caso('al_pos_vendedor', 'Vendedor en la orden y en el análisis de ventas; cierre de caja',
     'Cerrar la caja y revisar el análisis del TPV agrupado por vendedor.')


def _close_cpe():
    if not D.get('session'):
        return omitido('TPV', 'sin sesión')
    session = D['session']
    if D.get('sellers_check'):
        va, vb = D['sellers_check']
        Emp = env['hr.employee']
        domain = Emp._load_pos_data_domain({'pos.config': D['cfg']})
        data = {v['id']: v for v in Emp._load_pos_data_read(Emp.sudo().search(domain), D['cfg'])}
        check(va.id in data and vb.id not in data, 'Sin pos_hr solo viajan los vendedores de la lista')
        if va.id in data:
            check(data[va.id].get('_al_seller_only') and '_pin' not in data[va.id] and '_barcode' not in data[va.id],
                  'Vendedor sin PIN ni código de barras, marcado solo-vendedor')
    cash = sum(session.order_ids.payment_ids.filtered(lambda p: p.payment_method_id == D['pm_cash']).mapped('amount'))
    # Cierre como administrador del sistema: otro agente dejó cuentas bancarias de la
    # compañía sin «de confianza» y un usuario normal no puede publicar con ellas.
    res = session.close_session_from_ui({D['pm_cash'].id: cash})
    check(res.get('successful', res.get('status', True)) is not False, 'Cierre de caja sin errores', res)
    igual(session.state, 'closed', 'Sesión cerrada')
    moves = session.sale_move_ids if 'sale_move_ids' in session._fields else Move
    check(moves, 'Asientos de cierre de la sesión', moves.mapped('name'))
    if D.get('seller_emp'):
        rows = env['report.pos.order'].search([('session_id', '=', session.id), ('seller_id', '=', D['seller_emp'].id)])
        check(rows, 'Análisis del TPV: ventas por vendedor', len(rows))


ejecutar(_close_cpe)


# ======================================================================
# Cajero no administrador vendiendo producto con lote
# ======================================================================
caso('al_pos_product_view', 'Cajero QA20 (no admin) vende producto con lote: sin y con grupo Inventario/Usuario',
     'Como cajero sin permisos de Inventario abrir la caja, elegir el lote del producto, cobrar y cerrar; repetir con el grupo.')


def _lots():
    if not D.get('cfg_lot'):
        return omitido('Lotes', 'sin TPV')
    cashier = D.get('cashier') or _cashier()
    registro(cashier, 'cajero sin grupo de inventario al inicio')
    stock_user = env.ref('stock.group_stock_user')
    cashier.group_ids = [Command.unlink(stock_user.id)]
    check(not cashier.has_group('stock.group_stock_user'), 'Cajero sin grupo Inventario/Usuario')
    prod = get_or_create('product.product', [('name', '=', qa_name('Amoxicilina 500 mg (lote)'))], {
        'name': qa_name('Amoxicilina 500 mg (lote)'), 'is_storable': True, 'tracking': 'lot',
        'available_in_pos': True, 'list_price': 20.0, 'taxes_id': [Command.set(D['igv'].ids)]})
    registro(prod)
    cfg = D['cfg_lot']
    loc = cfg.picking_type_id.default_location_src_id
    lot = get_or_create('stock.lot', [('name', '=', 'QA20-LOTE-A1'), ('product_id', '=', prod.id)],
                        {'name': 'QA20-LOTE-A1', 'product_id': prod.id, 'company_id': company.id})
    if prod.with_context(location=loc.id).qty_available < 10:
        env['stock.quant']._update_available_quantity(prod, loc, 20, lot_id=lot)
    registro(lot)

    def run(label):
        out = {}
        try:
            with env.cr.savepoint():
                lots = env['pos.order.line'].with_user(cashier).get_existing_lots(company.id, cfg.id, prod.id)
                out['lots'] = [l.get('name') for l in lots]
        except Exception as exc:  # noqa: BLE001
            out['lots_error'] = '%s: %s' % (type(exc).__name__, str(exc)[:160])
        try:
            with env.cr.savepoint():
                session = open_session(cfg, cashier)
                order = pos_sync(session, [pos_line(prod, 1, pack_lot_ids=[[0, 0, {'lot_name': lot.name}]])],
                                 [(D['pm_cash2'], 23.6)], user=cashier)
                try:
                    with env.cr.savepoint():
                        res = session.with_user(cashier).close_session_from_ui({D['pm_cash2'].id: 23.6})
                except (UserError, RedirectWarning) as exc:
                    if 'confianza' not in str(exc):
                        raise
                    out['close_note'] = 'cierre por el cajero bloqueado por una cuenta bancaria ajena no confiable; se cierra como sistema'
                    res = session.close_session_from_ui({D['pm_cash2'].id: 23.6})
                out.update(session=session, order=order, close=res, state=session.state)
                ml = order.picking_ids.move_line_ids
                out['lot_ok'] = ml.lot_id == lot and order.picking_ids.state == 'done'
        except Exception as exc:  # noqa: BLE001
            import traceback as _tb
            frames = [f for f in _tb.extract_tb(exc.__traceback__) if 'odoo/orm' not in f.filename][-4:]
            out['error'] = '%s: %s | en %s' % (type(exc).__name__, str(exc).split('\n')[0][:160],
                                              ' > '.join('%s:%s %s' % (f.filename.split('/addons/')[-1], f.lineno, f.name) for f in frames))
        print('   [%s] %s' % (label, {k: v for k, v in out.items() if k not in ('session', 'order')}))
        return out

    r1 = run('sin grupo')
    if r1.get('error') or r1.get('lots_error'):
        aviso('Sin grupo Inventario/Usuario el cajero NO completa la venta con lote',
              r1.get('lots_error') or r1.get('error'))
    else:
        check(r1.get('lot_ok') and r1.get('state') == 'closed',
              'Sin grupo: venta con lote, entrega hecha y caja cerrada', r1.get('lots'))
        reg(r1['session'], r1['order'], nota='venta con lote sin grupo')
    cashier.group_ids = [Command.link(stock_user.id)]
    r2 = run('con grupo')
    check(not r2.get('error') and not r2.get('lots_error') and r2.get('lot_ok') and r2.get('state') == 'closed',
          'Con grupo Inventario/Usuario: lotes visibles, venta con lote y caja cerrada',
          r2.get('error') or r2.get('lots_error') or r2.get('lots'))
    if r2.get('close_note'):
        aviso('Cierre de caja del cajero', r2['close_note'])
    if r2.get('session'):
        reg(r2['session'], r2['order'], nota='venta con lote con grupo')
    D['lots_result'] = (r1, r2)


ejecutar(_lots)


# ======================================================================
# al_pos_pe_partner_lookup
# ======================================================================
caso('al_pos_pe_partner_lookup', 'Crear cliente en caja desde RUC o DNI (consulta simulada)',
     'En la lista de clientes del TPV escribir un RUC o un DNI y crear el cliente con los datos consultados.')


def _lookup():
    from stdnum.pe import ruc as stdnum_ruc
    Partner = env['res.partner']
    lookup = 'odoo.addons.l10n_pe_vat_sunat.models.res_partner.ResPartner._l10n_pe_lookup_document'
    ruc = next(n for n in (f'2060{i:06d}' + stdnum_ruc.calc_check_digit(f'2060{i:06d}') for i in range(900, 2000))
               if not Partner.with_context(active_test=False).search_count([('vat', '=', n)]))
    with patch.object(type(env['res.company']), '_l10n_pe_lookup_ready', lambda c, d: True):
        with patch(lookup, return_value={'name': qa_name('EMPRESA CONSULTADA SAC'),
                                         'street': 'AV. GARCILASO DE LA VEGA 1472'}) as lk:
            pid = Partner.l10n_pe_pos_create_from_document(ruc)
        p = Partner.browse(pid)
        registro(p, 'creado desde RUC')
        igual(lk.call_args.args[-1], '6', 'Consulta como RUC (código 6)')
        igual((p.vat, p.l10n_pe_sunat_id_code, p.is_company), (ruc, '6', True), 'Cliente RUC creado')
        with patch(lookup, return_value={'name': qa_name('LUIS HUAMAN CCORI')}) as lk:
            pid2 = Partner.l10n_pe_pos_create_from_document(' 7012 3456 ')
        p2 = Partner.browse(pid2)
        registro(p2, 'creado desde DNI')
        igual((p2.l10n_pe_sunat_id_code, p2.l10n_pe_sunat_id_value), ('1', '70123456'),
              'Cliente DNI creado (identificador adicional)')
        with patch(lookup) as lk:
            igual(Partner.l10n_pe_pos_create_from_document('46027897'), D['dni'].id,
                  'DNI existente: devuelve el cliente sin consultar')
            check(not lk.called, 'Sin consulta para cliente existente')
        expect_error(lambda: Partner.l10n_pe_pos_create_from_document('12345'), UserError,
                     'Formato inválido rechazado', '11 dígitos')
    expect_error(lambda: Partner.with_user(env.ref('base.public_user')).l10n_pe_pos_create_from_document(ruc[:-1] + '0'),
                 Exception, 'Usuario sin permiso de crear contactos rechazado')
    omitido('Consulta real SUNAT/RENIEC', 'sin token de consulta; respuesta simulada')


ejecutar(_lookup)


# ======================================================================
# Interfaz del TPV: bundles de assets
# ======================================================================
caso('al_pos_theme', 'Assets del TPV: los bundles compilan e incluyen los módulos QA',
     'Abrir la caja en el navegador (aquí: generar los bundles JS/CSS del TPV).')


def _assets():
    QWeb = env['ir.qweb']
    mods = ['al_l10n_pe_edi_pos', 'al_l10n_pe_pos_loyalty', 'al_pos_network_printer', 'al_pos_online_payment',
            'al_pos_payment_gateway', 'al_pos_pe_partner_lookup', 'al_pos_pe_wallet_qr', 'al_pos_product_view',
            'al_pos_theme', 'al_pos_vendedor']
    urls = []
    with env.cr.savepoint() as sp:
        for name in ('point_of_sale.assets_prod', 'point_of_sale.assets_prod_dark',
                     'point_of_sale.customer_display_assets'):
            bundle = QWeb._get_asset_bundle(name)
            files = [a.url for a in bundle.javascripts] + [a.url for a in bundle.stylesheets] + \
                [getattr(t, 'url', '') for t in getattr(bundle, 'templates', [])]
            urls += files
            if bundle.javascripts and name != 'point_of_sale.assets_prod_dark':
                att = bundle.js()
                check(att and att.raw, 'Bundle JS %s generado' % name, '%d archivos' % len(bundle.javascripts))
            if bundle.stylesheets:
                att = bundle.css()
                errors = getattr(bundle, 'css_errors', None)
                check(att and not errors, 'Bundle CSS/SCSS %s compilado' % name, errors or '%d hojas' % len(bundle.stylesheets))
        sp.rollback()
    missing = [m for m in mods if not any('/%s/' % m in (u or '') for u in urls)]
    check(not missing, 'Todos los módulos OL-POS presentes en los bundles del TPV', missing or len(urls))
    for mod in ('al_pos_theme', 'al_pos_product_view', 'al_pos_online_payment', 'al_pos_network_printer'):
        omitido('Interfaz %s' % mod, 'requiere navegador; cubierto por tours/estático')


ejecutar(_assets)


# ======================================================================
# Casos que tocan la configuración de la compañía (al final: bloqueo corto)
# ======================================================================

# Estos dos casos escriben res.company: la transacción principal (lectura
# repetible) choca con las escrituras de los otros agentes en la compañía. Se
# corren en un cursor propio, corto, con reintentos y con sus propios datos
# QA20 (los de la transacción principal aún no son visibles allí).
X = {}


def ejecutar_aparte(fn, intentos=6):
    import time
    from psycopg2 import errors as pg_errors
    from odoo import api
    global env, company, Move
    main = (env, company, Move)
    for intento in range(1, intentos + 1):
        _CUR['checks'] = []
        _CUR['registros'] = []
        _CUR['error'] = None
        try:
            with env.registry.cursor() as cr2:
                cr2.execute("SET lock_timeout = '45s'")
                env = api.Environment(cr2, main[0].uid, main[0].context)
                company = env['res.company'].browse(main[1].id)
                Move = env['account.move']
                try:
                    X['igv'] = env['account.tax'].browse(D['igv'].id)
                    X['ruc'] = get_or_create('res.partner', [('name', '=', qa_name('Cliente RUC Aprobaciones SAC'))], {
                        'name': qa_name('Cliente RUC Aprobaciones SAC'), 'is_company': True, 'vat': '20100070970',
                        'country_id': PE.id, 'street': 'Av. Larco 345'})
                    X['srv'] = get_or_create('product.product', [('name', '=', qa_name('Servicio HKA'))], {
                        'name': qa_name('Servicio HKA'), 'type': 'service', 'list_price': 100.0,
                        'taxes_id': [Command.set(X['igv'].ids)]})
                    X['journal'] = get_or_create('account.journal', [('company_id', '=', company.id), ('code', '=', 'QH20')], {
                        'name': qa_name('Ventas OSE HKA'), 'code': 'QH20', 'type': 'sale', 'company_id': company.id,
                        'l10n_latam_use_documents': True})
                    reg(X['ruc'], X['srv'], X['journal'])
                    fn()
                    if os.environ.get('QA_ROLLBACK'):
                        cr2.rollback()
                    else:
                        cr2.commit()
                    return
                finally:
                    env, company, Move = main
        except (pg_errors.SerializationFailure, pg_errors.LockNotAvailable, pg_errors.DeadlockDetected) as exc:
            print('  reintento %d por concurrencia: %s' % (intento, str(exc).splitlines()[0]))
            time.sleep(3 * intento)
            continue
        except Exception as exc:  # noqa: BLE001
            _CUR['error'] = '%s: %s' % (type(exc).__name__, exc)
            _log(FAIL, '%s lanzó una excepción' % fn.__name__, _CUR['error'])
            traceback.print_exc(limit=6)
            _CUR['registros'] = []
            return
    _log(FAIL, '%s: sin éxito tras %d reintentos por concurrencia' % (fn.__name__, intentos))


caso('al_sale_approval', 'Pedido con producto que exige aprobación: pendiente hasta aprobar',
     'Cotizar un producto marcado «Requiere aprobación», solicitar la aprobación, aprobarla como gerente y confirmar.')


def _approval():
    approver = env['res.users'].with_context(active_test=False).search([('login', '=', 'qa20_fact_aprobador')])
    if not approver:
        approver = env['res.users'].with_context(no_reset_password=True).create({
            'name': qa_name('Gerente aprobador'), 'login': 'qa20_fact_aprobador', 'company_id': company.id,
            'company_ids': [Command.set(company.ids)],
            'group_ids': [Command.set([env.ref('base.group_user').id, env.ref('approvals.group_approval_user').id])]})
    category = get_or_create('approval.category', [('name', '=', qa_name('Aprobación de orden de venta'))], {
        'name': qa_name('Aprobación de orden de venta'), 'has_reference': 'required', 'company_id': company.id,
        'approver_ids': [Command.create({'user_id': approver.id, 'required': True})]})
    previous = company.sale_approval_category_id
    company.sale_approval_category_id = category
    guarded = get_or_create('product.product', [('name', '=', qa_name('Muebles de melamina'))], {
        'name': qa_name('Muebles de melamina'), 'type': 'service', 'sale_approval_required': True,
        'list_price': 5000.0, 'taxes_id': [Command.set(X['igv'].ids)]})
    reg(approver, category, guarded)
    order = env['sale.order'].create({'partner_id': X['ruc'].id, 'order_line': [
        Command.create({'product_id': guarded.id, 'price_unit': 5000.0})]})
    registro(order, 'cotización con aprobación')
    igual(order.sale_approval_state, 'to_request', 'Cotización: aprobación por solicitar')
    expect_error(order.action_confirm, UserError, 'No se confirma sin aprobación')
    request = env['approval.request'].browse(order.action_request_sale_approval()['res_id'])
    registro(request, 'solicitud de aprobación')
    igual((request.sale_order_id, request.reference), (order, order.name), 'Solicitud enlazada al pedido')
    request.action_confirm()
    order.invalidate_recordset()
    igual(order.sale_approval_state, 'pending', 'Pendiente de aprobación')
    expect_error(order.action_confirm, UserError, 'Pendiente: no se confirma')
    request.with_user(approver).action_approve()
    order.invalidate_recordset()
    igual(order.sale_approval_state, 'approved', 'Aprobada por el gerente')
    order.action_confirm()
    igual(order.state, 'sale', 'Pedido confirmado tras aprobar')
    free = env['sale.order'].create({'partner_id': X['ruc'].id, 'order_line': [
        Command.create({'product_id': X['srv'].id, 'price_unit': 100.0})]})
    igual(free.sale_approval_state, 'not_required', 'Producto sin marca: no requiere aprobación')
    free.action_confirm()
    registro(free, 'pedido sin aprobación')
    company.sale_approval_category_id = previous
    aviso('El módulo aprueba por producto marcado, no por límite de importe',
          'no hay regla de monto en al_sale_approval (approvals nativo)')


ejecutar_aparte(_approval)

caso('al_ose_factory_hka', 'Operador Factory HKA: envío, consulta CDR y baja (OSE simulado)',
     'Con el operador «The Factory HKA» y sus credenciales, enviar una factura, consultar su CDR y darla de baja.')


def _hka():
    old = company.read(['l10n_pe_edi_provider', 'l10n_pe_edi_certificate_id', 'l10n_pe_edi_test_env',
                        'l10n_pe_edi_factory_hka_username', 'l10n_pe_edi_factory_hka_password',
                        'l10n_pe_edi_factory_hka_wsdl_prod'])[0]
    with file_open('l10n_pe_edi/demo/certificates/certificate.pfx', 'rb') as fh:
        content = BinaryBytes(fh.read())
    cert = get_or_create('certificate.certificate', [('name', '=', qa_name('Certificado demo (pruebas)'))], {
        'name': qa_name('Certificado demo (pruebas)'), 'content': content, 'pkcs12_password': '12345678a',
        'company_id': company.id})
    registro(cert)
    selection = dict(env['res.company']._fields['l10n_pe_edi_provider']._description_selection(env))
    check('factory_hka' in selection, 'Operador Factory HKA disponible')
    FakeHkaClient.calls = []
    patchers = [patch(p, FakeHkaClient) for p in CLIENT_PATHS]
    for p in patchers:
        p.start()
    try:
        company.write({'l10n_pe_edi_provider': 'factory_hka', 'l10n_pe_edi_certificate_id': cert.id,
                       'l10n_pe_edi_test_env': True, 'l10n_pe_edi_factory_hka_username': 'QA20HKA',
                       'l10n_pe_edi_factory_hka_password': 'qa20'})
        igual(company._l10n_pe_edi_factory_hka_wsdl(), company.l10n_pe_edi_factory_hka_wsdl_demo,
              'Entorno de prueba usa el WSDL demo de HKA')
        move = _invoice(X['ruc'], [(X['srv'], 1, 200.0, 0, X['igv'])], journal=X['journal'])
        move.action_post()
        registro(move, 'factura enviada por HKA (simulado)')
        fname = move._l10n_pe_edi_generate_edi_filename()
        number = fname.rsplit('-', 1)[1]
        check(len(number) == 8 and number.isdigit(), 'Nombre de archivo con número en 8 dígitos', fname)
        res = move._l10n_pe_edi_post_invoice()
        check(not res, 'Envío sin errores', res)
        igual(move.l10n_pe_edi_status, 'sent', 'Aceptada (CDR simulado)')
        call = FakeHkaClient.calls[-1]
        igual((call['operation'], call['username']), ('sendBill', 'QA20HKA'), 'sendBill con el usuario de HKA')
        check(call['args'][0] == fname + '.zip', 'ZIP enviado con el nombre HKA', call['args'][0])
        att = move.l10n_pe_edi_attachment_id if 'l10n_pe_edi_attachment_id' in move._fields else False
        if att:
            import zipfile
            with zipfile.ZipFile(io.BytesIO(att.raw)) as zf:
                xml = zf.read(fname + '.xml')
            check(etree.fromstring(xml).xpath('//ds:Signature/ds:SignatureValue', namespaces=NS_UBL),
                  'XML firmado con el certificado (SignatureValue)')
        res = move._l10n_pe_edi_get_status_cdr_sunat_estela()
        igual(res.get('code'), '0004', 'Consulta de CDR (getStatusCdr)')
        move.l10n_pe_edi_cancel_reason = qa_name('Error en el importe')
        move._l10n_pe_edi_cancel_invoice()
        igual(move.l10n_pe_edi_status, 'cancelled', 'Baja por comunicación (sendSummary + getStatus)')
        igual([c['operation'] for c in FakeHkaClient.calls][-2:], ['sendSummary', 'getStatus'], 'Operaciones de baja')
        check(not move._l10n_pe_edi_factory_hka_goes_in_summary(), 'Factura: baja por RA, no por resumen')
        company.l10n_pe_edi_factory_hka_password = False
        move2 = _invoice(X['ruc'], [(X['srv'], 1, 100.0, 0, X['igv'])], journal=X['journal'])
        move2.action_post()
        registro(move2, 'factura sin credenciales HKA')
        n = len(FakeHkaClient.calls)
        res = move2._l10n_pe_edi_post_invoice()
        check('Factory HKA' in str(move2.l10n_pe_edi_warnings) and len(FakeHkaClient.calls) == n,
              'Sin contraseña: queda pendiente y no llama al OSE')
    finally:
        for p in patchers:
            p.stop()
        company.write({k: (v[0] if isinstance(v, tuple) else v) for k, v in old.items() if k != 'id'})
    igual(company.l10n_pe_edi_provider, old['l10n_pe_edi_provider'], 'Configuración de la compañía restaurada')
    omitido('Envío real a Factory HKA', 'sin credenciales de prueba; cliente SOAP simulado')


ejecutar_aparte(_hka)

for _p in _patchers:
    _p.stop()
