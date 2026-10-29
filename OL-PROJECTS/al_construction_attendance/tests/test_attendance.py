# -*- coding: utf-8 -*-
"""v1.5, fases 17 y 18: sedes, quiosco, marcación de contratas, avance sin
asistencia y costo de personal por sede."""
from datetime import date, datetime

from odoo.tests import HttpCase, tagged

from odoo.addons.al_construction_planner_suite.tests.common import PlannerCommon


@tagged('post_install', '-at_install')
class TestConstructionAttendance(HttpCase, PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['account.analytic.account']
        plan = cls.env['account.analytic.plan'].create({'name': 'Etapa (test asistencia)'})
        cls.ins = Account.create({'name': 'INS (test)', 'plan_id': plan.id})
        cost_plan = cls.env['account.analytic.plan'].create({'name': 'Partida (test asistencia)'})
        cls.modf = Account.create({'name': 'MODF (test)', 'plan_id': cost_plan.id})
        site_account = Account.create({'name': 'Obra MOMEN (test)', 'plan_id': cost_plan.id})
        cls.site = cls.env['l10n_pe.hr.construction.site'].create({
            'name': 'Sede MOMEN (test)', 'project_id': cls.project.id,
            'latitude': -12.0464, 'longitude': -77.0428, 'radius_m': 150,
            'entry_deadline': 7.0 + 50 / 60.0, 'analytic_account_id': site_account.id,
            'default_stage_account_id': cls.ins.id, 'company_id': cls.env.company.id})
        cls.env.company.construction_labor_cost_account_id = cls.modf
        cls.worker = cls.env['construction.contractor.worker'].create({
            'name': 'Juan Gonza (test)', 'document_number': '44556677',
            'partner_id': cls.contractor.id, 'sctr_valid_until': date(2020, 1, 1)})
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Obrero propio (test)', 'identification_id': '11223344',
            'company_id': cls.env.company.id})

    def test_site_distance_and_late(self):
        self.assertEqual(self.site._distance_to(-12.0464, -77.0428), 0.0)
        far = self.site._distance_to(-12.0500, -77.0428)
        self.assertTrue(390 < far < 410, far)
        self.assertTrue(self.site._out_of_range(-12.0500, -77.0428))
        # 7:55 en Lima = 12:55 UTC.
        self.assertTrue(self.site._is_late(datetime(2026, 11, 2, 12, 55)))
        self.assertFalse(self.site._is_late(datetime(2026, 11, 2, 12, 45)))
        self.assertEqual(self.project._construction_site(), self.site)
        self.assertEqual(self.project._construction_distance_m(-12.0464, -77.0428), 0.0)

    def test_attendance_takes_nearest_site(self):
        far = self.env['l10n_pe.hr.construction.site'].create({
            'name': 'Sede lejana (test)', 'latitude': -12.1500, 'longitude': -77.0200,
            'radius_m': 300, 'company_id': self.env.company.id})
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': datetime(2026, 9, 24, 12, 0),
            'check_out': datetime(2026, 9, 24, 20, 0),
            'in_latitude': -12.0470, 'in_longitude': -77.0428})
        self.assertEqual(attendance.l10n_pe_construction_site_id, self.site)
        self.assertAlmostEqual(attendance.l10n_pe_site_distance_m, 66.7, delta=1)
        self.assertFalse(attendance.l10n_pe_site_out_of_range)
        outside = self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': datetime(2026, 9, 25, 12, 0),
            'check_out': datetime(2026, 9, 25, 20, 0),
            'in_latitude': -12.1450, 'in_longitude': -77.0200})
        self.assertEqual(outside.l10n_pe_construction_site_id, far)
        self.assertTrue(outside.l10n_pe_site_out_of_range)
        # Sin ubicación no se asigna sede.
        manual = self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': datetime(2026, 9, 26, 12, 0)})
        self.assertFalse(manual.l10n_pe_construction_site_id)

    def test_kiosk_marks_employee_and_contractor(self):
        url = '/obra/quiosco/%s/%s' % (self.site.id, self.site.sudo().kiosk_token)
        self.assertEqual(self.url_open(url).status_code, 200)
        self.assertEqual(self.url_open('/obra/quiosco/%s/clave-falsa' % self.site.id).status_code, 404)
        page = self.url_open(url, data={'document': '44556677', 'latitude': '-12.0464',
                                        'longitude': '-77.0428'})
        self.assertIn('Ingreso registrado', page.text)
        self.assertIn('SCTR', page.text)
        attendance = self.env['construction.contractor.attendance'].search(
            [('worker_id', '=', self.worker.id)])
        self.assertEqual(attendance.site_id, self.site)
        self.assertTrue(attendance.sctr_expired)
        self.assertFalse(attendance.out_of_range)
        page = self.url_open(url, data={'document': '44556677'})
        self.assertIn('Salida registrada', page.text)
        self.assertTrue(attendance.check_out)
        page = self.url_open(url, data={'document': '11223344', 'latitude': '-12.0600',
                                        'longitude': '-77.0428'})
        self.assertIn('Ingreso registrado', page.text)
        self.assertIn('fuera del radio', page.text)
        own = self.env['hr.attendance'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(own.l10n_pe_construction_site_id, self.site)
        self.assertTrue(own.l10n_pe_site_out_of_range)
        self.assertIn('No se encontró', self.url_open(url, data={'document': '999'}).text)

    def test_progress_without_attendance(self):
        self._generate()
        line = self.plan.line_ids.filtered(lambda l: l.resource_type == 'contract')[0]
        line.partner_id = self.contractor
        self.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for plan_line in self.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            plan_line.price_unit_planned = 10.0
        self.plan.action_request_approval()
        photo = self.env['ir.attachment'].create({'name': 'foto.png', 'raw': 'eA=='})
        progress = self.env['construction.task.progress'].create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id, 'plan_line_id': line.id,
            'qty': 1, 'date': date(2026, 11, 2), 'attachment_ids': [(6, 0, photo.ids)]})
        self.assertFalse(progress.attendance_ok)
        self.assertIn(progress, self.env['construction.task.progress'].search(
            [('attendance_ok', '=', False)]))
        self.env['construction.contractor.attendance'].create({
            'worker_id': self.worker.id, 'site_id': self.site.id,
            'check_in': datetime(2026, 11, 2, 12, 30)})
        progress.invalidate_recordset(['attendance_ok'])
        self.assertTrue(progress.attendance_ok)

    def test_payroll_cost_keys_add_stage_and_modf(self):
        payslip = self.env['hr.payslip'].new({'company_id': self.env.company.id})
        account = self.site.analytic_account_id
        keys = payslip._l10n_pe_site_cost_keys({str(account.id): 60.0, '999999': 40.0})
        expected = ','.join(str(i) for i in sorted([account.id, self.ins.id, self.modf.id]))
        self.assertEqual(keys, {expected: 60.0, '999999': 40.0})

    def test_monthly_labor_cost_allocation(self):
        if not self.project.account_id:
            self.project._create_analytic_account()
        self.employee.sudo().hourly_cost = 12.5
        Attendance = self.env['hr.attendance']
        Attendance.create([
            {'employee_id': self.employee.id, 'l10n_pe_construction_site_id': self.site.id,
             'check_in': datetime(2026, 9, day, 13, 0), 'check_out': datetime(2026, 9, day, 21, 0)}
            for day in (1, 2)])
        # Fuera del mes: no cuenta.
        Attendance.create({'employee_id': self.employee.id,
                           'l10n_pe_construction_site_id': self.site.id,
                           'check_in': datetime(2026, 10, 1, 13, 0),
                           'check_out': datetime(2026, 10, 1, 21, 0)})
        allocation = self.env['construction.labor.cost.allocation'].create(
            {'date_from': date(2026, 9, 1)})
        self.assertEqual(allocation.date_to, date(2026, 9, 30))
        allocation.action_compute()
        line = allocation.line_ids
        self.assertEqual((line.employee_id, line.site_id), (self.employee, self.site))
        self.assertAlmostEqual(line.hours, 16.0, 1)
        self.assertAlmostEqual(allocation.amount_total, 200.0, 2)
        self.assertIn('Sede MOMEN (test)', allocation.summary_html)
        allocation.action_post()
        self.assertEqual(allocation.state, 'posted')
        entry = allocation.analytic_line_ids
        self.assertEqual(len(entry), 1)
        self.assertAlmostEqual(entry.amount, -200.0, 2)
        self.assertEqual(entry.account_id, self.project.account_id)
        self.assertEqual(entry[self.ins.plan_id._column_name()], self.ins)
        self.assertEqual(entry[self.modf.plan_id._column_name()], self.modf)
        allocation.action_draft()
        self.assertFalse(allocation.analytic_line_ids.exists())
