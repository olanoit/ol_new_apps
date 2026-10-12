# -*- coding: utf-8 -*-
"""XML de la percepción.

* Comprobante de percepción electrónico (tipo 40): UBL 2.0 con el esquema
  ``Perception-1`` de SUNAT, gemelo del comprobante de retención
  (``account.edi.xml.ubl_pe_withholding``): mismas partes (emisor y receptor),
  mismo bloque por comprobante cobrado (``cac:Payment`` + información de la
  percepción) y totales en soles.
* Factura de venta sujeta a percepción (guía UBL 2.1 de la factura): cargo
  ``cac:AllowanceCharge`` con el código del catálogo 53 (51, 52 o 53), tasa,
  importe y base en soles, y ``cac:PaymentTerms`` «Percepcion» con el monto
  total cobrado incluida la percepción.
"""
from lxml import etree

from odoo import models

from odoo.addons.al_l10n_pe_retention.models.withholding_edi_xml_ubl_pe import _amount
from odoo.addons.al_l10n_pe_retention.models import withholding_edi_xml_ubl_pe as retention_xml

NS = {**retention_xml.NS,
      None: 'urn:sunat:names:specification:ubl:peru:schema:xsd:Perception-1'}


def _el(parent, tag, text=None, **attrs):
    prefix, name = tag.split(':') if ':' in tag else (None, tag)
    element = etree.SubElement(parent, '{%s}%s' % (NS[prefix], name), **attrs)
    if text is not None:
        element.text = str(text)
    return element


class AccountEdiXmlUblPePerception(models.AbstractModel):
    _name = 'account.edi.xml.ubl_pe_perception'
    _inherit = 'account.edi.xml.ubl_pe_withholding'
    _description = 'Comprobante de percepción UBL (SUNAT)'

    def _export_perception(self, perception):
        """XML del comprobante de percepción sin la firma, en UTF-8 (bytes)."""
        company = perception.company_id
        company_partner = company.partner_id.commercial_partner_id
        currency = company.currency_id.name

        root = etree.Element('Perception', nsmap=NS)
        _el(root, 'cbc:UBLVersionID', '2.0')
        _el(root, 'cbc:CustomizationID', '1.0')
        signature = _el(root, 'cac:Signature')
        _el(signature, 'cbc:ID', 'IDSignKG')
        signatory = _el(signature, 'cac:SignatoryParty')
        _el(_el(signatory, 'cac:PartyIdentification'), 'cbc:ID', company_partner.vat or '')
        _el(_el(signatory, 'cac:PartyName'), 'cbc:Name', (company_partner.name or '').upper())
        _el(_el(_el(signature, 'cac:DigitalSignatureAttachment'), 'cac:ExternalReference'),
            'cbc:URI', '#SignVX')
        _el(root, 'cbc:ID', perception.l10n_pe_edi_perception_number)
        _el(root, 'cbc:IssueDate', perception.date)
        # Las partes se arman con el mismo código que el CRE; sus etiquetas
        # (cac/cbc) son comunes a los dos esquemas.
        self._l10n_pe_retention_party(root, 'cac:AgentParty', company_partner,
                                      company.l10n_pe_edi_address_type_code or '0000')
        self._l10n_pe_retention_party(root, 'cac:ReceiverParty', perception.partner_id)
        _el(root, 'sac:SUNATPerceptionSystemCode', perception.perception_code)
        _el(root, 'sac:SUNATPerceptionPercent', _amount(perception.rate))
        if perception.note:
            _el(root, 'cbc:Note', perception.note)
        _el(root, 'cbc:TotalInvoiceAmount', _amount(perception.amount_perception),
            currencyID=currency)
        _el(root, 'sac:SUNATTotalCashed', _amount(perception.amount_collected),
            currencyID=currency)
        for line in perception.line_ids:
            invoice = line.invoice_id
            reference = _el(root, 'sac:SUNATPerceptionDocumentReference')
            _el(reference, 'cbc:ID', perception._l10n_pe_edi_retention_bill_number(invoice),
                schemeID=invoice.l10n_latam_document_type_id.code or '01')
            _el(reference, 'cbc:IssueDate', invoice.invoice_date or invoice.date)
            _el(reference, 'cbc:TotalInvoiceAmount', _amount(invoice.amount_total),
                currencyID=invoice.currency_id.name)
            payment_node = _el(reference, 'cac:Payment')
            _el(payment_node, 'cbc:ID', perception._l10n_pe_perception_payment_index(invoice))
            _el(payment_node, 'cbc:PaidAmount', _amount(line.paid_amount),
                currencyID=invoice.currency_id.name)
            _el(payment_node, 'cbc:PaidDate', perception.date)
            information = _el(reference, 'sac:SUNATPerceptionInformation')
            _el(information, 'sac:SUNATPerceptionAmount', _amount(line.perception_pen),
                currencyID=currency)
            _el(information, 'sac:SUNATPerceptionDate', perception.date)
            _el(information, 'sac:SUNATNetTotalCashed', _amount(line.collected_pen),
                currencyID=currency)
            if invoice.currency_id != company.currency_id:
                exchange = _el(information, 'cac:ExchangeRate')
                _el(exchange, 'cbc:SourceCurrencyCode', invoice.currency_id.name)
                _el(exchange, 'cbc:TargetCurrencyCode', currency)
                _el(exchange, 'cbc:CalculationRate', _amount(line.exchange_rate, 6))
                _el(exchange, 'cbc:Date', perception.date)
        return etree.tostring(root, xml_declaration=True, encoding='UTF-8')


