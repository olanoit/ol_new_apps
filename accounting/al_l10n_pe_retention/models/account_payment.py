# -*- coding: utf-8 -*-
from markupsafe import escape

from odoo import api, fields, models
from odoo.exceptions import UserError

CRE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Retention xmlns="urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1">
  <cbc:UBLVersionID>2.0</cbc:UBLVersionID>
  <cbc:CustomizationID>1.0</cbc:CustomizationID>
  <cbc:ID>{number}</cbc:ID>
  <cbc:IssueDate>{date}</cbc:IssueDate>
  <cac:AgentParty>
    <cac:PartyIdentification><cbc:ID schemeID="6">{agent_ruc}</cbc:ID></cac:PartyIdentification>
    <cac:PartyLegalEntity><cbc:RegistrationName>{agent_name}</cbc:RegistrationName></cac:PartyLegalEntity>
  </cac:AgentParty>
  <cac:ReceiverParty>
    <cac:PartyIdentification><cbc:ID schemeID="6">{supplier_ruc}</cbc:ID></cac:PartyIdentification>
    <cac:PartyLegalEntity><cbc:RegistrationName>{supplier_name}</cbc:RegistrationName></cac:PartyLegalEntity>
  </cac:ReceiverParty>
  <sac:SUNATRetentionSystemCode>01</sac:SUNATRetentionSystemCode>
  <sac:SUNATRetentionPercent>{rate}</sac:SUNATRetentionPercent>
  <cbc:TotalInvoiceAmount currencyID="{pen}">{total_retained}</cbc:TotalInvoiceAmount>
  <cbc:TotalPaid currencyID="{pen}">{total_paid}</cbc:TotalPaid>
{documents}</Retention>
"""

# Importe del comprobante y del pago en su moneda; retención y neto siempre
# en soles, con el tipo de cambio cuando el comprobante es en otra moneda.
CRE_DOCUMENT = """  <sac:SUNATRetentionDocumentReference>
    <cbc:ID schemeID="{doc_type}">{doc_number}</cbc:ID>
    <cbc:IssueDate>{doc_date}</cbc:IssueDate>
    <cbc:TotalInvoiceAmount currencyID="{doc_currency}">{doc_total}</cbc:TotalInvoiceAmount>
    <cac:Payment>
      <cbc:PaidAmount currencyID="{doc_currency}">{paid}</cbc:PaidAmount>
      <cbc:PaidDate>{pay_date}</cbc:PaidDate>
    </cac:Payment>
    <sac:SUNATRetentionInformation>
      <sac:SUNATRetentionAmount currencyID="{pen}">{retained}</sac:SUNATRetentionAmount>
      <sac:SUNATRetentionDate>{pay_date}</sac:SUNATRetentionDate>
      <sac:SUNATNetTotalPaid currencyID="{pen}">{net}</sac:SUNATNetTotalPaid>
{exchange_rate}    </sac:SUNATRetentionInformation>
  </sac:SUNATRetentionDocumentReference>
"""

CRE_EXCHANGE_RATE = """      <cac:ExchangeRate>
        <cbc:SourceCurrencyCode>{source}</cbc:SourceCurrencyCode>
        <cbc:TargetCurrencyCode>{pen}</cbc:TargetCurrencyCode>
        <cbc:CalculationRate>{rate}</cbc:CalculationRate>
        <cbc:Date>{date}</cbc:Date>
      </cac:ExchangeRate>
