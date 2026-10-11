# -*- coding: utf-8 -*-
"""CRE y su reversión por Factory HKA.

La emisión, el XML, el resumen de reversiones (RR), el correlativo y los
estados son comunes y viven en ``al_l10n_pe_retention``
(``l10n_pe.retention.edi.mixin``): aquí solo va lo propio del operador, el
envío por su ``billService`` (``sendBill``, ``sendSummary`` y ``getStatus``).
Al extender la clase común, lo mismo vale para los pagos y para los CRE sin
pago de Odoo."""
from odoo import models


class L10nPeRetentionEdiMixin(models.AbstractModel):
    _inherit = 'l10n_pe.retention.edi.mixin'

    def _l10n_pe_edi_sign_retention(self, edi_format, filename, edi_str):
        # Factory HKA recibe el CRE en el mismo billService que las facturas.
        if self.company_id._l10n_pe_edi_factory_hka_uses('retention'):
            return edi_format._l10n_pe_edi_sign_service_factory_hka(
                self.company_id, filename, edi_str, '20')
        return super()._l10n_pe_edi_sign_retention(edi_format, filename, edi_str)

    def _l10n_pe_edi_reversal_supported(self):
        """Con Factory HKA, la reversión es una función que se activa en los
        ajustes; si los CRE van directo a SUNAT (función de CRE apagada), se
        revierten también directo a SUNAT."""
        company = self.company_id
        if company.l10n_pe_edi_provider == 'factory_hka':
            if company.l10n_pe_edi_factory_hka_retention:
                return company._l10n_pe_edi_factory_hka_uses('reversal')
            return True
        return super()._l10n_pe_edi_reversal_supported()

    def _l10n_pe_edi_reversal_by_factory_hka(self):
        """La reversión va por HKA solo si el CRE también fue por HKA."""
        company = self.company_id
        return (company._l10n_pe_edi_factory_hka_uses('retention')
                and company._l10n_pe_edi_factory_hka_uses('reversal'))

    def _l10n_pe_edi_reversal_send(self, edi_format, filename, edi_str):
        if self._l10n_pe_edi_reversal_by_factory_hka():
            return edi_format._l10n_pe_edi_cancel_invoices_step_1_factory_hka(
                self.company_id, self, filename, edi_str)
        return super()._l10n_pe_edi_reversal_send(edi_format, filename, edi_str)

    def _l10n_pe_edi_reversal_status(self, edi_format, ticket):
        if self._l10n_pe_edi_reversal_by_factory_hka():
            return edi_format._l10n_pe_edi_cancel_invoices_step_2_factory_hka(
                self.company_id, [], ticket)
        return super()._l10n_pe_edi_reversal_status(edi_format, ticket)
