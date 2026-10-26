# -*- coding: utf-8 -*-
from odoo import models


class L10nPeTreasuryCreditLine(models.Model):
    _inherit = 'l10n_pe.treasury.credit.line'

    def _l10n_pe_credit_usage(self):
        # Saldo de capital de los préstamos vigentes asignados a la línea.
        usage = super()._l10n_pe_credit_usage()
        loans = self.env['l10n_pe.bank.loan'].search([('credit_line_id', 'in', self.ids), ('state', '=', 'running')])
        for loan in loans:
            line = loan.credit_line_id
            usage[line.id] = usage.get(line.id, 0.0) + line._l10n_pe_convert(loan.principal_balance, loan.currency_id)
        return usage
