# -*- coding: utf-8 -*-
"""Envío a SUNAT de los CPE que no son facturas (retención, percepción y sus
reversiones).

En Odoo 20 ``l10n_pe_edi`` dejó ``account.edi.format``: sus servicios son
métodos de la factura (``account.move``) que leen el tipo y el nombre del
propio comprobante. Este servicio arma lo mismo para cualquier documento a
partir de las primitivas de ``l10n_pe_edi`` (credenciales de la compañía,
firma, zip, SOAP e IAP) y devuelve la forma que usaban los servicios de 19:
``{'success': True, 'xml_document', 'cdr'}``, ``{'xml_document', 'cdr',
'cdr_number'}`` o ``{'error', 'blocking_level'}``.
"""
import base64
from copy import deepcopy

from lxml import etree, objectify
from requests.exceptions import (
    ConnectionError as ReqConnectionError, HTTPError, InvalidSchema, InvalidURL, ReadTimeout,
    RequestException,
)
from odoo.tools.zeep import Client, Settings

from odoo import api, models
from odoo.tools import BinaryBytes

from odoo.addons.iap.tools.iap_tools import iap_jsonrpc


def _as_error(result):
    """Error de los servicios de 20 (``message``/``level``) con la forma de 19;
    conserva el código de SUNAT (p. ej. 1033: el comprobante ya existe)."""
    error = {'error': result.get('message') or result.get('error'),
             'blocking_level': result.get('level', 'error')}
    if result.get('code'):
        error['code'] = result['code']
    return error


