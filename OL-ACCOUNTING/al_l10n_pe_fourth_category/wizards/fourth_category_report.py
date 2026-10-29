# -*- coding: utf-8 -*-
"""Recibos por honorarios pagados en el mes y su retención de 4.ª, para la
PLAME (PDT 601): el agente informa a los prestadores a quienes pagó o acreditó
rentas de cuarta categoría en el periodo y declara las retenciones.

El archivo de importación ``.4ta`` sigue la estructura 20 «Prestador de
servicios con rentas de cuarta categoría – Detalle de comprobantes» del anexo
3 de la planilla electrónica (R.S. 235-2013/SUNAT, longitud del monto
ampliada por la R.S. 028-2018/SUNAT): campos separados por «|», fechas
dd/mm/aaaa y montos con punto decimal y dos decimales.
"""
import calendar
from datetime import date

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes

MONTHS = [(str(m), name) for m, name in enumerate(
    ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
     'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'), start=1)]
# Tabla 3 de la PLAME por código de identificación SUNAT (catálogo 6).
PLAME_DOC_TYPES = {'6': '06', '1': '01', '4': '04', '7': '07'}


class FourthCategoryReport(models.TransientModel):
    _name = 'l10n_pe.fourth.category.report'
    _description = 'Retenciones de 4.ª categoría del mes'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    year = fields.Integer(
        string='Año', required=True, default=lambda self: fields.Date.context_today(self).year)
    month = fields.Selection(
        MONTHS, string='Mes', required=True,
        default=lambda self: str(fields.Date.context_today(self).month))
    line_ids = fields.One2many(
        'l10n_pe.fourth.category.report.line', 'report_id', string='Recibos pagados')
    amount_total = fields.Monetary(
        string='Total de honorarios', compute='_compute_totals', currency_field='currency_id')
    amount_withheld = fields.Monetary(
        string='Total retenido', compute='_compute_totals', currency_field='currency_id',
        help='Retenciones de 4.ª categoría a declarar y pagar en la PLAME del periodo.')
    file = fields.Binary(string='Archivo', readonly=True, attachment=False)
    filename = fields.Char(string='Nombre del archivo', readonly=True)

    @api.depends('line_ids.amount_total', 'line_ids.amount_withheld')
    def _compute_totals(self):
        for report in self:
            report.amount_total = sum(report.line_ids.mapped('amount_total'))
            report.amount_withheld = sum(report.line_ids.mapped('amount_withheld'))

    def _period(self):
        self.ensure_one()
        month = int(self.month)
        return date(self.year, month, 1), date(self.year, month,
                                               calendar.monthrange(self.year, month)[1])

    def _paid_receipts(self):
        """Recibos por honorarios publicados de la compañía cuyo pago quedó
        completo dentro del periodo."""
        self.ensure_one()
        start, end = self._period()
        receipts = self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('l10n_pe_fourth_category_receipt', '=', True),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('paid', 'in_payment')),
            ('invoice_date', '<=', end),
        ], order='invoice_date, id')
        result = []
        for move in receipts:
            paid = move._l10n_pe_fourth_category_payment_date()
            if paid and start <= paid <= end:
                result.append((move, paid))
        return result

    def action_compute(self):
        self.ensure_one()
        commands = [Command.clear()]
        for move, paid in self._paid_receipts():
            commands.append(Command.create({
                'move_id': move.id,
                'date_payment': paid,
                'amount_total': move._l10n_pe_fourth_category_gross(),
                'amount_withheld': move.l10n_pe_fourth_category_amount,
            }))
        self.write({'line_ids': commands, 'file': False, 'filename': False})
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new', 'name': self.env._('Retenciones de 4.ª categoría'),
        }

    def _txt_lines(self):
        rows = []
        for line in self.line_ids:
            partner = line.move_id.partner_id.commercial_partner_id
            code = partner.l10n_latam_identification_type_id.l10n_pe_vat_code
            fields_ = [
                PLAME_DOC_TYPES.get(code, '06'),
                (partner.vat or '').strip(),
                'R',
                line.series or '',
                line.number or '',
                '%.2f' % line.amount_total,
                line.move_id.invoice_date.strftime('%d/%m/%Y'),
                line.date_payment.strftime('%d/%m/%Y'),
                '1' if line.amount_withheld else '0',
                # Régimen pensionario del prestador: sin retención / no aplica.
                '3',
                '',
            ]
            rows.append('|'.join(fields_) + '|')
        return rows

    def action_export_txt(self):
        """Archivo .4ta para importar en el PDT PLAME (formulario 0601)."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(self.env._('No hay recibos pagados en el periodo: pulse «Calcular».'))
        missing = self.line_ids.filtered(lambda l: not l.move_id.partner_id.commercial_partner_id.vat)
        if missing:
            raise UserError(self.env._(
                'Estos prestadores no tienen número de documento: %s',
                ', '.join(missing.mapped('partner_id.display_name'))))
        ruc = (self.company_id.vat or '').strip()
        self.filename = '0601%04d%02d%s.4ta' % (self.year, int(self.month), ruc)
        self.file = BinaryBytes(('\r\n'.join(self._txt_lines()) + '\r\n').encode('utf-8'))
        return self._reopen()

    def action_view_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'name': self.env._('Recibos por honorarios pagados'),
            'view_mode': 'list,form', 'domain': [('id', 'in', self.line_ids.move_id.ids)],
        }


class FourthCategoryReportLine(models.TransientModel):
    _name = 'l10n_pe.fourth.category.report.line'
    _description = 'Recibo por honorarios del reporte de 4.ª'
    _order = 'date_payment, id'

    report_id = fields.Many2one(
        'l10n_pe.fourth.category.report', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='report_id.currency_id', string='Moneda')
    move_id = fields.Many2one('account.move', string='Recibo', required=True, readonly=True)
    partner_id = fields.Many2one(related='move_id.partner_id', string='Prestador')
    partner_vat = fields.Char(related='move_id.partner_id.vat', string='Documento')
    series = fields.Char(string='Serie', compute='_compute_document')
    number = fields.Char(string='Número', compute='_compute_document')
    date_issue = fields.Date(related='move_id.invoice_date', string='Emisión')
    date_payment = fields.Date(string='Pago', readonly=True)
    amount_total = fields.Monetary(string='Honorarios', readonly=True, currency_field='currency_id')
    amount_withheld = fields.Monetary(string='Retención', readonly=True, currency_field='currency_id')
    status = fields.Selection(related='move_id.l10n_pe_fourth_category_status', string='Estado')

    @api.depends('move_id.l10n_latam_document_number', 'move_id.ref')
    def _compute_document(self):
        for line in self:
            number = line.move_id.l10n_latam_document_number or line.move_id.ref or ''
            series, _sep, correlative = number.rpartition('-')
            line.series = series[-4:] if series else ''
            line.number = (correlative or number).lstrip('0')[-8:] or '0'
