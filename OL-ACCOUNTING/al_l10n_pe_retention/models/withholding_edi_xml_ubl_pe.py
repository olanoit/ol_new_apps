# -*- coding: utf-8 -*-
"""XML UBL 2.0 del Comprobante de Retención Electrónico (tipo 20).

Mismo nombre de modelo y punto de entrada (``_export_retention``) que el
módulo oficial de Odoo ``l10n_pe_edi_withholding`` (Enterprise 19.4/20), para
poder cambiar a él sin tocar a quien lo llame. Implementación propia con lxml,
contrastada con los XML de prueba oficiales.
"""
from lxml import etree

from odoo import models

NS = {
    None: 'urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
}


def _el(parent, tag, text=None, **attrs):
    """Subelemento ``prefijo:nombre`` con texto y atributos."""
    prefix, name = tag.split(':') if ':' in tag else (None, tag)
    element = etree.SubElement(parent, '{%s}%s' % (NS[prefix], name), **attrs)
    if text is not None:
        element.text = str(text)
    return element


def _amount(value, digits=2):
    return '%.*f' % (digits, value)


class AccountEdiXmlUblPeWithholding(models.AbstractModel):
    _name = 'account.edi.xml.ubl_pe_withholding'
    _inherit = 'account.edi.xml.ubl_pe'
    _description = 'Comprobante de retención UBL (SUNAT)'

    def _export_retention(self, payment):
        """XML del CRE sin el bloque de firma, en UTF-8 (bytes)."""
        company = payment.company_id
        company_partner = company.partner_id.commercial_partner_id
        currency = company.currency_id.name
        breakdown = payment._l10n_pe_edi_get_retention_breakdown()

        root = etree.Element('Retention', nsmap=NS)
        _el(root, 'cbc:UBLVersionID', '2.0')
        _el(root, 'cbc:CustomizationID', '1.0')
        signature = _el(root, 'cac:Signature')
        _el(signature, 'cbc:ID', 'IDSignKG')
        signatory = _el(signature, 'cac:SignatoryParty')
        _el(_el(signatory, 'cac:PartyIdentification'), 'cbc:ID', company_partner.vat or '')
        _el(_el(signatory, 'cac:PartyName'), 'cbc:Name', (company_partner.name or '').upper())
        _el(_el(_el(signature, 'cac:DigitalSignatureAttachment'), 'cac:ExternalReference'),
            'cbc:URI', '#SignVX')
        _el(root, 'cbc:ID', payment.l10n_pe_edi_retention_number or payment.name)
        _el(root, 'cbc:IssueDate', payment.date)
        self._l10n_pe_retention_party(root, 'cac:AgentParty', company_partner,
                                      company.l10n_pe_edi_address_type_code or '0000')
        self._l10n_pe_retention_party(root, 'cac:ReceiverParty', payment.partner_id)
        _el(root, 'sac:SUNATRetentionSystemCode', '01')
        _el(root, 'sac:SUNATRetentionPercent', _amount(company.l10n_pe_retention_rate))
        if payment.memo:
            _el(root, 'cbc:Note', payment.memo)
        # Totales en soles: importe retenido y pagado neto de la retención.
        _el(root, 'cbc:TotalInvoiceAmount',
            _amount(sum(entry['bill_retention_pen'] for entry in breakdown)), currencyID=currency)
        _el(root, 'sac:SUNATTotalPaid',
            _amount(sum(entry['net_total_paid_pen'] for entry in breakdown)), currencyID=currency)
        for index, entry in enumerate(breakdown, start=1):
            bill = entry['bill']
            reference = _el(root, 'sac:SUNATRetentionDocumentReference')
            _el(reference, 'cbc:ID', payment._l10n_pe_edi_retention_bill_number(bill),
                schemeID=bill.l10n_latam_document_type_id.code or '01')
            _el(reference, 'cbc:IssueDate', bill.invoice_date or bill.date)
            _el(reference, 'cbc:TotalInvoiceAmount', _amount(bill.amount_total),
                currencyID=bill.currency_id.name)
            payment_node = _el(reference, 'cac:Payment')
            _el(payment_node, 'cbc:ID', index)
            _el(payment_node, 'cbc:PaidAmount', _amount(entry['bill_paid_currency']),
                currencyID=bill.currency_id.name)
            _el(payment_node, 'cbc:PaidDate', payment.date)
            information = _el(reference, 'sac:SUNATRetentionInformation')
            _el(information, 'sac:SUNATRetentionAmount', _amount(entry['bill_retention_pen']),
                currencyID=currency)
            _el(information, 'sac:SUNATRetentionDate', payment.date)
            _el(information, 'sac:SUNATNetTotalPaid', _amount(entry['net_total_paid_pen']),
                currencyID=currency)
            if bill.currency_id != company.currency_id:
                exchange = _el(information, 'cac:ExchangeRate')
                _el(exchange, 'cbc:SourceCurrencyCode', bill.currency_id.name)
                _el(exchange, 'cbc:TargetCurrencyCode', currency)
                _el(exchange, 'cbc:CalculationRate', _amount(entry['exchange_rate'], 6))
                _el(exchange, 'cbc:Date', payment.date)
        return etree.tostring(root, xml_declaration=True, encoding='UTF-8')

    def _l10n_pe_retention_party(self, parent, tag, partner, address_type_code=None):
        """AgentParty / ReceiverParty en el orden UBL 2.0: documento, nombre,
        dirección, razón social (con RUC y domicilio fiscal) y contacto."""
        partner = partner.commercial_partner_id
        doc_type = partner.l10n_latam_identification_type_id.l10n_pe_vat_code or '6'
        name = partner.name or ''
        country_code = partner.country_id.code or 'PE'
        country_name = partner.country_id.name or 'Peru'

        def add_country(node):
            country = _el(node, 'cac:Country')
            _el(country, 'cbc:IdentificationCode', country_code)
            _el(country, 'cbc:Name', country_name)

        node = _el(parent, tag)
        _el(_el(node, 'cac:PartyIdentification'), 'cbc:ID', partner.vat or '', schemeID=doc_type)
        _el(_el(node, 'cac:PartyName'), 'cbc:Name', name)
        address = _el(node, 'cac:PostalAddress')
        if partner.street:
            _el(address, 'cbc:StreetName', partner.street)
        if partner.city:
            _el(address, 'cbc:CityName', partner.city)
        if partner.state_id:
            _el(address, 'cbc:CountrySubentity', partner.state_id.name)
        add_country(address)
        legal = _el(node, 'cac:PartyLegalEntity')
        _el(legal, 'cbc:RegistrationName', name)
        _el(legal, 'cbc:CompanyID', partner.vat or '')
        registration = _el(legal, 'cac:RegistrationAddress')
        if address_type_code:
            # código del establecimiento anexo (0000 = domicilio fiscal)
            _el(registration, 'cbc:AddressTypeCode', address_type_code)
        add_country(registration)
        _el(_el(node, 'cac:Contact'), 'cbc:Name', name)
        return node
