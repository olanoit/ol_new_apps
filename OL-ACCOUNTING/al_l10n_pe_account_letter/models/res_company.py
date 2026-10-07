# -*- coding: utf-8 -*-
from odoo import fields, models

#: Cuentas de la compañía para las operaciones de letras y sus valores por
#: defecto en el PCGE del plan contable peruano de Odoo (l10n_pe).
COMPANY_ACCOUNT_DEFAULTS = {
    # 4511 Préstamos de instituciones financieras: la obligación con el banco
    # en el descuento con responsabilidad.
    'l10n_pe_letter_loan_account_id': 'chart4511',
    # 6734 Intereses por documentos vendidos o descontados.
    'l10n_pe_letter_interest_account_id': 'chart6734',
    # 6391 Gastos bancarios: comisiones, portes y gastos de protesto.
    'l10n_pe_letter_fee_account_id': 'chart6391',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_letter_loan_account_id = fields.Many2one(
        'account.account', string='Obligación por letras en descuento',
        help='Préstamo del banco en el descuento de letras (PCGE 4511).')
    l10n_pe_letter_interest_account_id = fields.Many2one(
        'account.account', string='Intereses del descuento de letras',
        help='PCGE 6734 Intereses por documentos vendidos o descontados.')
    l10n_pe_letter_fee_account_id = fields.Many2one(
        'account.account', string='Gastos bancarios de letras',
        help='Comisiones de cobranza y descuento, portes y gastos de protesto (PCGE 6391).')
    l10n_pe_letter_rounding_loss_account_id = fields.Many2one(
        'account.account', string='Redondeo en contra (letras)',
        help='Sin cuenta, se usa la de gasto llamada «Redondeo».')
    l10n_pe_letter_rounding_gain_account_id = fields.Many2one(
        'account.account', string='Redondeo a favor (letras)',
        help='Sin cuenta, se usa la de ingreso llamada «Redondeo».')

    def _l10n_pe_letter_set_default_accounts(self):
        """Llena con el PCGE las cuentas de letras que la compañía no tenga."""
        for company in self.filtered(lambda c: c.country_code == 'PE'):
            vals = {}
            for field, xmlid in COMPANY_ACCOUNT_DEFAULTS.items():
                if company[field]:
                    continue
                account = self.env.ref('account.%s_%s' % (company.id, xmlid),
                                       raise_if_not_found=False)
                if account:
                    vals[field] = account.id
            if vals:
                company.write(vals)

    def _l10n_pe_letter_adopt_named_setup(self):
        """Pasa a campos lo que antes se reconocía por el nombre: diarios
        «Letras por cobrar/pagar» y cuentas «Redondeo»."""
        Journal = self.env['account.journal']
        Account = self.env['account.account']
        for company in self:
            if not Journal.search_count([('company_id', '=', company.id),
                                         ('l10n_pe_letter_type', '!=', False)], limit=1):
                for letter_type, word in (('receivable', 'cobrar'), ('payable', 'pagar')):
                    Journal.search([('company_id', '=', company.id), ('name', 'ilike', 'letra'),
                                    ('name', 'ilike', word)]).write({'l10n_pe_letter_type': letter_type})
            for field, account_type in (('l10n_pe_letter_rounding_loss_account_id', 'expense'),
                                        ('l10n_pe_letter_rounding_gain_account_id', 'income_other')):
                if not company[field]:
                    account = Account.search([*Account._check_company_domain(company),
                                              ('name', '=', 'Redondeo'),
                                              ('account_type', '=', account_type)], limit=1)
                    if account:
                        company[field] = account
        self._l10n_pe_letter_set_default_accounts()


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_letter_type = fields.Selection(
        selection=[('receivable', 'Letras por cobrar'), ('payable', 'Letras por pagar')],
        string='Diario de letras',
        help='Diario en que se registran los canjes de letras. Antes se reconocía por el '
             'nombre («letra» y «cobrar»/«pagar»), que sigue valiendo si ningún diario '
             'tiene este campo.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_letter_loan_account_id = fields.Many2one(
        related='company_id.l10n_pe_letter_loan_account_id', readonly=False)
    l10n_pe_letter_interest_account_id = fields.Many2one(
        related='company_id.l10n_pe_letter_interest_account_id', readonly=False)
    l10n_pe_letter_fee_account_id = fields.Many2one(
        related='company_id.l10n_pe_letter_fee_account_id', readonly=False)
    l10n_pe_letter_rounding_loss_account_id = fields.Many2one(
        related='company_id.l10n_pe_letter_rounding_loss_account_id', readonly=False)
    l10n_pe_letter_rounding_gain_account_id = fields.Many2one(
        related='company_id.l10n_pe_letter_rounding_gain_account_id', readonly=False)
