# -*- coding: utf-8 -*-
"""Control semanal de mano de obra (paquete 1.19, M119-02), con los criterios:

* Contrata de instalación, semana completa: 41.23 ML validados, rendimiento
  exigido 7.60 y 2 personas que marcaron 45 h cada una: 11.25 persona-días,
  rendimiento real 3.66 (−51.8 %), personal esperado 1 y «Exceso de
  personal». Con 1 persona: 7.33 (−3.6 %) y ningún aviso.
* Personal propio del ejemplo de M119-01, primera semana: meta 91.84, avance
  88 y 4 personas de 45 h: 22.5 persona-días, S/ 2,700, rendimiento real 3.91
  (−4.2 %), «Atraso» de 3.84 y ningún exceso (el avance justifica 21.56
  persona-días; la banda llega a 23.72).
* Segunda semana con 5 personas y 95 ML: rendimiento real 3.38 (−17.2 %),
  «Exceso de personal»; acumulado 50.63 persona-días y S/ 6,075 frente a 44.84 y
  S/ 5,380: la semana 2 es la primera sobre el presupuesto."""
import base64
from datetime import date, datetime, timedelta

from odoo.tests import tagged

from odoo.addons.al_construction_planner.tests.test_package_119_schedule import site_calendar
from odoo.addons.al_construction_planner_suite.tests.common import PlannerCommon

MONDAY = date(2026, 11, 2)


