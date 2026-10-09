# -*- coding: utf-8 -*-
import base64
from datetime import datetime

from pytz import timezone

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_edi_status = fields.Selection(
        selection_add=[('reversing', 'Reversión en proceso'), ('cancelled',)],
        ondelete={'reversing': lambda payments: payments.write({'l10n_pe_edi_status': 'sent'})})
    l10n_pe_edi_reversal_reason = fields.Char(
        string='Motivo de la reversión', copy=False, tracking=True,
        help='Por qué se revierte el comprobante de retención (queda en el historial del pago).')
    l10n_pe_edi_reversal_filename = fields.Char(
        string='Archivo de la reversión', copy=False, readonly=True,
        help='RUC-RR-AAAAMMDD-N. Se reutiliza en los reintentos para no cambiar el '
             'correlativo (SUNAT rechaza con el error 2220 un correlativo distinto).')
    l10n_pe_edi_reversal_ticket = fields.Char(
        string='Ticket de la reversión', copy=False, readonly=True,
        help='Ticket que devuelve SUNAT al recibir el resumen de reversiones.')
    l10n_pe_edi_reversal_message = fields.Html(
        string='Estado de la reversión', copy=False, readonly=True, sanitize=False)
    l10n_pe_edi_reversal_available = fields.Boolean(
        compute='_compute_l10n_pe_edi_reversal_available')

    @api.depends('company_id.l10n_pe_edi_provider', 'company_id.l10n_pe_edi_factory_hka_retention',
                 'company_id.l10n_pe_edi_factory_hka_reversal')
    def _compute_l10n_pe_edi_reversal_available(self):
        for payment in self:
            payment.l10n_pe_edi_reversal_available = payment.company_id._l10n_pe_edi_factory_hka_uses('reversal')

    def _compute_l10n_pe_edi_is_required(self):
        # Un CRE en reversión ya fue aceptado: no se vuelve a enviar.
        super()._compute_l10n_pe_edi_is_required()
        for payment in self.filtered(lambda p: p.l10n_pe_edi_status == 'reversing'):
            payment.l10n_pe_edi_is_required = False

    # ------------------------------------------------------------------
    # Envío del CRE
    # ------------------------------------------------------------------

    def _l10n_pe_edi_sign_retention(self, edi_format, filename, edi_str):
        # Factory HKA recibe el CRE en el mismo billService que las facturas.
        if self.company_id._l10n_pe_edi_factory_hka_uses('retention'):
            return edi_format._l10n_pe_edi_sign_service_factory_hka(
                self.company_id, filename, edi_str, '20')
        return super()._l10n_pe_edi_sign_retention(edi_format, filename, edi_str)

    # ------------------------------------------------------------------
    # Reversión del CRE (resumen de reversiones RR)
    # ------------------------------------------------------------------

    def _l10n_pe_edi_reversal_values(self):
        """Nombre de archivo e identificador del resumen RR. El ``cbc:ID`` va
        sin el RUC (error 2220); el archivo, con él. En los reintentos se
        reutiliza el guardado para no gastar otro correlativo."""
        self.ensure_one()
        today = datetime.now(tz=timezone('America/Lima')).date()
        filename = self.l10n_pe_edi_reversal_filename
        if not filename:
            number = self.env['ir.sequence'].with_context(ir_sequence_date=today).next_by_code(
                'al_ose_factory_hka.reversal_sequence')
            filename = '%s-%s' % (self.company_id.vat, number)
            self.l10n_pe_edi_reversal_filename = filename
        return {'filename': filename, 'number': filename.split('-', 1)[1], 'issue_date': today}

    def _l10n_pe_edi_generate_reversal_bstr(self, values):
        self.ensure_one()
        serie, _sep, folio = self.l10n_pe_edi_retention_number.partition('-')
        return self.env['ir.qweb']._render('al_ose_factory_hka.cre_reversal_summary', {
            'company': self.company_id,
            'reversal_number': values['number'],
            'reference_date': self.date,
            'issue_date': values['issue_date'],
            'serie': serie,
            'folio': int(folio) if folio.isdigit() else folio,
        }).encode()

    def action_l10n_pe_edi_reverse_retention(self):
        """Paso 1: envía el resumen de reversiones (sendSummary) y guarda el ticket."""
        for payment in self:
            if not payment.l10n_pe_edi_reversal_available:
                raise UserError(self.env._(
                    'La reversión del CRE por Factory HKA no está activa en %s.', payment.company_id.display_name))
            if payment.l10n_pe_edi_status != 'sent':
                raise UserError(self.env._('Solo se revierte un comprobante de retención aceptado por SUNAT.'))
            if not payment.l10n_pe_edi_reversal_reason:
                raise UserError(self.env._('Indique el motivo de la reversión.'))
            values = payment._l10n_pe_edi_reversal_values()
            edi_format = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')
            res = edi_format._l10n_pe_edi_cancel_invoices_step_1_factory_hka(
                payment.company_id, payment, values['filename'],
                payment._l10n_pe_edi_generate_reversal_bstr(values))
            if res.get('error'):
                payment.l10n_pe_edi_reversal_message = res['error']
                continue
            attachment = self.env['ir.attachment'].create({
                'name': '%s.xml' % values['filename'], 'res_model': payment._name, 'res_id': payment.id,
                'type': 'binary', 'raw': res['xml_document'], 'mimetype': 'application/xml'})
            payment.write({
                'l10n_pe_edi_status': 'reversing',
                'l10n_pe_edi_reversal_ticket': res['cdr_number'],
                'l10n_pe_edi_reversal_message': False,
            })
            payment.message_post(body=self.env._(
                'Reversión del CRE %(number)s enviada a SUNAT (ticket %(ticket)s). Motivo: %(reason)s',
                number=payment.l10n_pe_edi_retention_number, ticket=res['cdr_number'],
                reason=payment.l10n_pe_edi_reversal_reason), attachment_ids=attachment.ids)
        return True

    def action_l10n_pe_edi_check_reversal(self):
        """Paso 2: consulta el ticket (getStatus) hasta que SUNAT acepta la reversión."""
        edi_format = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')
        for payment in self:
            if payment.l10n_pe_edi_status != 'reversing' or not payment.l10n_pe_edi_reversal_ticket:
                raise UserError(self.env._('Este pago no tiene una reversión del CRE en proceso.'))
            res = edi_format._l10n_pe_edi_cancel_invoices_step_2_factory_hka(
                payment.company_id, [], payment.l10n_pe_edi_reversal_ticket)
            if res.get('error'):
                # 'info': SUNAT aún procesa (código 98), se vuelve a consultar.
                payment.l10n_pe_edi_reversal_message = res['error']
                continue
            attachment = self.env['ir.attachment'].create({
                'name': 'CDR-%s.xml' % payment.l10n_pe_edi_reversal_filename,
                'res_model': payment._name, 'res_id': payment.id,
                'type': 'binary', 'datas': base64.b64encode(res['cdr']), 'mimetype': 'application/xml'})
            payment.write({
                'l10n_pe_edi_status': 'cancelled',
                'l10n_pe_edi_reversal_message': False,
            })
            payment.message_post(body=self.env._(
                'SUNAT aceptó la reversión del CRE %(number)s. Si el pago también debe '
                'anularse, cancélelo o reviértalo en contabilidad.',
                number=payment.l10n_pe_edi_retention_number), attachment_ids=attachment.ids)
        return True
