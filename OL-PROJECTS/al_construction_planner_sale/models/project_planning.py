# -*- coding: utf-8 -*-
"""Pestaña «Planificación» de la obra (v1.5, fase 20, M15-14).

Tres márgenes, cada uno con su ingreso y su costo:

* **Planificado**: lo contratado (contratos de obra con sus adicionales y
  deductivos aprobados o, sin contratos, la orden de venta de la obra) contra
  el plan vigente.
* **Devengado**: lo valorizado y confirmado por el cliente contra el costo
  real de las líneas del plan (consumido, recibido y horas).
* **Contable**: los apuntes analíticos de la cuenta de la obra (ingresos en
  positivo, costos en negativo).
"""
from odoo import api, fields, models

EARNED_VALUATION_STATES = ('confirmed', 'invoiced')


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_income_planned = fields.Monetary(
        string='Ingreso contratado', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True,
        help='Contratos de obra con sus cambios aprobados o, sin contratos, la orden de venta '
             'de la obra (sin impuestos).')
    construction_cost_planned = fields.Monetary(
        string='Costo planificado', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True,
        help='Líneas del plan vigente.')
    construction_margin_planned = fields.Monetary(
        string='Margen planificado', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True)
    construction_margin_planned_pct = fields.Float(
        string='% planificado', compute='_compute_construction_margins', compute_sudo=True)
    construction_income_earned = fields.Monetary(
        string='Ingreso devengado', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True,
        help='Valorizaciones confirmadas por el cliente o facturadas.')
    construction_cost_accrued = fields.Monetary(
        string='Costo real', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True,
        help='Real de las líneas del plan vigente: consumido, recibido en OC de servicio y horas.')
    construction_margin_accrued = fields.Monetary(
        string='Margen devengado', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True)
    construction_margin_accrued_pct = fields.Float(
        string='% devengado', compute='_compute_construction_margins', compute_sudo=True)
    construction_income_accounting = fields.Monetary(
        string='Ingreso contable', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True,
        help='Apuntes analíticos positivos de la cuenta de la obra.')
    construction_cost_accounting = fields.Monetary(
        string='Costo contable', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True,
        help='Apuntes analíticos negativos de la cuenta de la obra.')
    construction_margin_accounting = fields.Monetary(
        string='Margen contable', compute='_compute_construction_margins',
        currency_field='construction_margin_currency_id', compute_sudo=True)
    construction_margin_accounting_pct = fields.Float(
        string='% contable', compute='_compute_construction_margins', compute_sudo=True)
    construction_margin_currency_id = fields.Many2one(
        'res.currency', string='Moneda de los márgenes',
        compute='_compute_construction_margins', compute_sudo=True)

    @staticmethod
    def _construction_pct(margin, income):
        return margin / income if income else 0.0

    @api.depends_context('company')
    def _compute_construction_margins(self):
        Valuation = self.env['construction.valuation']
        AnalyticLine = self.env['account.analytic.line']
        for project in self:
            company = project.company_id or self.env.company
            currency = company.currency_id
            plan = project._construction_current_plan() if project.is_construction_site \
                and project.id else self.env['construction.resource.plan']
            lines = plan.line_ids.filtered(lambda l: l.line_state != 'cancel')
            contracts = self.env['construction.contract'].search([
                ('project_id', '=', project.id), ('state', 'in', ('draft', 'active', 'closed'))]) \
                if project.id else self.env['construction.contract']
            if contracts:
                income = sum(c.currency_id._convert(
                    c.amount_total + c.amount_changes, currency, company, fields.Date.today())
                    for c in contracts)
            else:
                order = project.construction_sale_order_id
                income = order.currency_id._convert(
                    order.amount_untaxed, currency, company, fields.Date.today()) if order else 0.0
            cost = sum(lines.mapped('amount_planned'))
            earned = sum(Valuation.search([
                ('project_id', '=', project.id),
                ('state', 'in', EARNED_VALUATION_STATES)]).mapped('amount_confirmed')) \
                if project.id else 0.0
            accrued = sum(lines.mapped('amount_actual'))
            acc_income = acc_cost = 0.0
            if project.account_id:
                positive = AnalyticLine._read_group(
                    [('account_id', '=', project.account_id.id), ('amount', '>', 0)],
                    aggregates=['amount:sum'])[0][0]
                negative = AnalyticLine._read_group(
                    [('account_id', '=', project.account_id.id), ('amount', '<', 0)],
                    aggregates=['amount:sum'])[0][0]
                acc_income, acc_cost = positive or 0.0, -(negative or 0.0)
            project.update({
                'construction_margin_currency_id': currency,
                'construction_income_planned': income,
                'construction_cost_planned': cost,
                'construction_margin_planned': income - cost,
                'construction_margin_planned_pct': self._construction_pct(income - cost, income),
                'construction_income_earned': earned,
                'construction_cost_accrued': accrued,
                'construction_margin_accrued': earned - accrued,
                'construction_margin_accrued_pct': self._construction_pct(earned - accrued, earned),
                'construction_income_accounting': acc_income,
                'construction_cost_accounting': acc_cost,
                'construction_margin_accounting': acc_income - acc_cost,
                'construction_margin_accounting_pct': self._construction_pct(
                    acc_income - acc_cost, acc_income),
            })
