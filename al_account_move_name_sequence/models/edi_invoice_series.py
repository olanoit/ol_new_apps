# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Series SUNAT: letra según el tipo + 3 alfanuméricos (F001, FE01, B001...)
SERIE_REGEX = {
    '01': re.compile(r'^F[A-Z0-9]{3}$'),
    '03': re.compile(r'^[BE][A-Z0-9]{3}$'),
}


class EdiInvoiceSeries(models.Model):
    """Serie de comprobante electrónico (CPE).

    Cada registro agrupa una serie de emisión (F001, B001…) con sus series
    rectificativas de nota de crédito y débito. Al publicar se crean las
    tres ir.sequence (no_gap, relleno 8) en la compañía de la serie. Idea
    tomada del modelo homónimo de pe_edi_update, integrada al mecanismo
    opt-in de este módulo: la serie solo numera en diarios con «Numerar
    por secuencia» activo.
    """
    _name = 'edi.invoice.series'
    _description = 'Serie de comprobante electrónico'
    _inherit = ['mail.thread']
    _rec_name = 'name'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company)
    l10n_latam_document_type_id = fields.Many2one(
        'l10n_latam.document.type', string='Tipo de documento',
        domain=[('code', 'in', ('01', '03'))], required=True, copy=False)
    edi_type_code = fields.Char(
        related='l10n_latam_document_type_id.code', string='Código')
    name = fields.Char('Serie', size=4, required=True, tracking=True)
    name_nc = fields.Char(
        'Serie nota de crédito', size=4, required=True,
        help='Serie rectificativa usada por las notas de crédito de los '
             'comprobantes emitidos con esta serie (p. ej. FC01).')
    name_nd = fields.Char(
        'Serie nota de débito', size=4, required=True,
        help='Serie usada por las notas de débito (p. ej. FD01).')
    invoice_seq_id = fields.Many2one(
        'ir.sequence', string='Secuencia del comprobante', readonly=True,
        copy=False)
    credit_note_seq_id = fields.Many2one(
        'ir.sequence', string='Secuencia de nota de crédito', readonly=True,
        copy=False)
    debit_note_seq_id = fields.Many2one(
        'ir.sequence', string='Secuencia de nota de débito', readonly=True,
        copy=False)
    state = fields.Selection(
        [('draft', 'Borrador'),
         ('publish', 'Publicada'),
         ('canceled', 'Inhabilitada')],
        string='Estado', default='draft', tracking=True)
    invoice_count = fields.Integer(
        string='Comprobantes', compute='_compute_invoice_count')

    def _compute_invoice_count(self):
        counts = dict(self.env['account.move']._read_group(
            [('edi_series_id', 'in', self.ids)],
            groupby=['edi_series_id'], aggregates=['__count']))
        for serie in self:
            serie.invoice_count = counts.get(serie, 0)

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'name': self.env._('Comprobantes de la serie %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('edi_series_id', '=', self.id)],
            'context': {'create': False},
        }

    _serie_company_uniq = models.Constraint(
        'UNIQUE(name, company_id)',
        'Ya existe una serie con ese nombre en la compañía.')

    @api.onchange('name')
    def _onchange_name(self):
        """Propone las series rectificativas a partir de la principal:
        F001 → FC01 (NC) y FD01 (ND); B001 → BC01/BD01."""
        if self.name and len(self.name) == 4:
            letter, tail = self.name[0], self.name[2:]
            if not self.name_nc:
                self.name_nc = f'{letter}C{tail}'
            if not self.name_nd:
                self.name_nd = f'{letter}D{tail}'

    @api.constrains('name', 'l10n_latam_document_type_id')
    def _check_serie_format(self):
        for serie in self:
            regex = SERIE_REGEX.get(serie.edi_type_code)
            if regex and serie.name and not regex.match(serie.name):
                raise ValidationError(self.env._(
                    'La serie «%(serie)s» no es válida para %(doc)s: debe '
                    'ser la letra del tipo (%(letras)s) seguida de 3 '
                    'caracteres alfanuméricos, p. ej. %(ejemplo)s.',
                    serie=serie.name,
                    doc=serie.l10n_latam_document_type_id.name,
                    letras='F' if serie.edi_type_code == '01' else 'B/E',
                    ejemplo='F001' if serie.edi_type_code == '01' else 'B001'))

    def _create_sequence(self, serie_name, edi_type):
        self.ensure_one()
        return self.env['ir.sequence'].sudo().create({
            'name': f'CPE/{edi_type}/{serie_name}',
            'implementation': 'no_gap',
            'prefix': f'{serie_name}-',
            'padding': 8,
            'use_date_range': False,
            'company_id': self.company_id.id,
        })

    def action_publish(self):
        for serie in self:
            if not serie.invoice_seq_id:
                serie.invoice_seq_id = serie._create_sequence(
                    serie.name, serie.edi_type_code)
            if not serie.credit_note_seq_id:
                serie.credit_note_seq_id = serie._create_sequence(
                    serie.name_nc, '07')
            if not serie.debit_note_seq_id:
                serie.debit_note_seq_id = serie._create_sequence(
                    serie.name_nd, '08')
            serie.state = 'publish'

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_draft(self):
        self.write({'state': 'draft'})
