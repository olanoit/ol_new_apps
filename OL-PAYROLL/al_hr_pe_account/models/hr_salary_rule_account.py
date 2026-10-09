# -*- coding: utf-8 -*-
"""Cuentas contables por condición en las reglas salariales.

En Odoo 19 una regla tiene una sola cuenta de cargo y una de abono
(``company_dependent``). v18 permitía además una cuenta distinta por
centro de costo (``hr.salary.rule.line``: cuenta analítica → cuenta).
Esta tabla lo generaliza: por tipo de trabajador (T08), departamento y/o
cuenta analítica se elige otra cuenta de cargo y/o de abono; lo que la
fila deja vacío conserva la cuenta de la regla.

Prioridad: gana la fila con **más condiciones** que se cumplen (la más
específica); a igualdad, la de menor secuencia. Se aplica al armar el
asiento de planilla por lote (``hr.payslip.run._pe_prepare_batch_move_lines``).
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

CONDITION_FIELDS = ('worker_type_id', 'department_id', 'analytic_account_id')


class HrSalaryRuleAccount(models.Model):
    _name = 'l10n_pe.hr.salary.rule.account'
    _description = 'Cuenta de la regla salarial por condición'
    _order = 'salary_rule_id, sequence, id'
    _check_company_auto = True

    salary_rule_id = fields.Many2one(
        'hr.salary.rule', string='Regla salarial', required=True,
        index=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        readonly=True, default=lambda self: self.env.company)
    sequence = fields.Integer(string='Secuencia', default=10)
    worker_type_id = fields.Many2one(
        'hr.worker.type', string='Tipo de trabajador', check_company=True,
        help='Tipo de trabajador (T08) de la ficha: p. ej. empleado u obrero.')
    department_id = fields.Many2one(
        'hr.department', string='Departamento', check_company=True)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Centro de costo', check_company=True,
        help='Se aplica a la parte del importe que va a este centro de costo '
             '(distribución analítica de la regla, del tareaje o de la ficha).')
    account_debit_id = fields.Many2one(
        'account.account', string='Cuenta de cargo', check_company=True,
        help='Vacía: la cuenta de cargo de la regla.')
    account_credit_id = fields.Many2one(
        'account.account', string='Cuenta de abono', check_company=True,
        help='Vacía: la cuenta de abono de la regla.')

    @api.constrains(*CONDITION_FIELDS, 'account_debit_id', 'account_credit_id')
    def _check_condition_and_account(self):
        for record in self:
            if not any(record[name] for name in CONDITION_FIELDS):
                raise ValidationError(self.env._(
                    'Indique al menos una condición (tipo de trabajador, '
                    'departamento o centro de costo) en la regla %(rule)s.',
                    rule=record.salary_rule_id.display_name))
            if not (record.account_debit_id or record.account_credit_id):
                raise ValidationError(self.env._(
                    'Indique la cuenta de cargo o la de abono en la regla %(rule)s.',
                    rule=record.salary_rule_id.display_name))

    def _l10n_pe_matches(self, worker_type, department, analytic_ids):
        self.ensure_one()
        return ((not self.worker_type_id or self.worker_type_id == worker_type)
                and (not self.department_id or self.department_id == department)
                and (not self.analytic_account_id or self.analytic_account_id.id in analytic_ids))

    def _l10n_pe_specificity(self):
        self.ensure_one()
        return sum(1 for name in CONDITION_FIELDS if self[name])


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    l10n_pe_account_ids = fields.One2many(
        'l10n_pe.hr.salary.rule.account', 'salary_rule_id',
        string='Cuentas por condición',
        domain=lambda self: [('company_id', 'in', self.env.companies.ids)])

    def _l10n_pe_rule_account_lines(self, company):
        self.ensure_one()
        # sudo: el gestor de nómina arma el asiento aunque no tenga acceso
        # de lectura a la configuración contable de otra compañía; se
        # filtra explícitamente por la compañía del lote.
        return self.sudo().l10n_pe_account_ids.filtered(lambda line: line.company_id == company)

    def _l10n_pe_uses_analytic_accounts(self, company):
        """True si alguna fila de la compañía depende del centro de costo:
        entonces el importe se reparte por centro de costo antes de elegir
        la cuenta."""
        self.ensure_one()
        return any(self._l10n_pe_rule_account_lines(company).mapped('analytic_account_id'))

    def _l10n_pe_get_accounts(self, company, version, analytic_ids=()):
        """``(cuenta de cargo, cuenta de abono)`` para un trabajador.

        :param version: ``hr.version`` de la boleta (tipo de trabajador y
            departamento).
        :param analytic_ids: ids de las cuentas analíticas de la parte del
            importe que se contabiliza.
        """
        self.ensure_one()
        rule = self.with_company(company)
        debit, credit = rule.account_debit, rule.account_credit
        lines = self._l10n_pe_rule_account_lines(company)
        if not lines:
            return debit, credit
        # sudo: tipo de trabajador y departamento de la ficha son campos
        # de RR. HH. (groups=hr.group_hr_user); solo se leen para elegir
        # la cuenta.
        version_sudo = version.sudo()
        candidates = lines.filtered(lambda line: line._l10n_pe_matches(
            version_sudo.worker_type_id, version_sudo.department_id, set(analytic_ids)))
        if not candidates:
            return debit, credit
        best = candidates.sorted(
            key=lambda line: (-line._l10n_pe_specificity(), line.sequence, line.id))[0]
        return (best.account_debit_id.sudo(False) or debit,
                best.account_credit_id.sudo(False) or credit)