"""


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # Etiqueta en español del marco nativo
    withholding_line_ids = fields.One2many(string='Retenciones')

    l10n_pe_retention_number = fields.Char(
        string='Nº comprobante de retención',
        compute='_compute_l10n_pe_retention_number', store=True)

    def _l10n_pe_retention_lines(self):
        return self.withholding_line_ids.filtered(
            lambda l: l.tax_id == self.company_id.l10n_pe_retention_tax_id)

    @api.depends('withholding_line_ids.name')
    def _compute_l10n_pe_retention_number(self):
        for payment in self:
            payment.l10n_pe_retention_number = ', '.join(
                n for n in payment._l10n_pe_retention_lines().mapped('name')
                if n) or False

    def action_post(self):
        """El comprobante de retención se numera al emitir el pago (el
        marco nativo lo haría recién al generar el asiento con el
        extracto, tarde para el flujo SUNAT)."""
        res = super().action_post()
        for payment in self:
            for line in payment._l10n_pe_retention_lines().filtered(
                    lambda l: not l.name and l.withholding_sequence_id):
                line.name = line.withholding_sequence_id.next_by_id()
        return res

    def _l10n_pe_retention_documents(self):
        """Reparto del pago y de la retención entre sus comprobantes.

        Devuelve una lista (una entrada por factura) con importes en soles
        (moneda de la compañía) y, para el XML, en la moneda del
        comprobante. El pagado de cada factura sale de la conciliación si
        el pago ya tiene asiento; si no (Odoo 19 no lo genera hasta
        conciliar el extracto), se reparte en proporción al total de cada
        factura. La retención se reparte en proporción a lo pagado.
        """
        self.ensure_one()
        company = self.company_id
        company_currency = company.currency_id
        invoices = self.invoice_ids or self.reconciled_bill_ids
        if not invoices:
            return []
        # importe bruto del pago (antes de retener) en soles; el signado de
        # la compañía sería el neto cuando el pago ya tiene asiento
        total_paid = company_currency.round(self.currency_id._convert(
            self.amount, company_currency, company, self.date))
        total_retained = company_currency.round(sum(
            self.currency_id._convert(abs(line.amount), company_currency, company,
                                      self.date)
            for line in self._l10n_pe_retention_lines()))

        paid_by_invoice = {}
        if self.move_id:
            payment_lines = self.move_id.line_ids
            for invoice in invoices:
                partials = (invoice.line_ids.matched_debit_ids
                            | invoice.line_ids.matched_credit_ids)
                paid_by_invoice[invoice] = sum(
                    partial.amount for partial in partials
                    if partial.debit_move_id in payment_lines
                    or partial.credit_move_id in payment_lines)
        if not any(paid_by_invoice.values()):
            weights = {inv: abs(inv.amount_total_signed) for inv in invoices}
            total_weight = sum(weights.values()) or 1.0
            paid_by_invoice = {
                inv: total_paid * weight / total_weight
                for inv, weight in weights.items()}

        documents = []
        retained_left = total_retained
        paid_sum = sum(paid_by_invoice.values()) or 1.0
        for index, invoice in enumerate(invoices):
            paid = company_currency.round(paid_by_invoice[invoice])
            if index == len(invoices) - 1:
                retained = retained_left  # el redondeo cae en el último
            else:
                retained = company_currency.round(
                    total_retained * paid_by_invoice[invoice] / paid_sum)
                retained_left -= retained
            doc_currency = invoice.currency_id
            documents.append({
                'invoice': invoice,
                'currency': doc_currency,
                'paid': paid,
                'retained': retained,
                'net': paid - retained,
                'doc_total': invoice.amount_total,
                'doc_paid': company_currency._convert(
                    paid, doc_currency, company, self.date),
                'rate': self.env['res.currency']._get_conversion_rate(
                    doc_currency, company_currency, company, self.date),
            })
        return documents

    def action_l10n_pe_generate_cre_xml(self):
        """Genera el XML UBL del Comprobante de Retención Electrónico
        (borrador sin firma: la firma y el envío corren por el OSE)."""
        self.ensure_one()
        lines = self._l10n_pe_retention_lines()
        if not lines:
            raise UserError(self.env._(
                'El pago no tiene líneas de retención de IGV.'))
        company = self.company_id
        company_currency = company.currency_id
        pen = company_currency.name
        documents = self._l10n_pe_retention_documents()
        docs = []
        for doc in documents:
            invoice = doc['invoice']
            exchange_rate = ''
            if doc['currency'] != company_currency:
                exchange_rate = CRE_EXCHANGE_RATE.format(
                    source=doc['currency'].name, pen=pen,
                    rate='%.6f' % doc['rate'], date=self.date)
            docs.append(CRE_DOCUMENT.format(
                doc_type=invoice.l10n_latam_document_type_id.code or '01',
                doc_number=escape(invoice.ref or invoice.name),
                doc_date=invoice.invoice_date or invoice.date,
                doc_currency=doc['currency'].name,
                doc_total='%.2f' % doc['doc_total'],
                paid='%.2f' % doc['doc_paid'],
                pay_date=self.date,
                pen=pen,
                retained='%.2f' % doc['retained'],
                net='%.2f' % doc['net'],
                exchange_rate=exchange_rate,
            ))
        xml = CRE_TEMPLATE.format(
            number=escape(self.l10n_pe_retention_number or self.name),
            date=self.date,
            agent_ruc=escape(company.vat or ''),
            agent_name=escape(company.name),
            supplier_ruc=escape(self.partner_id.vat or ''),
            supplier_name=escape(self.partner_id.name),
            rate='%.0f' % company.l10n_pe_retention_rate,
            pen=pen,
            total_retained='%.2f' % sum(d['retained'] for d in documents),
            total_paid='%.2f' % sum(d['paid'] for d in documents),
            documents=''.join(docs),
        )
        filename = '%s-20-%s.xml' % (
            company.vat or 'RUC',
            (self.l10n_pe_retention_number or self.name).replace('/', '-'))
        attachment = self.env['ir.attachment'].create({
            'name': filename, 'res_model': self._name, 'res_id': self.id,
            'raw': xml.encode(), 'mimetype': 'application/xml'})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'self',
        }
