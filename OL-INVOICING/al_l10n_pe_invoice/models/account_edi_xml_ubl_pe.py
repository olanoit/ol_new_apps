# -*- coding: utf-8 -*-
from odoo import models


class AccountEdiXmlUblPe(models.AbstractModel):
    _inherit = 'account.edi.xml.ubl_pe'

    def _add_invoice_payment_terms_nodes(self, document_node, vals):
        """Forma de pago «Credito» y cuotas sin la retención del IGV cuando el
        cliente es agente de retención (R.S. 193-2020/SUNAT, numeral 2.1: el
        monto neto pendiente de pago no incluye las retenciones). Se aplica
        sobre lo que dejan el nativo y la detracción; las cuotas siguen
        sumando el neto informado. El reparto es el del comprobante impreso
        (``account.move._l10n_pe_retention_split``)."""
        super()._add_invoice_payment_terms_nodes(document_node, vals)
        invoice = vals['invoice']
        retention = invoice._l10n_pe_customer_retention()
        if not retention:
            return
        terms = document_node.get('cac:PaymentTerms') or []

        def means(term):
            return str(term.get('cbc:PaymentMeansID', {}).get('_text') or '')

        credit = next((term for term in terms
                       if means(term) == 'Credito' and 'cbc:Amount' in term), None)
        if not credit:
            return  # al contado no hay monto neto ni cuotas
        currency = invoice.currency_id
        digits = currency.decimal_places
        net = currency.round(float(credit['cbc:Amount']['_text']) - retention)
        credit['cbc:Amount']['_text'] = self.format_float(net, digits)
        cuotas = [term for term in terms if means(term).startswith('Cuota')]
        amounts = invoice._l10n_pe_retention_split(
            [float(term['cbc:Amount']['_text']) for term in cuotas])
        if cuotas:
            # las cuotas deben sumar el neto informado (redondeo en la última)
            amounts[-1] = currency.round(amounts[-1] + net - sum(amounts))
        for term, amount in zip(cuotas, amounts):
            term['cbc:Amount']['_text'] = self.format_float(amount, digits)

    def _add_document_allowance_charge_nodes(self, document_node, vals):
        """Retención del IGV del cliente agente (catálogo 53, código 62
        «Retención del IGV»; R.S. 193-2020/SUNAT): el oficial solo la informa
        si la factura lleva un impuesto de retención; aquí también cuando la
        retención se estima por el padrón (``_l10n_pe_customer_retention``),
        con el mismo importe que rebaja el neto pendiente. Nunca dos nodos 62."""
        super()._add_document_allowance_charge_nodes(document_node, vals)
        invoice = vals['invoice']
        retention = invoice._l10n_pe_customer_retention()
        if not retention:
            return
        charges = document_node.setdefault('cac:AllowanceCharge', [])
        if any(str((charge or {}).get('cbc:AllowanceChargeReasonCode', {}).get('_text')) == '62'
               for charge in charges):
            return
        currency = invoice.currency_id
        base = abs(invoice.amount_total)
        charges.append({
            'cbc:ChargeIndicator': {'_text': 'false'},
            'cbc:AllowanceChargeReasonCode': {'_text': '62'},
            'cbc:MultiplierFactorNumeric': {'_text': self.format_float(retention / base, 5)},
            'cbc:Amount': {'_text': self.format_float(retention, currency.decimal_places),
                           'currencyID': currency.name},
            'cbc:BaseAmount': {'_text': self.format_float(base, currency.decimal_places),
                               'currencyID': currency.name},
        })
