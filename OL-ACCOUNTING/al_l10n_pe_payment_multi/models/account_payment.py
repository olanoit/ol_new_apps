from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_payment_multi_id = fields.Many2one(
        'l10n_pe.payment.multi', string='Pago múltiple', readonly=True, copy=False,
        index='btree_not_null', check_company=True)

    def _l10n_pe_check_multi(self):
        if self.env.context.get('l10n_pe_payment_multi_cancel'):
            return
        multi = self.l10n_pe_payment_multi_id[:1]
        if multi:
            raise UserError(_('El pago %(payment)s es del pago múltiple %(multi)s: anúlelo desde allí.',
                              payment=self.filtered('l10n_pe_payment_multi_id')[:1].display_name,
                              multi=multi.name))

    def action_draft(self):
        self._l10n_pe_check_multi()
        return super().action_draft()

    def action_cancel(self):
        self._l10n_pe_check_multi()
        return super().action_cancel()

    def _l10n_pe_receipt_other_lines(self):
        # En el comprobante, cada anticipo con su socio en lugar de un
        # «queda a cuenta» global.
        lines = super()._l10n_pe_receipt_other_lines()
        if self.l10n_pe_payment_multi_id:
            lines |= self.move_id.line_ids.filtered(
                lambda l: l.l10n_pe_payment_multi_line_id.line_type == 'advance')
        return lines

    def _l10n_pe_receipt_unapplied(self):
        if self.l10n_pe_payment_multi_id:
            return 0.0
        return super()._l10n_pe_receipt_unapplied()

    def _synchronize_to_moves(self, changed_fields):
        # Los apuntes de un pago múltiple los arma su documento (una
        # contrapartida por línea): la sincronización nativa supone una sola.
        return super(AccountPayment, self.filtered(lambda p: not p.l10n_pe_payment_multi_id)) \
            ._synchronize_to_moves(changed_fields)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_payment_multi_line_id = fields.Many2one(
        'l10n_pe.payment.multi.line', string='Línea de pago múltiple', readonly=True, copy=False,
        index='btree_not_null')
