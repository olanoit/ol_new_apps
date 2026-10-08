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

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import bn_txt

# Tipos de comprobante admitidos por el banco (tabla 5.6): factura, boleta y
# guía de remisión. Las notas de débito se informan como factura.
BN_INVOICE_TYPES = {'01': '01', '03': '03', '08': '01', '09': '09'}
BN_DEFAULT_INVOICE_TYPE = '01'


class L10nPeDetractionTxtWizard(models.TransientModel):
    _name = 'l10n_pe.detraction.txt.wizard'
    _description = 'Depósito masivo de detracciones (Banco de la Nación)'
    _check_company_auto = True

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
        domain="[('l10n_pe_detraction_applies', '=', True),"
               " ('state', '=', 'posted'),"
               " ('l10n_pe_detraction_number', '=', False),"
               " ('move_type', '=', 'in_invoice' if mode == 'acquirer'"
               " else 'out_invoice')]",
        check_company=True)
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
        last = self.env.company.l10n_pe_detraction_last_batch or ''
        if re.fullmatch(r'\d{6}', last) and last[:2] == year \
                and last[2:] != '9999':
            return '%s%04d' % (year, int(last[2:]) + 1)
        return '%s0001' % year

    @api.constrains('batch_number')
    def _check_batch_number(self):
        for wizard in self:
            if not re.fullmatch(r'\d{6}', wizard.batch_number or ''):
                raise ValidationError(_(
                    'El número de lote debe tener 6 dígitos con el formato '
                    'AANNNN (por ejemplo 260001).'))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and \
                    wizard.date_to < wizard.date_from:
                raise ValidationError(_('La fecha «Hasta» no puede ser anterior a '
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
            # los ya depositados tienen constancia: no se depositan dos veces
            ('l10n_pe_detraction_number', '=', False),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
        ], order='invoice_date, name')

    def _identified_party(self, move):
        """Quién identifica cada línea de detalle (campos 01-47).

        Según el instructivo, en la modalidad adquiriente cada línea lleva al
        proveedor; en la modalidad proveedor, a cada adquiriente, es decir, al
        cliente de la factura. No es la propia empresa: esa ya va en la
        cabecera.
        """
        return move.partner_id.commercial_partner_id

    def _account_holder(self, move):
        """Titular de la cuenta del Banco de la Nación donde se deposita.

        Siempre es el proveedor de la operación: el tercero cuando la empresa
        compra y la propia empresa cuando vende.
        """
        return (move.partner_id.commercial_partner_id if self.mode == 'acquirer'
                else self.company_id.partner_id)

    @api.model
    def _document_type(self, partner):
        """Tipo de documento de identidad (tabla 5.8, códigos de SUNAT)."""
        identification = partner.l10n_latam_identification_type_id
        code = identification.l10n_pe_vat_code if identification else False
        return code or bn_txt.DOC_TYPE_RUC

    def _check_move(self, move):
        """Motivo por el que un comprobante no puede incluirse, o ``None``."""
        party = self._identified_party(move)
        holder = self._account_holder(move)
        # Los comprobantes elegidos a mano no pasan por el filtro del
        # periodo: se validan aquí con los mismos criterios.
        expected_type = ('in_invoice' if self.mode == 'acquirer'
                         else 'out_invoice')
        if move.company_id != self.company_id:
            return _('pertenece a otra compañía')
        if move.move_type != expected_type:
            return _('no corresponde a la modalidad elegida')
        if move.state != 'posted':
            return _('no está publicado')
        if not move.l10n_pe_detraction_applies:
            return _('no está sujeto a detracción')
        if move.l10n_pe_detraction_number:
            return _('ya tiene la constancia de depósito %s',
                     move.l10n_pe_detraction_number)
        if not move.l10n_pe_detraction_type_id:
            return _('sin tipo de detracción (catálogo 54)')
        if not move.l10n_pe_detraction_amount:
            return _('el monto de detracción es cero')
        if not (party.vat or '').strip():
            return _('%s no tiene número de documento', party.display_name)
        if not (holder.l10n_pe_detraction_account or '').strip():
            return _('%s no tiene cuenta de detracciones del Banco de la '
                     'Nación', holder.display_name)
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
        party = self._identified_party(move)
        holder = self._account_holder(move)
        bn_type, serie, folio = self._invoice_parts(move)
        return bn_txt.build_detail(
            doc_type=self._document_type(party),
            vat=party.vat,
            # El instructivo pide dejar el nombre en blanco: el banco lo
            # recupera del RUC.
            name='',
            service_code=move.l10n_pe_detraction_type_id.code,
            bank_account=holder.l10n_pe_detraction_account,
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
        # La cabecera siempre lleva a la empresa que presenta el lote: como
        # adquiriente o como proveedor (el indicador de maestra lo distingue).
        depositor = self.company_id.partner_id
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
        # El correlativo del lote se guarda en la compañía para proponer
        # el siguiente. sudo(): los contables no pueden escribir en
        # res.company y aquí solo se anota el último lote generado.
        company_sudo = self.company_id.sudo()
        if self.batch_number > (company_sudo.l10n_pe_detraction_last_batch
                                or ''):
            company_sudo.l10n_pe_detraction_last_batch = self.batch_number
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
        rows = Markup('').join(
            Markup('<tr><td>%s</td><td>%s</td></tr>') % (move.display_name, reason)
            for move, reason in excluded)
        return Markup(
            '<p>%s</p><table class="table table-sm">'
            '<thead><tr><th>%s</th><th>%s</th></tr></thead>'
            '<tbody>%s</tbody></table>'
        ) % (_('Comprobantes excluidos del archivo:'),
             _('Comprobante'), _('Motivo'), rows)