@tagged('post_install', '-at_install')
class TestLaborWeeklyControl(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.resource_calendar_id.tz = 'America/Lima'
        cls.company.construction_site_calendar_id = site_calendar(cls.env, cls.company)
        meter = cls.env.ref('uom.product_uom_meter')
        cls.activity = cls.env['construction.labor.activity'].create({
            'code': 'T19C-INS', 'name': 'Instalación ML (test control)', 'stage': 'installation',
            'uom_id': meter.id, 'productivity': 4.0, 'default_price': 7.0})
        cls.stage = cls.env['construction.stage'].search([('code', '=', 'installation')])
        cls.contractor = cls.env['res.partner'].create({'name': 'Contrata instalación (test)'})
        cls.sede = cls.project.construction_hr_site_ids[:1] or cls.env[
            'l10n_pe.hr.construction.site'].create({
                'name': 'Sede control (test)', 'project_id': cls.project.id,
                'company_id': cls.company.id})
        cls.Control = cls.env['construction.labor.weekly.control']

    def _budget(self, mode, qty, productivity, wage=120.0, rate=7.0):
        return self.env['construction.labor.budget'].create({
            'project_id': self.project.id, 'stage_id': self.stage.id, 'mode': mode,
            'date_start': MONDAY, 'date_end': date(2026, 12, 1), 'band': 10.0,
            'daily_wage': wage,
            'line_ids': [(0, 0, {'activity_id': self.activity.id, 'quantity': qty,
                                 'productivity': productivity, 'rate': rate})]})

    def _line(self, resource_type):
        values = {
            'plan_id': self.plan.id, 'task_id': self.space_501.id,
            'resource_type': resource_type, 'activity_id': self.activity.id,
            'stage': 'installation', 'qty_planned': 400.0, 'price_unit_planned': 7.0,
            'product_uom_id': self.activity.uom_id.id}
        if resource_type == 'contract':
            values['partner_id'] = self.contractor.id
        line = self.env['construction.resource.plan.line'].create(values)
        if self.plan.state == 'draft':
            self.plan.action_request_approval()
        return line

    def _progress(self, line, qty, day):
        photo = self.env['ir.attachment'].create({'name': 'f.png',
                                                  'datas': base64.b64encode(b'x')})
        progress = self.env['construction.task.progress'].create({
            'task_id': line.task_id.id, 'activity_id': self.activity.id,
            'plan_line_id': line.id, 'date': day, 'qty': qty,
            'attachment_ids': [(6, 0, photo.ids)]})
        # El informe solo lee el estado: se valida sin pasar por el flujo.
        progress.sudo().write({'state': 'validated'})
        return progress

    def _contract_worker_week(self, name, monday):
        worker = self.env['construction.contractor.worker'].create({
            'name': name, 'document_number': name, 'partner_id': self.contractor.id,
            'company_id': self.company.id})
        for offset, hours in enumerate((9, 9, 9, 9, 9, 5)):
            day = monday + timedelta(days=offset)
            start = datetime.combine(day, datetime.min.time()) + timedelta(hours=13)
            # 8 h efectivas de lunes a viernes (marcan el refrigerio aparte).
            worked = 8 if hours == 9 else 5
            self.env['construction.contractor.attendance'].create({
                'worker_id': worker.id, 'site_id': self.sede.id, 'check_in': start,
                'check_out': start + timedelta(hours=worked)})
        return worker

    def test_contract_excess_of_staff(self):
        # 7.6 × 24.5 × 2 = 372.4: dos personas exactas, rendimiento exigido 7.60.
        budget = self._budget('contract', 372.4, 7.6)
        line = self._line('contract')
        self._progress(line, 41.23, MONDAY)
        self._contract_worker_week('C1', MONDAY)
        self._contract_worker_week('C2', MONDAY)
        rows = self.Control._construction_refresh(self.project).filtered(
            lambda r: r.week_start == MONDAY)
        self.assertEqual(len(rows), 1)
        row = rows
        self.assertEqual(row.partner_id, self.contractor)
        self.assertAlmostEqual(row.person_days_real, 11.25, places=2)
        self.assertEqual(row.persons, 2)
        exigido = budget._required_productivity(self.activity)
        self.assertAlmostEqual(row.required_productivity, exigido, places=4)
        self.assertAlmostEqual(row.real_productivity, 41.23 / 11.25, places=2)
        self.assertTrue(row.excess_staff)
        self.assertEqual(round(row.expected_persons), 1)

    def test_contract_one_person_is_fine(self):
        self._budget('contract', 372.4, 7.6)
        line = self._line('contract')
        self._progress(line, 41.23, MONDAY)
        self._contract_worker_week('C1', MONDAY)
        row = self.Control._construction_refresh(self.project).filtered(
            lambda r: r.week_start == MONDAY)
        self.assertAlmostEqual(row.person_days_real, 5.625, places=3)
        self.assertAlmostEqual(row.real_productivity, 7.33, places=2)
        self.assertFalse(row.excess_staff)

    def _own_days(self, line, persons, monday):
        CrewDay = self.env['construction.crew.day']
        for person in range(persons):
            employee = self.env['hr.employee'].create({
                'name': 'Jornalero %s %s (test)' % (person, monday), 'company_id': self.company.id})
            for offset, days in enumerate((1, 1, 1, 1, 1, 0.625)):
                CrewDay.create({
                    'kind': 'executed', 'project_id': self.project.id,
                    'company_id': self.company.id, 'plan_line_id': line.id,
                    'task_id': line.task_id.id, 'employee_id': employee.id,
                    'date': monday + timedelta(days=offset), 'days': days, 'source': 'attendance'})

    def test_own_staff_two_weeks(self):
        budget = self._budget('own', 400.0, 4.0)
        self.assertEqual(budget.persons, 4)
        line = self._line('labor')
        self._progress(line, 88.0, MONDAY)
        self._own_days(line, 4, MONDAY)
        second = MONDAY + timedelta(days=7)
        self._progress(line, 95.0, second)
        self._own_days(line, 5, second)
        rows = self.Control._construction_refresh(self.project).sorted('week_start')
        first, other = rows[0], rows[1]
        self.assertAlmostEqual(first.target, 91.84, places=2)
        self.assertAlmostEqual(first.person_days_real, 22.5, places=2)
        self.assertAlmostEqual(first.amount_real, 2700.0, places=2)
        self.assertAlmostEqual(first.real_productivity, 3.91, places=2)
        self.assertAlmostEqual(first.productivity_deviation, -4.2, places=1)
        self.assertTrue(first.delay)
        self.assertAlmostEqual(first.target_cumulative - first.progress_cumulative, 3.84,
                               places=2)
        self.assertFalse(first.excess_staff)
        self.assertFalse(first.over_budget)
        self.assertAlmostEqual(first.progress_person_days, 21.56, places=2)
        self.assertAlmostEqual(other.real_productivity, 3.38, places=2)
        # El requerimiento dice −17.3 %; la cuenta exacta (3.378 ÷ 4.0816) da −17.24 %.
        self.assertAlmostEqual(other.productivity_deviation, -17.2, places=1)
        self.assertTrue(other.excess_staff)
        self.assertAlmostEqual(other.person_days_real_cumulative, 50.625, places=3)
        self.assertAlmostEqual(other.amount_real_cumulative, 6075.0, places=2)
        self.assertAlmostEqual(other.progress_person_days_cumulative, 44.84, delta=0.01)
        self.assertAlmostEqual(other.progress_amount_cumulative, 5380.2, delta=0.01)
        self.assertTrue(other.over_budget)
        self.assertTrue(other.first_over_budget)
        # Usar como rendimiento medido.
        other.action_use_as_measured()
        row = self.project.construction_productivity_ids.filtered(
            lambda r: r.activity_id == self.activity)
        self.assertEqual(row.origin, 'measured')
        self.assertAlmostEqual(row.productivity, 3.3778, places=3)

    def test_activity_without_productivity(self):
        self._budget('own', 400.0, 0.0)
        line = self._line('labor')
        self._progress(line, 10.0, MONDAY)
        row = self.Control._construction_refresh(self.project)[:1]
        self.assertTrue(row.missing_productivity)
        self.assertFalse(row.real_productivity)
        self.assertFalse(row.expected_persons)
        self.assertIn('Sin rendimiento', row.warning)

    def test_excess_band_of_its_own(self):
        """Corrección 1 del 1.19: con la banda del aviso en 20 %, la segunda
        semana (−17.24 %) no avisa «Exceso de personal»; el presupuesto no
        cambia y «Sobre el presupuesto» sigue con la banda del rendimiento."""
        budget = self._budget('own', 400.0, 4.0)
        line = self._line('labor')
        self._progress(line, 88.0, MONDAY)
        self._own_days(line, 4, MONDAY)
        second = MONDAY + timedelta(days=7)
        self._progress(line, 95.0, second)
        self._own_days(line, 5, second)
        other = self.Control._construction_refresh(self.project).sorted('week_start')[1]
        self.assertTrue(other.excess_staff)
        budget.excess_band = 20.0
        other = self.Control.search([('project_id', '=', self.project.id)]).sorted(
            'week_start')[1]
        self.assertFalse(other.excess_staff)
        self.assertTrue(other.over_budget)
        self.assertEqual(budget.persons, 4)
        self.assertAlmostEqual(budget.person_days_budget, 98.0)
        self.assertAlmostEqual(budget.amount, 11760.0, places=2)
