# -*- coding: utf-8 -*-
"""XML UBL 2.0 del Comprobante de Retención Electrónico (tipo 20).

Odoo 20 trae el generador (``l10n_pe_edi_withholding``): aquí solo se ajustan
sus partes para que sirva a cualquier documento ``l10n_pe.retention.edi.mixin``
(un pago o un CRE sin pago de Odoo): tasa del régimen de la compañía, nota,
totales del reparto, número del comprobante citado y número del pago a ese
comprobante. ``_l10n_pe_retention_party`` y los helpers ``_el``/``_amount``
los usa además el comprobante de percepción.
"""
from lxml import etree

from odoo import models

from odoo.addons.account_edi_ubl_cii.models.account_edi_common import FloatFmt

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
    _inherit = 'account.edi.xml.ubl_pe_withholding'

    def _add_retention_header_nodes(self, document_node, vals):
        """Tasa del régimen de la compañía y nota del documento: el nativo las
        toma de la línea de retención y del memo del pago, que el CRE sin pago
        no tiene."""
        document = vals['payment']
        note = document._l10n_pe_retention_note()
        document_node.update({
            'cbc:UBLVersionID': {'_text': '2.0'},
            'cbc:CustomizationID': {'_text': '1.0'},
            'cbc:ID': {'_text': document.l10n_pe_edi_retention_number or document.name},
            'cbc:IssueDate': {'_text': document.date},
            'sac:SUNATRetentionSystemCode': {'_text': '01'},
            'sac:SUNATRetentionPercent': {
                '_text': FloatFmt(document.company_id.l10n_pe_retention_rate, min_dp=2)},
            'cbc:Note': {'_text': note} if note else None,
        })

    def _add_retention_monetary_totals_nodes(self, document_node, vals):
        """Totales en soles desde el reparto: retenido y pagado neto (el
        nativo parte del importe del pago, que el CRE sin pago no tiene)."""
        currency = vals['company_currency_id'].name
        breakdown = vals['breakdown']
        document_node.update({
            'cbc:TotalInvoiceAmount': {
                '_text': FloatFmt(sum(e['bill_retention_pen'] for e in breakdown), min_dp=2),
                'currencyID': currency},
            'sac:SUNATTotalPaid': {
                '_text': FloatFmt(sum(e['net_total_paid_pen'] for e in breakdown), min_dp=2),
                'currencyID': currency},
        })

    def _add_retention_document_reference_nodes(self, document_node, vals):
        """Número del comprobante citado (serie-número SUNAT, también sin tipo
        de documento LATAM) y número del pago a ESE comprobante (1, 2…), no su
        posición en el CRE."""
        super()._add_retention_document_reference_nodes(document_node, vals)
        document = vals['payment']
        references = document_node.get('sac:SUNATRetentionDocumentReference') or []
        for reference, entry in zip(references, vals['breakdown']):
            bill = entry['bill']
            reference['cbc:ID'] = {
                '_text': document._l10n_pe_edi_retention_bill_number(bill),
                'schemeID': bill.l10n_latam_document_type_id.code
                or ('07' if bill.move_type == 'in_refund' else '01'),
            }
            reference['cbc:IssueDate'] = {'_text': bill.invoice_date or bill.date}
            reference['cac:Payment']['cbc:ID'] = {
                '_text': str(document._l10n_pe_edi_retention_payment_index(bill))}

    def _l10n_pe_retention_party(self, parent, tag, partner, address_type_code=None):
        """AgentParty / ReceiverParty en el orden UBL 2.0: documento, nombre,
        dirección, razón social (con RUC y domicilio fiscal) y contacto."""
        partner = partner.commercial_partner_id
        doc_type = partner.l10n_pe_sunat_id_code or '6'
        name = partner.name or ''
        country_code = partner.country_id.code or 'PE'
        country_name = partner.country_id.name or 'Peru'

        def add_country(node):
            country = _el(node, 'cac:Country')
            _el(country, 'cbc:IdentificationCode', country_code)
            _el(country, 'cbc:Name', country_name)

        node = _el(parent, tag)
        _el(_el(node, 'cac:PartyIdentification'), 'cbc:ID', partner.l10n_pe_sunat_id_value or '', schemeID=doc_type)
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
        _el(legal, 'cbc:CompanyID', partner.l10n_pe_sunat_id_value or '')
        registration = _el(legal, 'cac:RegistrationAddress')
        if address_type_code:
            # código del establecimiento anexo (0000 = domicilio fiscal)
            _el(registration, 'cbc:AddressTypeCode', address_type_code)
        add_country(registration)
        _el(_el(node, 'cac:Contact'), 'cbc:Name', name)
        return node
