# -*- coding: utf-8 -*-
"""XML UBL 2.1 de la liquidación de compra electrónica (``SelfBilledInvoice``).

Implementación propia desde el anexo 6, literal e), de la R.S. 097-2012/SUNAT
(sustituido por la R.S. 244-2019/SUNAT): el emisor (comprador) va en
``AccountingCustomerParty`` y el vendedor en ``AccountingSupplierParty``; el
lugar de la operación, en ``DeliveryTerms/DeliveryLocation``; la retención del
impuesto a la renta, como ``TaxSubtotal`` del tributo 3000 (``IR``, ``TOX``).

Importes (anexo 27):

* Total valor de venta = suma de los valores de venta de los ítems.
* Monto total de tributos = IGV + otros tributos (sin la retención de renta).
* Sub total = total valor de venta + monto total de tributos.
* Importe total neto = sub total − IGV (crédito) − IR (retención).

El orden de los elementos es el del esquema OASIS ``UBL-SelfBilledInvoice-2.1``.
"""
from lxml import etree

from odoo import models
from odoo.tools import float_repr

NS = {
    None: 'urn:oasis:names:specification:ubl:schema:xsd:SelfBilledInvoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
}
CATALOG_URI = 'urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo%s'
UNECE = 'United Nations Economic Commission for Europe'
# Catálogo 05: código, nombre y código internacional de cada tributo.
TAX_SCHEMES = {
    '1000': ('IGV', 'VAT'),
    '3000': ('IR', 'TOX'),
    '9996': ('GRA', 'FRE'),
    '9997': ('EXO', 'VAT'),
    '9998': ('INA', 'FRE'),
    '9999': ('OTROS', 'OTH'),
}


def _el(parent, tag, text=None, **attrs):
    """Subelemento ``prefijo:nombre`` con texto y atributos."""
    prefix, name = tag.split(':') if ':' in tag else (None, tag)
    element = etree.SubElement(parent, '{%s}%s' % (NS[prefix], name), **attrs)
    if text is not None:
        element.text = str(text)
    return element


