# -*- coding: utf-8 -*-
"""Depósito masivo de detracciones en el Banco de la Nación.

Genera el archivo de ancho fijo que acepta el banco para pagar muchas
detracciones de una vez, en las dos modalidades del instructivo oficial:
como **adquiriente** (deposito en las cuentas de mis proveedores) o como
**proveedor** (deposito en mi propia cuenta lo retenido por mis clientes).

Estructura en ``services/bn_txt.py``.
"""
import base64
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import bn_txt

# Tipos de comprobante admitidos por el banco (tabla 5.6): factura, boleta y
# guía de remisión. Las notas de débito se informan como factura.
BN_INVOICE_TYPES = {'01': '01', '03': '03', '08': '01', '09': '09'}
BN_DEFAULT_INVOICE_TYPE = '01'


class L10nPeDetractionTxtWizard(models.TransientModel):
    _name = 'l10n_pe.detraction.txt.wizard'
    _description = 'Depósito masivo de detracciones (Banco de la Nación)'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    mode = fields.Selection(
        [('acquirer', 'Como adquiriente — deposito a mis proveedores'),
         ('supplier', 'Como proveedor — deposito en mi propia cuenta')],
        string='Modalidad', default='acquirer', required=True)
    batch_number = fields.Char(
        string='Nº de lote', required=True,
        default=lambda self: self._default_batch_number(),
        help='Formato AANNNN: los dos primeros dígitos son el año y los '
             'cuatro restantes el correlativo del envío. No puede repetirse '
             'para la misma empresa.')
    # Sin ``size``: un lote de más dígitos debe avisar al usuario, no
    # recortarse en silencio — el banco rechaza el envío si el número no
    # corresponde al correlativo que la empresa lleva.
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    move_ids = fields.Many2many(
        'account.move', string='Comprobantes',
        domain="[('l10n_pe_detraction_applies', '=', True)]")
    file_name = fields.Char(readonly=True)
    file_data = fields.Binary(string='Archivo', readonly=True)
    excluded_html = fields.Html(string='Excluidos', readonly=True)

    # ------------------------------------------------------------------
    # Valores por defecto
    # ------------------------------------------------------------------
    @api.model
    def _default_batch_number(self):
        """Propone AANNNN con el correlativo siguiente del año en curso."""
        year = fields.Date.context_today(self).strftime('%y')
        return '%s0001' % year

    @api.constrains('batch_number')
    def _check_batch_number(self):
        for wizard in self:
            if not re.fullmatch(r'\d{6}', wizard.batch_number or ''):
                raise UserError(_(
                    'El número de lote debe tener 6 dígitos con el formato '
                    'AANNNN (por ejemplo 260001).'))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and \
                    wizard.date_to < wizard.date_from:
                raise UserError(_('La fecha «Hasta» no puede ser anterior a '
                                  '«Desde».'))

    # ------------------------------------------------------------------
    # Selección de comprobantes
    # ------------------------------------------------------------------
    def _candidate_moves(self):
        """Comprobantes con detracción del periodo, si no se eligieron a mano."""
        self.ensure_one()
        if self.move_ids:
            return self.move_ids
        move_types = (('in_invoice',) if self.mode == 'acquirer'
                      else ('out_invoice',))
        return self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('l10n_pe_detraction_applies', '=', True),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
        ], order='invoice_date, name')

    def _counterparty(self, move):
        """El titular de la cuenta de detracciones en cada modalidad."""
        return (move.partner_id.commercial_partner_id if self.mode == 'acquirer'
                else self.company_id.partner_id)

    def _check_move(self, move):
        """Motivo por el que un comprobante no puede incluirse, o ``None``."""
        partner = self._counterparty(move)
        if not move.l10n_pe_detraction_type_id:
            return _('sin tipo de detracción (catálogo 54)')
        if not move.l10n_pe_detraction_amount:
            return _('el monto de detracción es cero')
        if not (partner.vat or '').strip():
            return _('%s no tiene RUC', partner.display_name)
        if not (partner.l10n_pe_detraction_account or '').strip():
            return _('%s no tiene cuenta de detracciones del Banco de la '
                     'Nación', partner.display_name)
        if not move.invoice_date:
            return _('sin fecha de emisión')
        return None

    # ------------------------------------------------------------------
    # Construcción del archivo
    # ------------------------------------------------------------------
    def _invoice_parts(self, move):
        """(tipo de comprobante, serie, número) según las tablas 5.6 y 5.7."""
        code = move.l10n_latam_document_type_id.code or ''
        bn_type = BN_INVOICE_TYPES.get(code, BN_DEFAULT_INVOICE_TYPE)
        name = (move.l10n_latam_document_number or move.name or '').strip()
        name = name.replace(' ', '')
        serie, _sep, folio = name.partition('-')
        return bn_type, serie[-4:], folio

    def _detail_line(self, move):
        partner = self._counterparty(move)
        bn_type, serie, folio = self._invoice_parts(move)
        return bn_txt.build_detail(
            doc_type=bn_txt.DOC_TYPE_RUC,
            vat=partner.vat,
            # El instructivo pide dejar el nombre en blanco: el banco lo
            # recupera del RUC.
            name='',
            service_code=move.l10n_pe_detraction_type_id.code,
            bank_account=partner.l10n_pe_detraction_account,
            deposit=move.l10n_pe_detraction_amount,
            operation_type=move.l10n_pe_detraction_operation_type or '01',
            tax_period=bn_txt.period(move.invoice_date),
            invoice_type=bn_type,
            invoice_serie=serie,
            invoice_number=folio,
        )

    def action_generate(self):
        self.ensure_one()
        moves = self._candidate_moves()
        if not moves:
            raise UserError(_(
                'No hay comprobantes con detracción en el periodo indicado.'))

        included, excluded = self.env['account.move'], []
        for move in moves:
            reason = self._check_move(move)
            if reason:
                excluded.append((move, reason))
            else:
                included |= move

        if not included:
            raise UserError(_(
                'Ningún comprobante reúne las condiciones para el depósito '
                'masivo. Revise el detalle de exclusiones.'))

        details = [self._detail_line(move) for move in included]
        total = sum(included.mapped('l10n_pe_detraction_amount'))
        depositor = (self.company_id.partner_id if self.mode == 'acquirer'
                     else self.company_id.partner_id)
        header = bn_txt.build_header(
            master=(bn_txt.MASTER_ACQUIRER if self.mode == 'acquirer'
                    else bn_txt.MASTER_SUPPLIER),
            vat=depositor.vat,
            name=depositor.name,
            batch_number=self.batch_number,
            total=total,
        )
        content = bn_txt.build_file(header, details)

        problems = bn_txt.check_structure(content)
        if problems:
            raise UserError(_(
                'El archivo generado no cumple la estructura del banco:\n%s',
                '\n'.join(problems)))

        self.write({
            'file_data': base64.b64encode(content.encode('latin-1', 'replace')),
            'file_name': 'D%s%s.txt' % (
                (depositor.vat or '').strip(), self.batch_number),
            'excluded_html': self._excluded_html(excluded),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _excluded_html(self, excluded):
        if not excluded:
            return False
        rows = ''.join(
            '<tr><td>%s</td><td>%s</td></tr>' % (move.display_name, reason)
            for move, reason in excluded)
        return (
            '<p>%s</p><table class="table table-sm">'
            '<thead><tr><th>%s</th><th>%s</th></tr></thead>'
            '<tbody>%s</tbody></table>'
        ) % (_('Comprobantes excluidos del archivo:'),
             _('Comprobante'), _('Motivo'), rows)
