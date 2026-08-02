# -*- coding: utf-8 -*-

from odoo import models, fields, api


class L10nPeLetterResidual(models.Model):
    _name = 'l10n_pe.letter.residual'
    _description = 'redondeo'

    name = fields.Char(
        string='Comprobantes',
    )
    letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Letra',
        ondelete='cascade',
    )
    type = fields.Selection(
        string='Tipo',
        related='letter_id.type',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda',
        related='letter_id.currency_id',
    )
    company_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda de la compañía',
        related='letter_id.company_currency_id',
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta',
        index=True,
        compute='_compute_account',
    )
    debit = fields.Monetary(
        currency_field='company_currency_id',
        string='Debe',
        compute='_compute_debit_credit',
    )
    credit = fields.Monetary(
        currency_field='company_currency_id',
        string='Crédito',
        compute='_compute_debit_credit',
    )
    amount = fields.Monetary(
        string='Importe',
        currency_field='company_currency_id',
    )
    amount_currency = fields.Monetary(
        currency_field='currency_id',
        string='Importe en moneda',
    )

    @api.depends('amount')
    def _compute_debit_credit(self):
        for record in self:
            if record.amount > 0:
                record.debit = record.amount
                record.credit = 0
            else:
                record.debit = 0
                record.credit = record.amount * -1

    @api.depends('debit', 'credit')
    def _compute_account(self):
        for record in self:
            if record.debit > 0:
                record.account_id = self.env['account.account'].search(
                    [('name', '=', 'Redondeo'), ('account_type', '=', 'expense')], limit=1)
            elif record.credit > 0:
                record.account_id = self.env['account.account'].search(
                    [('name', '=', 'Redondeo'), ('account_type', '=', 'income_other')], limit=1)
            else:
                record.account_id = False
