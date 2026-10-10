# -*- coding: utf-8 -*-
from odoo import api, fields, models

#: Tipos de depósito y su cuenta del PCGE por defecto.
DEPOSIT_TYPES = [
    ('term', 'Depósito a plazo'),
    ('guarantee_fund', 'Fondo en garantía'),
    ('guarantee_given', 'Depósito en garantía entregado'),
]


class L10nPeTermDepositAccountConfig(models.Model):
    _name = 'l10n_pe.term.deposit.account.config'
    _description = 'Cuentas de depósitos y garantías'
    _check_company_auto = True
    _order = 'company_id, deposit_type, currency_id'

    deposit_type = fields.Selection(DEPOSIT_TYPES, string='Tipo', required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        help='Vacía: se usa para cualquier moneda sin configuración propia.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    deposit_account_id = fields.Many2one(
        'account.account', string='Cuenta del depósito', required=True, check_company=True,
        help='Donde queda el dinero inmovilizado: 1062 depósitos a plazo, 1071 fondos en '
             'garantía, 1643 depósitos en garantía entregados.')
    interest_account_id = fields.Many2one(
        'account.account', string='Intereses por cobrar', required=True, check_company=True,
        help='Intereses devengados aún no cobrados (PCGE 1631).')
    income_account_id = fields.Many2one(
        'account.account', string='Ingreso por intereses', required=True, check_company=True,
        help='Rendimientos ganados (PCGE 7721).')

    _unique_combination = models.Constraint(
        'unique(deposit_type, currency_id, company_id)',
        'Ya hay cuentas para ese tipo de depósito, moneda y compañía.')

    #: Cuentas del PCGE que trae el plan contable peruano de Odoo (l10n_pe).
    PCGE_DEFAULTS = {
        'term': {'deposit_account_id': 'chart1062'},
        'guarantee_fund': {'deposit_account_id': 'chart1071'},
        'guarantee_given': {'deposit_account_id': 'chart1643'},
    }
    PCGE_COMMON = {'interest_account_id': 'chart1631', 'income_account_id': 'chart7721'}

    @api.model
    def _l10n_pe_create_default_configs(self, companies=None):
        """Cuentas por defecto (PCGE) para las compañías peruanas que no las
        tienen; nunca toca una configuración existente."""
        companies = companies or self.env['res.company'].search([])
        created = self.browse()
        for company in companies.filtered(lambda c: c.country_code == 'PE'):
            for deposit_type, _label in DEPOSIT_TYPES:
                if self.search_count([('deposit_type', '=', deposit_type), ('currency_id', '=', False),
                                      ('company_id', '=', company.id)], limit=1):
                    continue
                vals = {'deposit_type': deposit_type, 'company_id': company.id}
                for field, xmlid in dict(self.PCGE_COMMON, **self.PCGE_DEFAULTS[deposit_type]).items():
                    account = self.env.ref('account.%s_%s' % (company.id, xmlid), raise_if_not_found=False)
                    if account:
                        vals[field] = account.id
                if all(vals.get(f) for f in ('deposit_account_id', 'interest_account_id', 'income_account_id')):
                    created |= self.create(vals)
        return created

    @api.model
    def _l10n_pe_get(self, company, deposit_type, currency):
        """Configuración de la moneda o, si no hay, la general del tipo."""
        domain = [('company_id', '=', company.id), ('deposit_type', '=', deposit_type)]
        config = self.search(domain + [('currency_id', '=', currency.id)], limit=1) or \
            self.search(domain + [('currency_id', '=', False)], limit=1)
        if not config:
            config = self._l10n_pe_create_default_configs(company).filtered(
                lambda c: c.deposit_type == deposit_type)[:1]
        return config
