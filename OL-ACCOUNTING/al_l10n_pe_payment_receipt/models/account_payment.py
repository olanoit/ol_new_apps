from num2words import num2words

from odoo import _, fields, models
from odoo.exceptions import UserError

#: Nombre de la moneda en el monto en letras (plural, como en los comprobantes).
CURRENCY_WORDS = {'PEN': 'SOLES', 'USD': 'DÓLARES AMERICANOS', 'EUR': 'EUROS'}


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_receipt_number = fields.Char(
        string='N.º de comprobante de pago', copy=False, readonly=True, index='btree_not_null',
        help='Recibo de ingreso (cobros) o comprobante de egreso (pagos). Se asigna al '
             'confirmar el pago en un diario con comprobante numerado y no se reutiliza.')

    _l10n_pe_receipt_number_uniq = models.Constraint(
        'unique(company_id, l10n_pe_receipt_number)',
        'El número de comprobante de pago ya existe en la compañía.',
    )

    def action_post(self):
        res = super().action_post()
        self._l10n_pe_receipt_assign_number()
        return res

    def _l10n_pe_receipt_applies(self):
        self.ensure_one()
        return bool(
            self.journal_id.l10n_pe_receipt_enabled
            and self.payment_type in ('inbound', 'outbound')
            and not self.paired_internal_transfer_payment_id
            and self.partner_id != self.company_id.partner_id)

    def _l10n_pe_receipt_assign_number(self):
        """Número del comprobante al confirmar. Un pago vuelto a borrador y
        confirmado otra vez conserva el suyo: la serie no deja huecos."""
        for payment in self.filtered(lambda p: not p.l10n_pe_receipt_number):
            if not payment._l10n_pe_receipt_applies():
                continue
            journal = payment.journal_id
            if not (journal.l10n_pe_receipt_in_sequence_id and journal.l10n_pe_receipt_out_sequence_id):
                journal._l10n_pe_receipt_ensure_sequences()
            sequence = journal.l10n_pe_receipt_in_sequence_id if payment.payment_type == 'inbound' \
                else journal.l10n_pe_receipt_out_sequence_id
            # sudo: el contable no administra ir.sequence, pero numera sus pagos.
            payment.l10n_pe_receipt_number = sequence.sudo().next_by_id(sequence_date=payment.date)

    # ------------------------------------------------------------------
    # Datos del comprobante impreso
    # ------------------------------------------------------------------

    def _l10n_pe_receipt_title(self):
        self.ensure_one()
        return _('Recibo de ingreso') if self.payment_type == 'inbound' else _('Comprobante de egreso')

    def _l10n_pe_receipt_amount_words(self):
        """«CIENTO DIECIOCHO Y 50/100 SOLES», como el monto en letras de los comprobantes."""
        self.ensure_one()
        integer, decimals = divmod(round(abs(self.amount), 2), 1)
        cents = int(round(decimals * 100))
        currency = CURRENCY_WORDS.get(self.currency_id.name) or (self.currency_id.currency_unit_label or '').upper()
        return ('%s Y %02d/100 %s' % (num2words(int(integer), lang='es'), cents, currency)).upper()

    def _l10n_pe_receipt_counterpart_lines(self):
        """Apuntes del pago contra el socio (cuentas por cobrar, por pagar o de anticipos)."""
        self.ensure_one()
        return self.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

    def _l10n_pe_receipt_documents(self):
        """Comprobantes aplicados con lo pagado de cada uno, en la moneda del pago.

        Con asiento, sale de sus conciliaciones parciales (pagos parciales y
        varias facturas). Sin asiento —en v19 el pago de un diario sin cuenta
        de pendientes no lo tiene hasta conciliar el extracto— se reparte el
        importe entre las facturas del pago por fecha, como el asistente.
        """
        self.ensure_one()
        if self.move_id:
            applied = {}
            for line in self._l10n_pe_receipt_counterpart_lines():
                for partial in line.matched_debit_ids | line.matched_credit_ids:
                    ours_is_debit = partial.debit_move_id == line
                    counterpart = partial.credit_move_id if ours_is_debit else partial.debit_move_id
                    amount = partial.debit_amount_currency if ours_is_debit else partial.credit_amount_currency
                    applied[counterpart.move_id] = applied.get(counterpart.move_id, 0.0) + amount
            return [self._l10n_pe_receipt_document_vals(move, amount, move.amount_residual)
                    for move, amount in applied.items()]
        documents = []
        remaining = self.amount
        for move in self.invoice_ids.sorted(lambda m: (m.invoice_date or m.date, m.id)):
            due = move.currency_id._convert(
                abs(move.amount_residual), self.currency_id, self.company_id, self.date)
            amount = min(remaining, due)
            remaining -= amount
            residual = move.amount_residual - self.currency_id._convert(
                amount, move.currency_id, self.company_id, self.date)
            documents.append(self._l10n_pe_receipt_document_vals(move, amount, residual))
        return documents

    def _l10n_pe_receipt_document_vals(self, move, applied, residual):
        is_invoice = move.is_invoice(include_receipts=True)
        name = move.name
        if 'l10n_latam_document_number' in move._fields and move.l10n_latam_document_number:
            name = move.l10n_latam_document_number
        return {
            'move': move,
            'partner': move.commercial_partner_id,
            'name': name,
            'document_type': move.l10n_latam_document_type_id.name
            if 'l10n_latam_document_type_id' in move._fields else '',
            'date': move.invoice_date or move.date,
            'total': move.amount_total if is_invoice else None,
            'currency': move.currency_id,
            'applied': applied,
            'residual': residual if is_invoice else None,
        }

    def _l10n_pe_receipt_unapplied(self):
        """Lo que el pago deja a cuenta (sin aplicar a ningún comprobante)."""
        self.ensure_one()
        if self.move_id:
            lines = self._l10n_pe_receipt_counterpart_lines()
            return abs(sum(lines.mapped('amount_residual_currency')))
        applied = sum(doc['applied'] for doc in self._l10n_pe_receipt_documents())
        return self.currency_id.round(max(self.amount - applied, 0.0))

    def _l10n_pe_receipt_other_lines(self):
        """Otros conceptos del asiento: retenciones, diferencias, comisiones."""
        self.ensure_one()
        liquidity, counterpart, writeoff = self._seek_for_lines()
        return writeoff

    def action_l10n_pe_receipt_print(self):
        payments = self.filtered('l10n_pe_receipt_number')
        if not payments:
            raise UserError(_('Los pagos elegidos no tienen comprobante: confírmelos en un diario '
                              'con «Comprobante de pago numerado».'))
        return self.env.ref('al_l10n_pe_payment_receipt.action_report_payment_receipt_pe') \
            .report_action(payments)

    def action_l10n_pe_receipt_send(self):
        self.ensure_one()
        if not self.l10n_pe_receipt_number:
            raise UserError(_('El pago aún no tiene comprobante.'))
        template = self.env.ref('al_l10n_pe_payment_receipt.mail_template_payment_receipt_pe')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': self._name,
                'default_res_ids': self.ids,
                'default_template_id': template.id,
                'default_composition_mode': 'comment',
                'force_email': True,
            },
        }
