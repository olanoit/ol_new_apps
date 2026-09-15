# -*- coding: utf-8 -*-
import base64
import calendar
from datetime import date

from odoo import _, fields, models
from odoo.exceptions import UserError


def _previous_month(today):
    """El 626 se presenta por el mes anterior: es el periodo por defecto."""
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


class L10nPeRetentionSummaryWizard(models.TransientModel):
    """Resumen mensual de retenciones efectuadas (soporte del F.V. 626):
    una línea por retención con proveedor, comprobante, pago y monto."""
    _name = 'l10n_pe.retention.summary.wizard'
    _description = 'Resumen de retenciones IGV (F. 626)'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    year = fields.Integer(
        required=True, string='Ejercicio',
        default=lambda self: _previous_month(
            fields.Date.context_today(self))[0])
    month = fields.Selection(
        [('%02d' % m, '%02d' % m) for m in range(1, 13)],
        required=True, string='Mes',
        default=lambda self: '%02d' % _previous_month(
            fields.Date.context_today(self))[1])
    file_name = fields.Char(readonly=True)
    file_data = fields.Binary(readonly=True, string='Archivo')
    retention_count = fields.Integer(string='Retenciones', readonly=True)
    retention_total = fields.Float(
        string='Total retenido', digits=(16, 2), readonly=True)

    def action_export(self):
        self.ensure_one()
        month = int(self.month)
        date_from = date(self.year, month, 1)
        date_to = date(self.year, month,
                       calendar.monthrange(self.year, month)[1])
        tax = self.company_id.l10n_pe_retention_tax_id
        if not tax:
            raise UserError(_(
                '%(company)s no tiene configurado el impuesto de retención '
                'del IGV (Ajustes ▸ Perú ▸ Retenciones IGV).',
                company=self.company_id.display_name))
        lines = self.env['account.payment.withholding.line'].search([
            ('payment_id.state', 'in', ('in_process', 'paid')),
            ('payment_id.date', '>=', date_from),
            ('payment_id.date', '<=', date_to),
            ('payment_id.company_id', '=', self.company_id.id),
            ('tax_id', '=', tax.id),
        ])
        if not lines:
            raise UserError(_(
                'No hay retenciones efectuadas en %(month)s/%(year)s para '
                '%(company)s: no hay nada que declarar en ese periodo. '
                'Revise el mes o los pagos en Perú ▸ Retenciones IGV ▸ '
                'Retenciones efectuadas.',
                month=self.month, year=self.year,
                company=self.company_id.display_name))
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
        content = '\r\n'.join(rows) + '\r\n'
        self.write({
            'file_name': 'retenciones_626_%04d%s.txt' % (
                self.year, self.month),
            'file_data': base64.b64encode(content.encode()),
            'retention_count': len(lines),
            'retention_total': sum(abs(line.amount) for line in lines),
        })
        return {
            'type': 'ir.actions.act_window', 'name': _('Resumen de retenciones (626)'),
            'res_model': self._name,
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }
