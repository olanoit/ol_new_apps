# -*- coding: utf-8 -*-
from odoo import api, fields, models

LOAN_TYPES = [
    ('loan', 'Préstamo bancario'),
    ('promissory', 'Pagaré'),
    ('other', 'Otra obligación financiera'),
]


class L10nPeBankLoanAccountConfig(models.Model):
    _name = 'l10n_pe.bank.loan.account.config'
    _description = 'Cuentas de préstamos bancarios'
    _check_company_auto = True
    _order = 'company_id, loan_type, currency_id'

    loan_type = fields.Selection(LOAN_TYPES, string='Tipo', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda',
                                  help='Vacía: se usa para cualquier moneda sin configuración propia.')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    principal_account_id = fields.Many2one(
        'account.account', string='Capital adeudado', required=True, check_company=True,
        help='Obligación financiera: 4511 préstamos de instituciones financieras, 4544 pagarés.')
    interest_payable_account_id = fields.Many2one(
        'account.account', string='Intereses por pagar', required=True, check_company=True,
        help='Costos de financiación devengados y no pagados: 45511 (préstamos), 45544 (pagarés).')
    interest_expense_account_id = fields.Many2one(
        'account.account', string='Gasto por intereses', required=True, check_company=True,
        help='67311 intereses de préstamos de instituciones financieras, 6733 de otros instrumentos.')
    insurance_account_id = fields.Many2one(
        'account.account', string='Seguro de desgravamen', check_company=True,
        help='Gasto por el seguro que cobra el banco en la cuota (651 seguros). Vacía: va al gasto por intereses.')
    fee_account_id = fields.Many2one(
        'account.account', string='Comisiones y portes', check_company=True,
        help='Comisiones, portes y gastos de desembolso (6391 gastos bancarios).')

    _unique_combination = models.Constraint(
        'unique(loan_type, currency_id, company_id)',
        'Ya hay cuentas para ese tipo de préstamo, moneda y compañía.')

    #: Cuentas del PCGE que trae el plan contable peruano de Odoo (l10n_pe).
    PCGE_DEFAULTS = {
        'loan': {'principal_account_id': 'chart4511', 'interest_payable_account_id': 'chart45511',
                 'interest_expense_account_id': 'chart67311'},
        'promissory': {'principal_account_id': 'chart4544', 'interest_payable_account_id': 'chart45544',
                       'interest_expense_account_id': 'chart6733'},
        'other': {'principal_account_id': 'chart4549', 'interest_payable_account_id': 'chart45549',
                  'interest_expense_account_id': 'chart6733'},
    }
    PCGE_COMMON = {'insurance_account_id': 'chart651', 'fee_account_id': 'chart6391'}

    @api.model
    def _l10n_pe_create_default_configs(self, companies=None):
        """Cuentas por defecto (PCGE) para las compañías peruanas que no las
        tienen; nunca toca una configuración existente."""
        companies = companies or self.env['res.company'].search([])
        created = self.browse()
        for company in companies.filtered(lambda c: c.country_code == 'PE'):
            for loan_type, _label in LOAN_TYPES:
                if self.search_count([('loan_type', '=', loan_type), ('currency_id', '=', False),
                                      ('company_id', '=', company.id)], limit=1):
                    continue
                vals = {'loan_type': loan_type, 'company_id': company.id}
                for field, xmlid in dict(self.PCGE_COMMON, **self.PCGE_DEFAULTS[loan_type]).items():
                    account = self.env.ref('account.%s_%s' % (company.id, xmlid), raise_if_not_found=False)
                    if account:
                        vals[field] = account.id
                if all(vals.get(f) for f in ('principal_account_id', 'interest_payable_account_id',
                                             'interest_expense_account_id')):
                    created |= self.create(vals)
        return created

    @api.model
    def _l10n_pe_get(self, company, loan_type, currency):
        """Configuración de la moneda o, si no hay, la general del tipo."""
        domain = [('company_id', '=', company.id), ('loan_type', '=', loan_type)]
        config = self.search(domain + [('currency_id', '=', currency.id)], limit=1) or \
            self.search(domain + [('currency_id', '=', False)], limit=1)
        if not config:
            config = self._l10n_pe_create_default_configs(company).filtered(
                lambda c: c.loan_type == loan_type)[:1]
        return config
