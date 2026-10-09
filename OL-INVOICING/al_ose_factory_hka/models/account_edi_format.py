# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools.zeep.wsse.username import UsernameToken


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    # Factory HKA expone el mismo billService de SUNAT (sendBill, getStatus,
    # sendSummary, getStatusCdr): basta con sus credenciales y su WSDL, y el
    # resto lo hacen los servicios comunes de l10n_pe_edi, que ``getattr``
    # elige por el nombre del proveedor.

    def _l10n_pe_edi_get_factory_hka_credentials(self, company):
        """Credenciales con la forma de las nativas, o ``{'error': …}`` si
        falta configuración (sin excepción, para no cortar el cron del EDI)."""
        self.ensure_one()
        company_sudo = company.sudo()  # credenciales con groups=base.group_system
        username = company_sudo.l10n_pe_edi_factory_hka_username
        password = company_sudo.l10n_pe_edi_factory_hka_password
        if not username or not password:
            return {'error': self.env._(
                'Faltan el usuario o la contraseña de Factory HKA de %(company)s. '
                'Configúrelos en Ajustes ▸ Contabilidad ▸ Facturación electrónica peruana.',
                company=company.display_name), 'blocking_level': 'error'}
        wsdl = company._l10n_pe_edi_factory_hka_wsdl()
        if not wsdl:
            return {'error': self.env._(
                'Falta el WSDL de producción de Factory HKA de %(company)s. '
                'Configúrelo en Ajustes o active «Entorno de prueba».',
                company=company.display_name), 'blocking_level': 'error'}
        return {'fault_ns': 'S', 'wsdl': wsdl, 'token': UsernameToken(username, password)}

    def _l10n_pe_edi_factory_hka_filename(self, edi_filename):
        """``RUC-TT-SERIE-NUMERO`` con el número en 8 dígitos, como exige HKA
        (``20524531861-01-F001-11`` → ``20524531861-01-F001-00000011``)."""
        prefix, sep, number = edi_filename.rpartition('-')
        if not sep or not number.isdigit():
            return edi_filename
        return '%s-%s' % (prefix, number.zfill(8))

    # -------------------------------------------------------------------------
    # Envío
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_sign_invoices_factory_hka(self, invoice, edi_filename, edi_str):
        return self._l10n_pe_edi_sign_service_factory_hka(
            invoice.company_id, edi_filename, edi_str, invoice.l10n_latam_document_type_id.code)

    def _l10n_pe_edi_sign_service_factory_hka(self, company, edi_filename, edi_str, latam_document_type):
        """Mismo contrato que ``_l10n_pe_edi_sign_service_sunat``: lo usan
        también otros documentos (p. ej. el comprobante de retención)."""
        credentials = self._l10n_pe_edi_get_factory_hka_credentials(company)
        if credentials.get('error'):
            return credentials
        return self._l10n_pe_edi_sign_service_sunat_digiflow_common(
            company, self._l10n_pe_edi_factory_hka_filename(edi_filename), edi_str,
            credentials, latam_document_type)

    # -------------------------------------------------------------------------
    # Consulta del CDR
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_get_status_cdr_factory_hka_service(self, company, serie_folio, latam_document_type):
        credentials = self._l10n_pe_edi_get_factory_hka_credentials(company)
        if credentials.get('error'):
            return credentials
        return self._l10n_pe_edi_get_status_cdr_sunat_digiflow_service_common(
            credentials, company.vat, serie_folio, latam_document_type)

    # -------------------------------------------------------------------------
    # Comunicación de baja
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_cancel_invoices_step_1_factory_hka(self, company, invoices, void_filename, void_str):
        credentials = self._l10n_pe_edi_get_factory_hka_credentials(company)
        if credentials.get('error'):
            return credentials
        return self._l10n_pe_edi_cancel_invoices_step_1_sunat_digiflow_common(
            company, invoices, void_filename, void_str, credentials)

    def _l10n_pe_edi_cancel_invoices_step_2_factory_hka(self, company, edi_values, cdr_number):
        credentials = self._l10n_pe_edi_get_factory_hka_credentials(company)
        if credentials.get('error'):
            return credentials
        return self._l10n_pe_edi_cancel_invoices_step_2_sunat_digiflow_common(
            company, edi_values, cdr_number, credentials)
