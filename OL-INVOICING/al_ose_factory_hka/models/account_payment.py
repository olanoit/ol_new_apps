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

    def _l10n_pe_edi_hka_context(self, function):
        """Por HKA si la compañía lo usa para esta función; si no, directo a
        SUNAT con la clave SOL."""
        if self.company_id._l10n_pe_edi_factory_hka_uses(function):
            return self
        return self.with_context(l10n_pe_edi_direct_sunat=True)

    def _l10n_pe_edi_sign_retention(self, filename, edi_str):
        # Factory HKA recibe el CRE en el mismo billService que las facturas
        # (y el comprobante de percepción, tipo 40, de al_l10n_pe_perception),
        # con el número en 8 dígitos.
        if self.company_id._l10n_pe_edi_factory_hka_uses('retention'):
            prefix, sep, number = filename.rpartition('-')
            if sep and number.isdigit():
                filename = '%s-%s' % (prefix, number.zfill(8))
        return super(L10nPeRetentionEdiMixin, self._l10n_pe_edi_hka_context('retention')) \
            ._l10n_pe_edi_sign_retention(filename, edi_str)

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

    def _l10n_pe_edi_reversal_send(self, filename, edi_str):
        records = self if self._l10n_pe_edi_reversal_by_factory_hka() \
            else self.with_context(l10n_pe_edi_direct_sunat=True)
        return super(L10nPeRetentionEdiMixin, records)._l10n_pe_edi_reversal_send(filename, edi_str)

    def _l10n_pe_edi_reversal_status(self, ticket):
        records = self if self._l10n_pe_edi_reversal_by_factory_hka() \
            else self.with_context(l10n_pe_edi_direct_sunat=True)
        return super(L10nPeRetentionEdiMixin, records)._l10n_pe_edi_reversal_status(ticket)
