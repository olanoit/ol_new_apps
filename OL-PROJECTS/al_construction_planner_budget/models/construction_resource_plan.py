# -*- coding: utf-8 -*-
"""Presupuesto analítico del plan (fase 3, en su puente desde la v1.7): una
línea de presupuesto por combinación de cuentas al aprobar, la versión
anterior pasa a «Revisado», los cambios aprobados se suman y el cierre lo da
por hecho."""
from collections import defaultdict

from odoo import Command, fields, models


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    budget_analytic_id = fields.Many2one(
        'budget.analytic', string='Presupuesto analítico', readonly=True, copy=False,
        check_company=True, help='Lo crea la aprobación del plan.')

    def _construction_on_approve(self, previous):
        values = super()._construction_on_approve(previous)
        budget = self._create_budget(parent_budget=previous.budget_analytic_id)
        return dict(values, budget_analytic_id=budget.id)

    def _construction_lines_added(self, lines):
        super()._construction_lines_added(lines)
        if self.budget_analytic_id:
            self._construction_add_to_budget(lines)

    def _construction_on_close(self):
        super()._construction_on_close()
        # sudo: mismo motivo que al crearlo (permisos de contabilidad).
        self.budget_analytic_id.sudo().filtered(
            lambda b: b.state == 'confirmed').action_budget_done()

    def _get_budget_line_values(self):
        """Una línea de presupuesto por combinación de cuentas analíticas.

        La distribución de cada línea del plan (o, vacía, la cuenta de la
        obra al 100 %) se reparte por sus claves «id1,id2,…»; cada cuenta va
        a la columna de su plan raíz (``account_id`` para el plan de
        proyectos, ``x_plan<N>_id`` para los demás). El redondeo se corrige
        en la combinación mayor para que el total cuadre con el plan."""
        self.ensure_one()
        Account = self.env['account.analytic.account']
        project_account = self.project_id.account_id
        default = {str(project_account.id): 100.0} if project_account else {}
        combos = defaultdict(float)
        key_cache = {}
        for line in self.line_ids.filtered(lambda l: l.line_state != 'cancel'):
            for key, percentage in (line.analytic_distribution or default).items():
                if key not in key_cache:
                    accounts = Account.browse(int(a) for a in key.split(',') if a).exists()
                    key_cache[key] = tuple(sorted(
                        (account.root_plan_id._column_name(), account.id)
                        for account in accounts))
                combos[key_cache[key]] += line.amount_planned * percentage / 100.0
        currency = self.currency_id
        values = [{**dict(combo), 'budget_amount': currency.round(amount)}
                  for combo, amount in combos.items() if combo]
        if values:
            difference = currency.round(sum(combos.values())) - sum(
                v['budget_amount'] for v in values)
            if not currency.is_zero(difference):
                biggest = max(values, key=lambda v: abs(v['budget_amount']))
                biggest['budget_amount'] = currency.round(biggest['budget_amount'] + difference)
        return values

    def _construction_match_budget_line(self, combo):
        """Línea del presupuesto analítico del plan que cubre una combinación
        de cuentas ({columna: id}): la que tiene todas sus cuentas en la
        combinación (sus columnas vacías no filtran, como en el informe de
        presupuesto de Odoo) y, entre ellas, la más específica."""
        self.ensure_one()
        best, best_size = self.env['budget.line'], 0
        for budget_line in self.budget_analytic_id.budget_line_ids:
            values = {fname: budget_line[fname].id for fname in budget_line._get_plan_fnames()
                      if budget_line[fname]}
            if values and len(values) > best_size and all(
                    combo.get(fname) == value for fname, value in values.items()):
                best, best_size = budget_line, len(values)
        return best

    def _create_budget(self, parent_budget=False):
        self.ensure_one()
        line_values = self._get_budget_line_values()
        # sudo: quien aprueba el plan (jefatura) no suele tener permisos de
        # contabilidad; el presupuesto es una consecuencia de la aprobación y
        # sus valores salen del plan, no del usuario.
        budget_sudo = self.env['budget.analytic'].sudo().create({
            'name': '%s · %s' % (self.project_id.name, self.display_name),
            'date_from': self.date_start,
            'date_to': self.date_end,
            'budget_type': 'expense',
            'company_id': self.company_id.id,
            'user_id': self.user_id.id,
            'parent_id': parent_budget.id if parent_budget else False,
            'budget_line_ids': [Command.create(vals) for vals in line_values],
        })
        # Con versión anterior, su presupuesto pasa a «Revisado» (archivado):
        # es el mecanismo de revisiones de account_budget.
        budget_sudo.action_budget_confirm()
        return budget_sudo.sudo(False)

    def action_view_budget(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Presupuesto analítico'),
            'res_model': 'budget.analytic',
            'view_mode': 'form',
            'res_id': self.budget_analytic_id.id,
        }

    def _construction_add_to_budget(self, lines):
        """Suma ``lines`` al presupuesto analítico del plan: a la línea de
        presupuesto de su misma combinación de cuentas o, si no existe, a una
        nueva."""
        self.ensure_one()
        Account = self.env['account.analytic.account']
        project_account = self.project_id.account_id
        default = {str(project_account.id): 100.0} if project_account else {}
        combos = {}
        for line in lines:
            for key, percentage in (line.analytic_distribution or default).items():
                accounts = Account.browse(int(a) for a in key.split(',') if a).exists()
                combo = tuple(sorted((a.root_plan_id._column_name(), a.id) for a in accounts))
                if combo:
                    combos[combo] = combos.get(combo, 0.0) + \
                        line.amount_planned * percentage / 100.0
        # sudo: la jefatura que aprueba el cambio no suele tener permisos de
        # contabilidad; el presupuesto es consecuencia de la aprobación y sus
        # valores salen del plan.
        budget_sudo = self.budget_analytic_id.sudo()
        for combo, amount in combos.items():
            values = dict(combo)
            match = budget_sudo.budget_line_ids.filtered(lambda b: all(
                b[fname].id == values.get(fname) for fname in b._get_plan_fnames()))
            if match:
                match[0].budget_amount += self.currency_id.round(amount)
            else:
                budget_sudo.write({'budget_line_ids': [Command.create(
                    dict(values, budget_amount=self.currency_id.round(amount)))]})
