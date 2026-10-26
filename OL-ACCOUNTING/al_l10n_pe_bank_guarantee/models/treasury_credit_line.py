# -*- coding: utf-8 -*-
from odoo import models


class L10nPeTreasuryCreditLine(models.Model):
    _inherit = 'l10n_pe.treasury.credit.line'

    def _l10n_pe_credit_usage(self):
        # Importe de las cartas fianza emitidas vigentes (o vencidas sin devolver).
        usage = super()._l10n_pe_credit_usage()
        guarantees = self.env['l10n_pe.bank.guarantee'].search([
            ('credit_line_id', 'in', self.ids), ('direction', '=', 'issued'), ('state', 'in', ('active', 'expired'))])
        for guarantee in guarantees:
            line = guarantee.credit_line_id
            usage[line.id] = usage.get(line.id, 0.0) + line._l10n_pe_convert(guarantee.amount, guarantee.currency_id)
        return usage