class AccountEdiXmlUblPeLce(models.AbstractModel):
    _name = 'account.edi.xml.ubl_pe_lce'
    _description = 'Liquidación de compra electrónica UBL (SUNAT)'

    def _export_purchase_settlement(self, move):
        """XML de la liquidación de compra sin firmar (bytes UTF-8), con
        ``cac:Signature`` pero sin el bloque ``ext:UBLExtensions``: lo añade
        quien firma (como en ``l10n_pe_edi``)."""
        values = move._l10n_pe_lce_values()
        company = move.company_id
        currency = move.currency_id.name

        def amount(value):
            return float_repr(value, 2)

        root = etree.Element('SelfBilledInvoice', nsmap=NS)
        _el(root, 'cbc:UBLVersionID', '2.1')
        _el(root, 'cbc:CustomizationID', '2.0')
        _el(root, 'cbc:ID', values['number'])
        _el(root, 'cbc:IssueDate', move.invoice_date.isoformat())
        _el(root, 'cbc:InvoiceTypeCode', '04',
            listID=move.l10n_pe_lce_operation_type or '0501',
            listAgencyName='PE:SUNAT', listName='Tipo de Documento',
            listURI=CATALOG_URI % '01', name='Tipo de Operacion',
            listSchemeURI=CATALOG_URI % '51')
        _el(root, 'cbc:DocumentCurrencyCode', currency, listID='ISO 4217 Alpha',
            listName='Currency', listAgencyName=UNECE)

        # Firma (la referencia que usa la firma digital de l10n_pe_edi).
        signature = _el(root, 'cac:Signature')
        _el(signature, 'cbc:ID', 'IDSignKG')
        signatory = _el(signature, 'cac:SignatoryParty')
        _el(_el(signatory, 'cac:PartyIdentification'), 'cbc:ID', company.vat)
        _el(_el(signatory, 'cac:PartyName'), 'cbc:Name', company.name.upper())
        _el(_el(_el(signature, 'cac:DigitalSignatureAttachment'), 'cac:ExternalReference'),
            'cbc:URI', '#SignVX')

        # Emisor electrónico (comprador).
        buyer = _el(_el(root, 'cac:AccountingCustomerParty'), 'cac:Party')
        _el(_el(buyer, 'cac:PartyIdentification'), 'cbc:ID', company.vat, schemeID='6',
            schemeName='Documento de Identidad', schemeAgencyName='PE:SUNAT',
            schemeURI=CATALOG_URI % '06')
        buyer_entity = _el(buyer, 'cac:PartyLegalEntity')
        _el(buyer_entity, 'cbc:RegistrationName', company.name)
        self._lce_address(buyer_entity, 'cac:RegistrationAddress', values['buyer_address'])

        # Vendedor.
        seller = _el(_el(root, 'cac:AccountingSupplierParty'), 'cac:Party')
        _el(_el(seller, 'cac:PartyIdentification'), 'cbc:ID', values['seller_vat'],
            schemeID=values['seller_doc_type'], schemeName='Documento de Identidad',
            schemeAgencyName='PE:SUNAT', schemeURI=CATALOG_URI % '06')
        seller_entity = _el(seller, 'cac:PartyLegalEntity')
        _el(seller_entity, 'cbc:RegistrationName', values['seller_name'])
        self._lce_address(seller_entity, 'cac:RegistrationAddress', values['seller_address'],
                          type_code=move.l10n_pe_lce_partner_address_type)

        # Traslado de los bienes con la liquidación (placa del vehículo).
        if move.l10n_pe_lce_license_plate:
            shipment = _el(_el(root, 'cac:Delivery'), 'cac:Shipment')
            _el(shipment, 'cbc:ID', '02')
            stage = _el(shipment, 'cac:ShipmentStage')
            _el(_el(_el(stage, 'cac:TransportMeans'), 'cac:RoadTransport'),
                'cbc:LicensePlateID', move.l10n_pe_lce_license_plate)
            if move.l10n_pe_lce_trailer_plate:
                _el(_el(_el(shipment, 'cac:TransportHandlingUnit'), 'cac:TransportEquipment'),
                    'cbc:ID', move.l10n_pe_lce_trailer_plate)

        # Lugar donde se realiza la operación.
        location = _el(_el(root, 'cac:DeliveryTerms'), 'cac:DeliveryLocation')
        _el(location, 'cbc:LocationTypeCode', move.l10n_pe_lce_place_type)
        self._lce_address(location, 'cac:Address', values['place_address'])

        # Totales de tributos.
        tax_total = _el(root, 'cac:TaxTotal')
        _el(tax_total, 'cbc:TaxAmount', amount(values['tax_amount']), currencyID=currency)
        for code, base, tax in values['tax_subtotals']:
            subtotal = _el(tax_total, 'cac:TaxSubtotal')
            _el(subtotal, 'cbc:TaxableAmount', amount(base), currencyID=currency)
            _el(subtotal, 'cbc:TaxAmount', amount(tax), currencyID=currency)
            self._lce_tax_category(subtotal, code, global_level=True)

        monetary = _el(root, 'cac:LegalMonetaryTotal')
        _el(monetary, 'cbc:LineExtensionAmount', amount(values['untaxed']), currencyID=currency)
        _el(monetary, 'cbc:TaxInclusiveAmount', amount(values['subtotal']), currencyID=currency)
        _el(monetary, 'cbc:PayableAmount', amount(values['net']), currencyID=currency)

        for line in values['lines']:
            self._lce_invoice_line(root, line, currency)
        return etree.tostring(root, xml_declaration=True, encoding='UTF-8')

    def _lce_address(self, parent, tag, address, type_code=None):
        """Dirección con ubigeo (catálogo 13): orden de ``AddressType``."""
        node = _el(parent, tag)
        _el(node, 'cbc:ID', address['ubigeo'], schemeAgencyName='PE:INEI', schemeName='Ubigeos')
        if type_code:
            _el(node, 'cbc:AddressTypeCode', type_code, listAgencyName='PE:SUNAT',
                listName='Tipo de Direccion', listURI=CATALOG_URI % '60')
        if address['urbanization']:
            _el(node, 'cbc:CitySubdivisionName', address['urbanization'])
        _el(node, 'cbc:CityName', address['province'])
        _el(node, 'cbc:CountrySubentity', address['department'])
        _el(node, 'cbc:District', address['district'])
        _el(_el(node, 'cac:AddressLine'), 'cbc:Line', address['street'])
        _el(_el(node, 'cac:Country'), 'cbc:IdentificationCode', 'PE', listID='ISO 3166-1',
            listAgencyName=UNECE, listName='Country')
        return node

    def _lce_tax_category(self, parent, code, percent=None, exemption=None, global_level=False):
        category = _el(parent, 'cac:TaxCategory')
        if percent is not None:
            _el(category, 'cbc:Percent', float_repr(percent, 2))
        if exemption:
            _el(category, 'cbc:TaxExemptionReasonCode', exemption, listAgencyName='PE:SUNAT',
                listName='Afectacion del IGV', listURI=CATALOG_URI % '07')
        name, international = TAX_SCHEMES[code]
        scheme = _el(category, 'cac:TaxScheme')
        attrs = {'schemeName': 'Codigo de tributos', 'schemeAgencyName': 'PE:SUNAT',
                 'schemeURI': CATALOG_URI % '05'} if global_level else {}
        _el(scheme, 'cbc:ID', code, **attrs)
        _el(scheme, 'cbc:Name', name)
        _el(scheme, 'cbc:TaxTypeCode', international)
        return category

    def _lce_invoice_line(self, root, line, currency):
        node = _el(root, 'cac:InvoiceLine')
        _el(node, 'cbc:ID', line['sequence'])
        _el(node, 'cbc:InvoicedQuantity', float_repr(line['quantity'], 10).rstrip('0').rstrip('.'),
            unitCode=line['uom_code'], unitCodeListID='UN/ECE rec 20',
            unitCodeListAgencyName=UNECE)
        _el(node, 'cbc:LineExtensionAmount', float_repr(line['untaxed'], 2), currencyID=currency)
        alternative = _el(_el(node, 'cac:PricingReference'), 'cac:AlternativeConditionPrice')
        _el(alternative, 'cbc:PriceAmount', float_repr(line['price_with_tax'], 10).rstrip('0').rstrip('.'),
            currencyID=currency)
        _el(alternative, 'cbc:PriceTypeCode', '01', listName='Tipo de Precio',
            listAgencyName='PE:SUNAT', listURI=CATALOG_URI % '16')

        tax_total = _el(node, 'cac:TaxTotal')
        _el(tax_total, 'cbc:TaxAmount', float_repr(line['igv'], 2), currencyID=currency)
        igv = _el(tax_total, 'cac:TaxSubtotal')
        _el(igv, 'cbc:TaxableAmount', float_repr(line['untaxed'], 2), currencyID=currency)
        _el(igv, 'cbc:TaxAmount', float_repr(line['igv'], 2), currencyID=currency)
        self._lce_tax_category(igv, line['igv_code'], percent=line['igv_rate'],
                               exemption=line['affectation'])
        ir = _el(tax_total, 'cac:TaxSubtotal')
        _el(ir, 'cbc:TaxableAmount', float_repr(line['untaxed'], 2), currencyID=currency)
        _el(ir, 'cbc:TaxAmount', float_repr(line['ir'], 2), currencyID=currency)
        self._lce_tax_category(ir, '3000', percent=line['ir_rate'])

        item = _el(node, 'cac:Item')
        _el(item, 'cbc:Description', line['description'])
        if line['default_code']:
            _el(_el(item, 'cac:SellersItemIdentification'), 'cbc:ID', line['default_code'])
        if line['unspsc']:
            _el(_el(item, 'cac:CommodityClassification'), 'cbc:ItemClassificationCode',
                line['unspsc'], listID='UNSPSC', listAgencyName='GS1 US',
                listName='Item Classification')
        _el(_el(node, 'cac:Price'), 'cbc:PriceAmount',
            float_repr(line['price_unit'], 10).rstrip('0').rstrip('.'), currencyID=currency)
        return node
