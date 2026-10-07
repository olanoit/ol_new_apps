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

    @api.depends('debit', 'credit', 'letter_id.company_id')
    def _compute_account(self):
        """Cuenta «Redondeo» de gasto (redondeo a favor) o de ingreso (en
        contra) de la compañía del canje."""
        Account = self.env['account.account']
        for record in self:
            if record.debit > 0:
                account_type = 'expense'
            elif record.credit > 0:
                account_type = 'income_other'
            else:
                record.account_id = False
                continue
            company = record.letter_id.company_id or self.env.company
            configured = (company.l10n_pe_letter_rounding_loss_account_id
                          if account_type == 'expense'
                          else company.l10n_pe_letter_rounding_gain_account_id)
            # Respaldo: la cuenta llamada «Redondeo», como antes de la v9.
            record.account_id = configured or Account.search([
                *Account._check_company_domain(company),
                ('name', '=', 'Redondeo'),
                ('account_type', '=', account_type),
            ], limit=1)
