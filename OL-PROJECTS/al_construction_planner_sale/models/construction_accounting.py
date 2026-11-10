# -*- coding: utf-8 -*-
"""Costo ejecutado e ingreso contable de la obra (paquete 7 de CREVAL, CR-62).

Va en el puente de ventas y no en el núcleo: el núcleo no depende de
Contabilidad y el costo se lee por el tipo de la cuenta contable.

Salen de los apuntes analíticos de la cuenta de la obra: costo, los de cuentas
de gasto; ingreso, los de cuentas de ingreso. Las cuentas de balance
(anticipos, por cobrar, por pagar) quedan fuera por su tipo, y los prefijos
que la compañía excluye (en Perú, 9 y 79: destinos y cargas imputables) no
suman, para que los asientos de destino no dupliquen el costo."""
from odoo import api, fields, models
from odoo.fields import Domain

EXPENSE_TYPES = ('expense', 'expense_direct_cost', 'expense_depreciation')
INCOME_TYPES = ('income', 'income_other')


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_excluded_account_prefixes = fields.Char(
        string='Cuentas fuera del costo de obra',
        default=lambda self: '9,79' if self.env.company.country_id.code == 'PE' else '',
        help='Prefijos de cuentas contables, separados por coma, que no suman al costo ejecutado '
             'ni al ingreso de la obra (en Perú, 9 y 79: destinos y cargas imputables).')

    def _construction_excluded_prefixes(self):
        self.ensure_one()
        return [prefix.strip() for prefix in (self.construction_excluded_account_prefixes or '')
                .split(',') if prefix.strip()]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_excluded_account_prefixes = fields.Char(
        related='company_id.construction_excluded_account_prefixes', readonly=False)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_cost_executed = fields.Monetary(
        string='Costo ejecutado', compute='_compute_construction_accounting', compute_sudo=True,
        currency_field='construction_accounting_currency_id',
        help='De la contabilidad: apuntes analíticos de la obra en cuentas de gasto, por fecha '
             'contable, sin las cuentas excluidas de la compañía (Ajustes). El ingreso contable '
             'es el de la pestaña «Planificación», con la misma regla.')
    construction_accounting_currency_id = fields.Many2one(
        'res.currency', compute='_compute_construction_accounting', compute_sudo=True)

    def _construction_analytic_domain(self, kinds, date_from=None, date_to=None):
        """Apuntes analíticos de la obra en cuentas de ``kinds``."""
        self.ensure_one()
        account = self.account_id
        column = account.plan_id._column_name() if account.plan_id else 'account_id'
        domain = Domain([(column, '=', account.id),
                         ('general_account_id.account_type', 'in', list(kinds))])
        company = self.company_id or self.env.company
        for prefix in company._construction_excluded_prefixes():
            domain &= ~Domain('general_account_id.code', '=like', prefix + '%')
        if date_from:
            domain &= Domain('date', '>=', date_from)
        if date_to:
            domain &= Domain('date', '<=', date_to)
        return domain

    def _construction_accounting_amounts(self, date_from=None, date_to=None):
        """{'cost': costo ejecutado, 'income': ingreso contable} de la obra,
        en la moneda de la compañía."""
        self.ensure_one()
        if not self.account_id:
            return {'cost': 0.0, 'income': 0.0}
        # sudo: la gerencia y la jefatura ven el costo de la obra aunque no
        # tengan acceso a Contabilidad; solo se suman importes.
        Line_sudo = self.env['account.analytic.line'].sudo()
        cost = Line_sudo._read_group(
            self._construction_analytic_domain(EXPENSE_TYPES, date_from, date_to), [],
            ['amount:sum'])[0][0] or 0.0
        income = Line_sudo._read_group(
            self._construction_analytic_domain(INCOME_TYPES, date_from, date_to), [],
            ['amount:sum'])[0][0] or 0.0
        # El gasto va en negativo en la analítica.
        return {'cost': -cost, 'income': income}

    @api.depends_context('company')
    def _compute_construction_accounting(self):
        for project in self:
            amounts = project._construction_accounting_amounts() if project.id and \
                project.is_construction_site else {'cost': 0.0, 'income': 0.0}
            project.construction_cost_executed = amounts['cost']
            project.construction_accounting_currency_id = \
                (project.company_id or self.env.company).currency_id

    def action_construction_cost_entries(self):
        """CR-62: el costo ejecutado lleva directo a sus apuntes, por cuenta."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Costo ejecutado · %s', self.display_name),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,pivot,form',
            'domain': list(self._construction_analytic_domain(EXPENSE_TYPES)),
            'context': {'group_by': ['general_account_id'], 'create': False},
        }