class AccountEdiXmlUblPe(models.AbstractModel):
    _inherit = 'account.edi.xml.ubl_pe'

    def _add_document_allowance_charge_nodes(self, document_node, vals):
        """Cargo de la percepción (catálogo 53: 51 venta interna, 52
        combustibles, 53 agente con tasa especial) en soles."""
        super()._add_document_allowance_charge_nodes(document_node, vals)
        invoice = vals['invoice']
        if invoice.move_type != 'out_invoice' or not invoice.l10n_pe_perception_code:
            return
        charges = document_node.setdefault('cac:AllowanceCharge', [])
        codes = {str((charge or {}).get('cbc:AllowanceChargeReasonCode', {}).get('_text'))
                 for charge in charges}
        if codes & {'51', '52', '53'}:
            return
        pen = invoice.company_id.currency_id
        charges.append({
            'cbc:ChargeIndicator': {'_text': 'true'},
            'cbc:AllowanceChargeReasonCode': {'_text': invoice.l10n_pe_perception_code},
            'cbc:MultiplierFactorNumeric': {
                '_text': self.format_float(invoice.l10n_pe_perception_rate / 100.0, 3)},
            'cbc:Amount': {'_text': self.format_float(invoice.l10n_pe_perception_amount, 2),
                           'currencyID': pen.name},
            'cbc:BaseAmount': {'_text': self.format_float(invoice.l10n_pe_perception_base_pen, 2),
                               'currencyID': pen.name},
        })

    def _add_invoice_payment_terms_nodes(self, document_node, vals):
        """«Percepcion»: monto total cobrado incluida la percepción, en soles."""
        super()._add_invoice_payment_terms_nodes(document_node, vals)
        invoice = vals['invoice']
        if invoice.move_type != 'out_invoice' or not invoice.l10n_pe_perception_code:
            return
        terms = document_node.get('cac:PaymentTerms')
        if terms is None:
            terms = document_node['cac:PaymentTerms'] = []
        elif isinstance(terms, dict):
            terms = document_node['cac:PaymentTerms'] = [terms]
        if any(str((term or {}).get('cbc:ID', {}).get('_text')) == 'Percepcion' for term in terms):
            return
        terms.insert(0, {
            'cbc:ID': {'_text': 'Percepcion'},
            'cbc:Amount': {'_text': self.format_float(invoice._l10n_pe_perception_total_pen(), 2),
                           'currencyID': invoice.company_id.currency_id.name},
        })
