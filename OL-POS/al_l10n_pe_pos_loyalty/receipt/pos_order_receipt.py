# -*- coding: utf-8 -*-
from odoo import _, models


class PosOrderReceipt(models.AbstractModel):
    """Mismo criterio que el ticket del TPV (static/src/app/generate_printer_data.js)."""
    _inherit = 'pos.order.receipt'

    def _l10n_pe_receipt_line_records(self):
        return super()._l10n_pe_receipt_line_records() - self.lines._l10n_pe_pos_voucher_lines()

    def _l10n_pe_receipt_extra_payments(self):
        redeemed = self.lines._l10n_pe_pos_voucher_lines().filtered('is_reward_line')
        return super()._l10n_pe_receipt_extra_payments() + [
            (line.reward_id.program_id.name or _('Tarjeta de regalo'), -line.price_subtotal_incl)
            for line in redeemed]

    def _l10n_pe_receipt_notes(self):
        sold = self.lines._l10n_pe_pos_voucher_lines().filtered(lambda line: not line.is_reward_line)
        return super()._l10n_pe_receipt_notes() + [
            '%s: %s %s' % (line.full_product_name or line.product_id.display_name,
                           self._order_receipt_format_currency(line.price_subtotal_incl),
                           _('(no forma parte del comprobante: se emite al canjearla)'))
            for line in sold]
