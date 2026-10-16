# -*- coding: utf-8 -*-
"""Cuadrillas, nómina, sedes y costo por jornal (v1.8, M18-06 a M18-08).

Criterio: al marcar un proyecto como obra se crea su sede; una cuadrilla de
un operario, un oficial y dos peones planificada por 5 días en día completo
muestra 20 jornales planificados; tras una semana de marcación, el control
muestra los jornales ejecutados y su costo contra lo planificado. Una sede de
planta no aparece en ningún proyecto."""
from datetime import date, datetime, timedelta

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.al_construction_planner_suite.tests.common import PlannerCommon

REF = 'al_hr_pe_construction.'
MONDAY = date(2026, 11, 2)


@tagged('post_install', '-at_install')
class TestCrewDays(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.construction_site_auto_create = True
        cls.company.construction_crew_time_unit = 'FULL'
        cls.company.construction_crew_hours_per_day = 8.0
        cls.project.construction_week_start_day = '0'
        cls.day = cls.env.ref('uom.product_uom_day')
        Role = cls.env['planning.role']
        cls.categories = {name: cls.env.ref(REF + 'category_%s' % name)
                          for name in ('operario', 'oficial', 'peon')}
        cls.roles = {name: Role.create({'name': '%s (test v18)' % name.title(),
                                        'construction_category_id': category.id})
                     for name, category in cls.categories.items()}
        cls.activity = cls.env['construction.labor.activity'].create({
            'code': 'T18-CUA', 'name': 'Cuadrilla de instalación (test)', 'stage': 'installation',
            'uom_id': cls.day.id, 'default_price': 70.0})
        cls.line = cls.env['construction.resource.plan.line'].create({
            'plan_id': cls.plan.id, 'task_id': cls.space_501.id, 'resource_type': 'labor',
            'activity_id': cls.activity.id, 'stage': 'installation', 'qty_planned': 20.0,
            'price_unit_planned': 70.0, 'product_uom_id': cls.day.id})
        cls.plan.action_request_approval()

        def employee(name, category):
            record = cls.env['hr.employee'].create({'name': name, 'company_id': cls.company.id})
            record.version_id.l10n_pe_construction_category_id = cls.categories[category]
            return record

        cls.crew = [employee('Operario v18 (test)', 'operario'),
                    employee('Oficial v18 (test)', 'oficial'),
                    employee('Peón 1 v18 (test)', 'peon'), employee('Peón 2 v18 (test)', 'peon')]
        cls.crew_roles = ['operario', 'oficial', 'peon', 'peon']

    def _wage(self, category, day=MONDAY):
        table = self.env['l10n_pe.hr.construction.wage.table']._get_table_for_date(day, self.company)
        return table.line_ids.filtered(lambda l: l.category_id == self.categories[category])[:1].daily_wage

    def _wizard(self, members):
        return self.env['construction.plan.crew.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.space_501.ids,
        ).create({'time_mode': 'days', 'days_per_week': 5, 'weeks': 1, 'date_start': MONDAY,
                  'member_ids': [Command.create({'resource_id': employee.resource_id.id,
                                                 'role_id': self.roles[role].id})
                                 for employee, role in members]})

    def test_site_created_with_the_project(self):
        site = self.env['project.project'].create({'name': 'Obra con sede (test)',
                                                   'is_construction_site': True})
        sede = site.construction_hr_site_ids
        self.assertEqual(len(sede), 1)
        self.assertEqual(sede.name, 'Obra con sede (test)')
        self.assertEqual(sede.analytic_account_id, site.account_id)
        self.assertEqual(sede.site_kind, 'site')
        self.assertEqual(sede.radius_m, self.company.construction_site_radius_m)
        plant = self.env['l10n_pe.hr.construction.site'].create({
            'name': 'Planta central (test)', 'site_kind': 'plant', 'company_id': self.company.id})
        self.assertFalse(plant.project_id)
        with self.assertRaises(ValidationError):
            plant.project_id = site

    def test_crew_in_days_against_attendance(self):
        wizard = self._wizard(list(zip(self.crew, self.crew_roles)))
        self.assertAlmostEqual(wizard.days_total, 20.0)
        wizard.action_assign()
        CrewDay = self.env['construction.crew.day']
        planned = CrewDay.search([('project_id', '=', self.project.id), ('kind', '=', 'planned')])
        self.assertAlmostEqual(sum(planned.mapped('days')), 20.0)
        expected = 5 * (self._wage('operario') + self._wage('oficial') + 2 * self._wage('peon'))
        self.assertAlmostEqual(sum(planned.mapped('amount')), round(expected, 2), places=2)
        self.assertEqual(set(planned.mapped('stage')), {'installation'})
        # Una semana de marcación en la sede de la obra (8:00 a 16:00 en Lima).
        sede = self.project.construction_hr_site_ids[:1] or self.env[
            'l10n_pe.hr.construction.site'].create({
                'name': 'Sede MOMEN v18 (test)', 'project_id': self.project.id,
                'company_id': self.company.id})
        for employee in self.crew:
            for offset in range(5):
                day = MONDAY + timedelta(days=offset)
                self.env['hr.attendance'].create({
                    'employee_id': employee.id, 'l10n_pe_construction_site_id': sede.id,
                    'check_in': datetime.combine(day, datetime.min.time()) + timedelta(hours=13),
                    'check_out': datetime.combine(day, datetime.min.time()) + timedelta(hours=21)})
        executed = CrewDay.search([('project_id', '=', self.project.id),
                                   ('kind', '=', 'executed')])
        self.assertAlmostEqual(sum(executed.mapped('days')), 20.0)
        self.assertEqual(executed.plan_line_id, self.line)
        self.assertAlmostEqual(sum(executed.mapped('amount')), round(expected, 2), places=2)
        # El análisis por etapa: planificado contra ejecutado.
        groups = {kind: (days, amount) for kind, days, amount in CrewDay._read_group(
            [('project_id', '=', self.project.id), ('stage', '=', 'installation')],
            ['kind'], ['days:sum', 'amount:sum'])}
        self.assertAlmostEqual(groups['planned'][0], groups['executed'][0])

    def test_member_category_must_match(self):
        wrong = list(zip(self.crew, ['operario', 'oficial', 'operario', 'peon']))
        with self.assertRaises(UserError):
            self._wizard(wrong).action_assign()

    def test_half_day_rounding(self):
        self.project.construction_crew_time_unit = 'HALF'
        self.assertEqual(self.project._construction_round_days(5.5 / 8), 0.5)
        self.assertEqual(self.project._construction_round_days(7.0 / 8), 1.0)
        self.project.construction_crew_time_unit = 'NO'
        self.assertAlmostEqual(self.project._construction_round_days(6.0 / 8), 0.75)
