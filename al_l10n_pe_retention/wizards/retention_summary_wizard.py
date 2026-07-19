# -*- coding: utf-8 -*-
import base64
import calendar
from datetime import date

from odoo import fields, models


class L10nPeRetentionSummaryWizard(models.TransientModel):
    """Resumen mensual de retenciones efectuadas (soporte del F.V. 626):
    una línea por retención con proveedor, comprobante, pago y monto."""
    _name = 'l10n_pe.retention.summary.wizard'
    _description = 'Resumen de retenciones IGV (F. 626)'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    year = fields.Integer(
        required=True, string='Ejercicio',
        default=lambda self: fields.Date.context_today(self).year)
    month = fields.Selection(
        [('%02d' % m, '%02d' % m) for m in range(1, 13)],
        required=True, string='Mes',
        default=lambda self: '%02d' % fields.Date.context_today(self).month)
    file_name = fields.Char(readonly=True)
    file_data = fields.Binary(readonly=True, string='Archivo')

    def action_export(self):
        self.ensure_one()
        month = int(self.month)
        date_from = date(self.year, month, 1)
        date_to = date(self.year, month,
                       calendar.monthrange(self.year, month)[1])
        tax = self.company_id.l10n_pe_retention_tax_id
        lines = self.env['account.payment.withholding.line'].search([
            ('payment_id.state', 'in', ('in_process', 'paid')),
            ('payment_id.date', '>=', date_from),
            ('payment_id.date', '<=', date_to),
            ('payment_id.company_id', '=', self.company_id.id),
            ('tax_id', '=', tax.id),
        ]) if tax else self.env['account.payment.withholding.line']
        rows = []
        for line in lines:
            payment = line.payment_id
            invoice = (payment.invoice_ids or payment.reconciled_bill_ids)[:1]
            rows.append('|'.join([
                payment.partner_id.vat or '',
                (payment.partner_id.name or '')[:100],
                invoice.ref or invoice.name or '',
                str(payment.date),
                '%.2f' % payment.amount,
                line.name or '',
                '%.2f' % abs(line.amount),
            ]))
        content = ('\r\n'.join(rows) + '\r\n') if rows else b''.decode()
        self.write({
            'file_name': 'retenciones_626_%04d%s.txt' % (
                self.year, self.month),
            'file_data': base64.b64encode(content.encode()),
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name,
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }
