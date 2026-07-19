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
  <cbc:TotalInvoiceAmount currencyID="PEN">{total_retained}</cbc:TotalInvoiceAmount>
  <cbc:TotalPaid currencyID="PEN">{total_paid}</cbc:TotalPaid>
{documents}</Retention>
"""

CRE_DOCUMENT = """  <sac:SUNATRetentionDocumentReference>
    <cbc:ID schemeID="{doc_type}">{doc_number}</cbc:ID>
    <cbc:IssueDate>{doc_date}</cbc:IssueDate>
    <cbc:TotalInvoiceAmount currencyID="PEN">{doc_total}</cbc:TotalInvoiceAmount>
    <cac:Payment>
      <cbc:PaidAmount currencyID="PEN">{paid}</cbc:PaidAmount>
      <cbc:PaidDate>{pay_date}</cbc:PaidDate>
    </cac:Payment>
    <sac:SUNATRetentionInformation>
      <sac:SUNATRetentionAmount currencyID="PEN">{retained}</sac:SUNATRetentionAmount>
      <sac:SUNATRetentionDate>{pay_date}</sac:SUNATRetentionDate>
      <sac:SUNATNetTotalPaid currencyID="PEN">{net}</sac:SUNATNetTotalPaid>
    </sac:SUNATRetentionInformation>
  </sac:SUNATRetentionDocumentReference>
"""


class AccountPayment(models.Model):
    _inherit = 'account.payment'

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

    def action_l10n_pe_generate_cre_xml(self):
        """Genera el XML UBL del Comprobante de Retención Electrónico
        (borrador sin firma: la firma y el envío corren por el OSE)."""
        self.ensure_one()
        lines = self._l10n_pe_retention_lines()
        if not lines:
            raise UserError(self.env._(
                'El pago no tiene líneas de retención de IGV.'))
        company = self.company_id
        total_retained = sum(lines.mapped('amount'))
        docs = []
        for invoice in self.invoice_ids or self.reconciled_bill_ids:
            docs.append(CRE_DOCUMENT.format(
                doc_type=invoice.l10n_latam_document_type_id.code or '01',
                doc_number=escape(invoice.ref or invoice.name),
                doc_date=invoice.invoice_date or invoice.date,
                doc_total='%.2f' % invoice.amount_total,
                paid='%.2f' % self.amount,
                pay_date=self.date,
                retained='%.2f' % total_retained,
                net='%.2f' % (self.amount - total_retained),
            ))
        xml = CRE_TEMPLATE.format(
            number=escape(self.l10n_pe_retention_number or self.name),
            date=self.date,
            agent_ruc=escape(company.vat or ''),
            agent_name=escape(company.name),
            supplier_ruc=escape(self.partner_id.vat or ''),
            supplier_name=escape(self.partner_id.name),
            rate='%.0f' % company.l10n_pe_retention_rate,
            total_retained='%.2f' % total_retained,
            total_paid='%.2f' % self.amount,
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
