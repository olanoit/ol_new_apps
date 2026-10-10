# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_term_deposit_id = fields.Many2one(
        'l10n_pe.term.deposit', string='Depósito o garantía', readonly=True, copy=False,
        index='btree_not_null', check_company=True,
        help='Depósito a plazo o garantía que generó el asiento.')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_term_deposit_id = fields.Many2one(
        related='move_id.l10n_pe_term_deposit_id', store=True, index='btree_not_null',
        string='Depósito o garantía')
    l10n_pe_term_deposit_interest = fields.Boolean(
        string='Interés de depósito', copy=False,
        help='Apunte de ingreso por intereses de un depósito: devengo o ajuste al cobrarlos.')
