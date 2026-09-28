# -*- coding: utf-8 -*-
from odoo import models


class AccountEdiXmlUblPe(models.AbstractModel):
    _inherit = 'account.edi.xml.ubl_pe'

    def _add_invoice_payment_terms_nodes(self, document_node, vals):
        """Cuotas del XML cuando la detracción se separó en el asiento.

        El nativo toma como cuota cada línea por cobrar y además resta la
        detracción a la primera. Con el reparto, la línea de detracción es
        otra línea por cobrar: saldría como cuota y la detracción se
        restaría dos veces (o quedaría una cuota en cero), y SUNAT rechaza
        el comprobante. Las cuotas se rehacen solo con las líneas del neto.
        """
        super()._add_invoice_payment_terms_nodes(document_node, vals)
        invoice = vals['invoice']
        det_account = invoice.company_id.l10n_pe_detraction_receivable_account_id
        if not det_account:
            return
        rec_lines = invoice.line_ids.filtered(
            lambda l: l.account_type == 'asset_receivable')
        det_lines = rec_lines.filtered(lambda l: l.account_id == det_account)
        net_lines = (rec_lines - det_lines).sorted('date_maturity')
        if not det_lines or not net_lines:
            return
        terms = document_node.get('cac:PaymentTerms') or []

        def means(term):
            return str(term.get('cbc:PaymentMeansID', {}).get('_text') or '')

        credit = next((term for term in terms
                       if means(term) == 'Credito' and 'cbc:Amount' in term),
                      None)
        if not credit:
            return  # al contado no hay cuotas
        currency = invoice.currency_id
        amounts = [line.amount_currency for line in net_lines]
        # las cuotas deben sumar el neto informado en la forma de pago
        total_after_spot = float(credit['cbc:Amount']['_text'])
        amounts[0] += currency.round(total_after_spot - sum(amounts))
        cuotas = [{
            'cbc:ID': {'_text': 'FormaPago'},
            'cbc:PaymentMeansID': {'_text': f'Cuota{index:03d}'},
            'cbc:Amount': {
                '_text': self.format_float(amount, currency.decimal_places),
                'currencyID': currency.name,
            },
            'cbc:PaymentDueDate': {'_text': line.date_maturity},
        } for index, (line, amount) in enumerate(zip(net_lines, amounts), start=1)]
        document_node['cac:PaymentTerms'] = [
            term for term in terms if not means(term).startswith('Cuota')
        ] + cuotas