class L10nPeEdiCpeService(models.AbstractModel):
    _name = 'l10n_pe.edi.cpe.service'
    _description = 'Envío de CPE a SUNAT (otros comprobantes)'

    @api.model
    def _move(self):
        return self.env['account.move']

    @api.model
    def _credentials(self, company, sunat_wsdl):
        """Credenciales del operador; un operador sin configurar puede
        devolver ``{'error', 'blocking_level'}``."""
        return company._l10n_pe_edi_get_credentials(sunat_wsdl=sunat_wsdl)

    @api.model
    def _soap_client(self, credentials):
        return Client(wsdl=credentials['wsdl'], wsse=credentials['token'],
                      settings=Settings(raw_response=True), operation_timeout=15, timeout=15)

    @api.model
    def _sign(self, company, edi_str):
        certificate = company.sudo().l10n_pe_edi_certificate_id
        tree = self._move()._l10n_pe_edi_sign(certificate, objectify.fromstring(edi_str))
        return etree.tostring(tree, xml_declaration=True, encoding='ISO-8859-1')

    # ------------------------------------------------------------------
    # Envío (sendBill)
    # ------------------------------------------------------------------
    @api.model
    def _send_bill(self, company, filename, edi_str, cpe_type, sunat_wsdl):
        if company.l10n_pe_edi_provider == 'iap':
            result = self._send_bill_iap(company, filename, edi_str, cpe_type)
        else:
            result = self._send_bill_soap(company, filename, edi_str, sunat_wsdl)
        return result if result.get('success') else _as_error(result)

    @api.model
    def _send_bill_soap(self, company, filename, edi_str, sunat_wsdl):
        Move = self._move()
        if not company.sudo().l10n_pe_edi_certificate_id:
            return {'message': self.env._('No hay un certificado válido para %s.', company.display_name)}
        credentials = self._credentials(company, sunat_wsdl)
        if credentials.get('error'):
            return {'message': credentials['error'], 'level': credentials.get('blocking_level', 'error')}
        edi_str = self._sign(company, edi_str)
        zip_str = Move._l10n_pe_edi_zip_edi_document([('%s.xml' % filename, edi_str)])
        decoded = Move._l10n_pe_edi_send_bill_sunat_estela(credentials, filename, zip_str)
        if decoded.get('error'):
            return {'message': decoded['error'], 'level': decoded.get('level', 'error'),
                    'code': decoded.get('code')}
        return self._cdr_result(decoded['cdr'], edi_str)

    @api.model
    def _send_bill_iap(self, company, filename, edi_str, cpe_type):
        Move = self._move()
        # Firma de relleno para validar el XSD; IAP la reemplaza.
        tree = deepcopy(objectify.fromstring(edi_str))
        signature = tree.xpath('.//ds:Signature', namespaces={'ds': 'http://www.w3.org/2000/09/xmldsig#'})
        if signature:
            dummy = self.env['ir.qweb']._render('l10n_pe_edi.ubl_pe_21_signature_template', {'digest_value': ''})
            signature[0].getparent().replace(signature[0], objectify.fromstring(dummy))
        dbuuid, url, token = Move._l10n_pe_edi_get_iap_params(company)
        params = {'vat': company.vat, 'doc_type': cpe_type, 'dbuuid': dbuuid, 'fname': filename,
                  'xml': BinaryBytes(edi_str).to_base64(), 'token': token}
        try:
            result = iap_jsonrpc(url + '/iap/l10n_pe_edi/1/send_bill', params=params, timeout=60)
        except (InvalidSchema, InvalidURL):
            return {'message': Move._l10n_pe_edi_get_general_error_messages()['L10NPE18']}
        except RequestException:
            return {'message': Move._l10n_pe_edi_get_general_error_messages()['L10NPE17'], 'level': 'warning'}
        if result.get('message'):
            return {'message': result['message']}
        xml_document = result.get('signed') and Move._l10n_pe_edi_unzip_edi_document(
            base64.b64decode(result['signed']))
        soap = result.get('cdr') and base64.b64decode(result['cdr'])
        decoded = Move._l10n_pe_edi_decode_soap_response(soap) if soap else {}
        if decoded.get('error') or not decoded.get('cdr'):
            return {'message': decoded.get('error') or self.env._('Sin respuesta de SUNAT.'),
                    'code': decoded.get('code')}
        return self._cdr_result(decoded['cdr'], xml_document)

    @api.model
    def _cdr_result(self, cdr, xml_document):
        status = self._move()._l10n_pe_edi_extract_cdr_status(cdr)
        if status['code'] != '0':
            return {'message': status['description']}
        return {'success': True, 'xml_document': xml_document, 'cdr': cdr}

    # ------------------------------------------------------------------
    # Resumen de bajas o reversiones (sendSummary) y su ticket (getStatus)
    # ------------------------------------------------------------------
    @api.model
    def _send_summary(self, company, filename, edi_str, sunat_wsdl):
        Move = self._move()
        if company.l10n_pe_edi_provider == 'iap':
            dbuuid, url, token = Move._l10n_pe_edi_get_iap_params(company)
            params = {'vat': company.vat, 'dbuuid': dbuuid, 'fname': filename,
                      'xml': base64.encodebytes(edi_str).decode(), 'token': token}
            try:
                result = iap_jsonrpc(url + '/iap/l10n_pe_edi/1/send_summary', params=params, timeout=15)
            except RequestException:
                return {'error': Move._l10n_pe_edi_get_general_error_messages()['L10NPE17'],
                        'blocking_level': 'warning'}
            if result.get('message'):
                return {'error': result['message'], 'blocking_level': 'error'}
            soap = result.get('cdr') and base64.b64decode(result['cdr'])
            xml_document = result.get('signed') and Move._l10n_pe_edi_unzip_edi_document(
                base64.b64decode(result['signed']))
        else:
            credentials = self._credentials(company, sunat_wsdl)
            if credentials.get('error'):
                return credentials
            xml_document = self._sign(company, edi_str)
            zip_str = Move._l10n_pe_edi_zip_edi_document([('%s.xml' % filename, xml_document)])
            try:
                response = self._soap_client(credentials).service.sendSummary(
                    '%s.zip' % filename, zip_str)
                response.raise_for_status()
            except (ReqConnectionError, HTTPError, TypeError, ReadTimeout):
                return {'error': Move._l10n_pe_edi_get_general_error_messages()['L10NPE08'],
                        'blocking_level': 'warning'}
            soap = response.content
        decoded = Move._l10n_pe_edi_decode_soap_response(soap) if soap else {}
        if decoded.get('error') or not decoded.get('number'):
            return {'error': decoded.get('error') or self.env._('Sin respuesta de SUNAT.'),
                    'blocking_level': 'error'}
        return {'xml_document': xml_document, 'cdr': soap, 'cdr_number': decoded['number']}

    @api.model
    def _get_status(self, company, ticket, sunat_wsdl):
        Move = self._move()
        if company.l10n_pe_edi_provider == 'iap':
            dbuuid, url, token = Move._l10n_pe_edi_get_iap_params(company)
            params = {'vat': company.vat, 'dbuuid': dbuuid, 'number': ticket, 'token': token}
            try:
                result = iap_jsonrpc(url + '/iap/l10n_pe_edi/1/get_status', params=params, timeout=15)
            except RequestException:
                return {'error': Move._l10n_pe_edi_get_general_error_messages()['L10NPE17'],
                        'blocking_level': 'warning'}
            if result.get('message'):
                return {'error': result['message'], 'blocking_level': 'error'}
            soap = result.get('cdr') and base64.b64decode(result['cdr'])
        else:
            credentials = self._credentials(company, sunat_wsdl)
            if credentials.get('error'):
                return credentials
            try:
                response = self._soap_client(credentials).service.getStatus(ticket)
                response.raise_for_status()
            except (ReqConnectionError, HTTPError, TypeError, ReadTimeout):
                return {'error': Move._l10n_pe_edi_get_general_error_messages()['L10NPE08'],
                        'blocking_level': 'warning'}
            soap = response.content
        result = Move._l10n_pe_edi_parse_cancel_soap(soap)
        return result if result.get('success') else _as_error(result)

    # ------------------------------------------------------------------
    # Constancia de un comprobante ya enviado (getStatusCdr)
    # ------------------------------------------------------------------
    @api.model
    def _get_status_cdr(self, company, doc_type, serie, folio):
        """``{'cdr'}`` si SUNAT ya tiene el comprobante aceptado, o
        ``{'error', 'blocking_level'}``."""
        Move = self._move()
        if company.l10n_pe_edi_provider == 'iap':
            dbuuid, url, token = Move._l10n_pe_edi_get_iap_params(company)
            params = {'vat': company.vat, 'doc_type': doc_type, 'dbuuid': dbuuid,
                      'serie': serie, 'folio': folio, 'token': token}
            try:
                result = iap_jsonrpc(url + '/iap/l10n_pe_edi/1/get_status_cdr', params=params, timeout=60)
            except RequestException:
                return {'error': Move._l10n_pe_edi_get_general_error_messages()['L10NPE17'],
                        'blocking_level': 'warning'}
            if result.get('message'):
                return {'error': result['message'], 'blocking_level': 'error'}
            soap = result.get('cdr') and base64.b64decode(result['cdr'])
        else:
            credentials = self._credentials(
                company, 'https://e-factura.sunat.gob.pe/ol-it-wsconscpegem/billConsultService?wsdl')
            if credentials.get('error'):
                return credentials
            try:
                response = self._soap_client(credentials).service.getStatusCdr(
                    company.vat, doc_type, serie, folio)
                response.raise_for_status()
            except (ReqConnectionError, HTTPError, TypeError, ReadTimeout):
                return {'error': Move._l10n_pe_edi_get_general_error_messages()['L10NPE08'],
                        'blocking_level': 'warning'}
            soap = response.content
        decoded = Move._l10n_pe_edi_decode_soap_response(soap) if soap else {}
        if decoded.get('error') or decoded.get('code') != '0004' or not decoded.get('cdr'):
            return {'error': decoded.get('error') or self.env._('SUNAT no tiene la constancia.'),
                    'blocking_level': 'error'}
        if self._move()._l10n_pe_edi_extract_cdr_status(decoded['cdr'])['code'] != '0':
            return {'error': self.env._('SUNAT registró el comprobante como rechazado.'),
                    'blocking_level': 'error'}
        return {'cdr': decoded['cdr']}
