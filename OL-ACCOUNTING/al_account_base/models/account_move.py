# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Glosa peruana (descripción del asiento para el PLE / libros).
    l10n_pe_gloss = fields.Char(string='Glosa', copy=False)

    def l10n_pe_is_pe(self):
        """Es un comprobante de una compañía peruana."""
        self.ensure_one()
        return self.country_code == 'PE'

    def _l10n_pe_customer_retention(self):
        """IGV que retendrá el cliente agente de retención sobre esta venta, en
        la moneda del comprobante (R.S. 037-2002/SUNAT): el 3 % del total si
        el comprobante supera S/ 700. No se retiene si la operación está
        sujeta a detracción, si no tiene IGV, si el cliente no es agente o si
        la compañía es agente de retención o buen contribuyente (art. 5).

        El «Monto neto pendiente de pago» de la factura no incluye esta
        retención (R.S. 193-2020/SUNAT, numeral 2.1): lo usan el comprobante
        impreso, las cuotas del XML y el factoring. Los datos del padrón, de
        la detracción y de la tasa vienen de otros módulos de la suite si
        están instalados (sin ellos no hay retención que estimar)."""
        self.ensure_one()
        if self.move_type != 'out_invoice' or self.state == 'cancel':
            return 0.0
        doc_type = 'l10n_latam_document_type_id' in self._fields and \
            self.l10n_latam_document_type_id.code
        if doc_type and doc_type not in ('01', '08'):
            return 0.0  # facturas y notas de débito
        company = self.company_id
        if not getattr(self.commercial_partner_id, 'is_retention_agent', False):
            return 0.0
        if getattr(company, 'l10n_pe_retention_agent', False) \
                or getattr(company.partner_id, 'is_retention_agent', False) \
                or getattr(company.partner_id, 'is_good_taxpayer', False):
            return 0.0
        if self.currency_id.is_zero(self.amount_tax):
            return 0.0
        if 'l10n_pe_detraction_applies' in self._fields and self.l10n_pe_detraction_applies:
            return 0.0
        if hasattr(self, '_l10n_pe_edi_get_spot') and self._l10n_pe_edi_get_spot():
            return 0.0
        minimum = getattr(company, 'l10n_pe_retention_min_amount', 0.0) or 700.0
        if company.currency_id.compare_amounts(abs(self.amount_total_signed), minimum) <= 0:
            return 0.0
        rate = getattr(company, 'l10n_pe_retention_rate', 0.0) or 3.0
        return self.currency_id.round(abs(self.amount_total) * rate / 100.0)

    def _l10n_pe_retention_split(self, amounts):
        """Reparte la retención del cliente entre las cuotas (en proporción a
        cada una; el redondeo cae en la última) y devuelve las cuotas netas.
        El comprobante impreso y el XML usan este mismo reparto."""
        self.ensure_one()
        retention = self._l10n_pe_customer_retention()
        total = sum(amounts)
        if not retention or not amounts or self.currency_id.is_zero(total):
            return list(amounts)
        shares = [self.currency_id.round(retention * amount / total) for amount in amounts[:-1]]
        shares.append(self.currency_id.round(retention - sum(shares)))
        return [self.currency_id.round(amount - share) for amount, share in zip(amounts, shares)]
