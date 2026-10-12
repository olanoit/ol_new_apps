# -*- coding: utf-8 -*-
from odoo import fields, models

from .cash_fund import PAYMENT_KINDS


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_cash_fund_id = fields.Many2one(
        'l10n_pe.cash.fund', string='Entrega a rendir / caja chica', index='btree_not_null',
        copy=False, check_company=True, readonly=True)
    l10n_pe_cash_fund_kind = fields.Selection(
        PAYMENT_KINDS, string='Movimiento del fondo', copy=False, readonly=True)

    def action_post(self):
        res = super().action_post()
        # Una devolución o reposición confirmada concilia lo pendiente del fondo.
        self.l10n_pe_cash_fund_id._reconcile_fund_lines()
        return res
