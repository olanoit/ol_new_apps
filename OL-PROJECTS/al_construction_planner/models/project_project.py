# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

from .common import WEEKDAYS
from .construction_resource_plan import DRAFT_STATES, OPEN_STATES


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_plan_ids = fields.One2many(
        'construction.resource.plan', 'project_id', string='Planes de recursos')
    construction_plan_count = fields.Integer(
        string='Nº de planes de recursos', compute='_compute_construction_plan_count')
    construction_typology_ids = fields.One2many(
        'construction.typology', 'project_id', string='Tipologías')
    construction_typology_count = fields.Integer(
        string='Nº de tipologías', compute='_compute_construction_plan_count')

    # Semana de la obra (especificación: jueves a miércoles, liquidación el
    # jueves y pago el sábado; configurable por obra con valor por defecto de
    # la compañía).
    construction_week_start_day = fields.Selection(
        WEEKDAYS, string='Inicio de semana', compute='_compute_construction_week_days',
        store=True, readonly=False,
        help='Primer día de las semanas de liquidación de la obra; el cierre es el día '
             'anterior.')
    construction_settlement_day = fields.Selection(
        WEEKDAYS, string='Día de liquidación', compute='_compute_construction_week_days',
        store=True, readonly=False,
        help='Primer día con este nombre después del cierre de la semana. Si es feriado, se '
             'corre al día hábil anterior.')
    construction_payment_day = fields.Selection(
        WEEKDAYS, string='Día de pago', compute='_compute_construction_week_days',
        store=True, readonly=False,
        help='Primer día con este nombre desde la liquidación: es el vencimiento de la '
             'factura de la contrata. Si es feriado, se corre al día hábil anterior.')
    construction_settlement_count = fields.Integer(
        string='Nº de liquidaciones', compute='_compute_construction_settlement_count')

    @api.depends('company_id')
    def _compute_construction_week_days(self):
        for project in self:
            company = project.company_id or self.env.company
            project.construction_week_start_day = (
                project.construction_week_start_day or company.construction_week_start_day or '3')
            project.construction_settlement_day = (
                project.construction_settlement_day or company.construction_settlement_day or '3')
            project.construction_payment_day = (
                project.construction_payment_day or company.construction_payment_day or '5')

    def _compute_construction_settlement_count(self):
        counts = dict(self.env['construction.contract.settlement']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        for project in self:
            project.construction_settlement_count = counts.get(project, 0)

    def _construction_period(self, day):
        """Semana de liquidación que contiene ``day``: (inicio, fin)."""
        self.ensure_one()
        start_day = int(self.construction_week_start_day or '3')
        start = day - timedelta(days=(day.weekday() - start_day) % 7)
        return start, start + timedelta(days=6)

    def _construction_settlement_dates(self, period_start):
        """Fechas de liquidación y de pago de la semana que empieza en
        ``period_start``: el primer día de liquidación después del cierre y el
        primer día de pago desde ese día, corridos al día hábil anterior si
        caen en feriado del calendario de la compañía."""
        self.ensure_one()
        company = self.company_id or self.env.company
        after_close = period_start + timedelta(days=7)
        settlement_day = int(self.construction_settlement_day or '3')
        payment_day = int(self.construction_payment_day or '5')
        settlement = after_close + timedelta(days=(settlement_day - after_close.weekday()) % 7)
        payment = settlement + timedelta(days=(payment_day - settlement.weekday()) % 7)
        return (company._construction_previous_working_day(settlement),
                company._construction_previous_working_day(payment))

    def action_view_construction_settlements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Liquidaciones de %s', self.display_name),
            'res_model': 'construction.contract.settlement',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def _compute_construction_plan_count(self):
        plans = dict(self.env['construction.resource.plan']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        typologies = dict(self.env['construction.typology']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        for project in self:
            project.construction_plan_count = plans.get(project, 0)
            project.construction_typology_count = typologies.get(project, 0)

    def _construction_current_plan(self):
        """Plan vigente de la obra o, si aún no se aprobó ninguno, el que está
        en preparación."""
        self.ensure_one()
        Plan = self.env['construction.resource.plan']
        return (Plan.search([('project_id', '=', self.id), ('state', 'in', OPEN_STATES)], limit=1)
                or Plan.search([('project_id', '=', self.id), ('state', 'in', DRAFT_STATES)],
                               limit=1))

    def action_view_construction_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Planes de recursos'),
            'res_model': 'construction.resource.plan',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_construction_typologies(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Tipologías'),
            'res_model': 'construction.typology',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
