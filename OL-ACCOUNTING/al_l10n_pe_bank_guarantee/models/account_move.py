# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_bank_guarantee_id = fields.Many2one(
        'l10n_pe.bank.guarantee', string='Carta fianza', readonly=True, copy=False, index='btree_not_null',
        check_company=True)
