from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .res_company import itf_amount


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_itf_journal_applies = fields.Boolean(related='journal_id.l10n_pe_itf_applies')
    l10n_pe_itf_exempt = fields.Boolean(
        string='Exonerado del ITF', copy=False,
        help='No registrar el ITF de este pago (operación exonerada o no gravada).')
    l10n_pe_itf_amount = fields.Monetary(
        string='ITF', currency_field='currency_id', compute='_compute_l10n_pe_itf_amount',
        help='Impuesto a las Transacciones Financieras que cobrará el banco por este movimiento.')
    l10n_pe_itf_move_id = fields.Many2one(
        'account.move', string='Asiento del ITF', readonly=True, copy=False, check_company=True,
        index='btree_not_null')

    @api.depends('amount', 'journal_id.l10n_pe_itf_applies', 'l10n_pe_itf_exempt',
                 'destination_account_id', 'paired_internal_transfer_payment_id')
    def _compute_l10n_pe_itf_amount(self):
        for payment in self:
            payment.l10n_pe_itf_amount = itf_amount(
                payment.amount, payment.company_id.root_id.l10n_pe_itf_rate
            ) if payment._l10n_pe_itf_applies() else 0.0

    def _l10n_pe_itf_applies(self):
        """El ITF grava el cargo o abono en la cuenta bancaria, salvo entre cuentas
        del mismo titular (art. 9 a de la Ley 28194: transferencias internas y
        compraventa de moneda) y las exoneradas."""
        self.ensure_one()
        return bool(
            self.journal_id.l10n_pe_itf_applies
            and self.journal_id.type == 'bank'
            and self.payment_type in ('inbound', 'outbound')
            and not self.l10n_pe_itf_exempt
            and not self.paired_internal_transfer_payment_id
            and self.destination_account_id != self.company_id.transfer_account_id
            and self.partner_id != self.company_id.partner_id)

    def action_post(self):
        res = super().action_post()
        self._l10n_pe_itf_create_moves()
        return res

    def _l10n_pe_itf_create_moves(self):
        """Asiento del ITF: gasto a la cuenta del ITF contra la misma cuenta de
        pendientes del pago, para conciliarlo con la línea «ITF» del extracto.
        Un pago sin asiento (diario sin cuenta de pendientes) no lo lleva: su ITF
        se registra al conciliar el extracto con la regla «ITF»."""
        for payment in self.filtered(lambda p: not p.l10n_pe_itf_move_id and p.move_id):
            amount = payment.l10n_pe_itf_amount
            if not amount:
                continue
            account = payment.company_id._l10n_pe_itf_account()
            if not account:
                raise UserError(_('Indique la cuenta del ITF en Ajustes ▸ Perú ▸ ITF.'))
            company = payment.company_id
            balance = payment.currency_id._convert(amount, company.currency_id, company, payment.date)
            label = _('ITF %s', payment.name)
            common = {'currency_id': payment.currency_id.id, 'name': label}
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': payment.journal_id.id,
                'date': payment.date,
                'ref': label,
                'company_id': company.id,
                'l10n_pe_itf_payment_id': payment.id,
                'line_ids': [
                    fields.Command.create({**common, 'account_id': account.id,
                                           'amount_currency': amount, 'balance': balance}),
                    fields.Command.create({**common, 'account_id': payment.outstanding_account_id.id,
                                           'amount_currency': -amount, 'balance': -balance}),
                ],
            })
            move.action_post()
            payment.l10n_pe_itf_move_id = move

    def _l10n_pe_itf_cancel_moves(self):
        """Al volver el pago a borrador o anularlo, su ITF se anula (queda en el historial)."""
        moves = self.l10n_pe_itf_move_id.filtered(lambda m: m.state == 'posted')
        if moves:
            moves.button_cancel()
        self.l10n_pe_itf_move_id = False

    def action_draft(self):
        res = super().action_draft()
        self._l10n_pe_itf_cancel_moves()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._l10n_pe_itf_cancel_moves()
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_itf_payment_id = fields.Many2one(
        'account.payment', string='Pago del ITF', readonly=True, copy=False, index='btree_not_null',
        check_company=True, help='Pago o cobro cuyo ITF registra este asiento.')
