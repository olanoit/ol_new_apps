# -*- coding: utf-8 -*-
"""Paquete 1.11, M111-01: avances y liquidaciones sin permisos de Nómina."""
from datetime import date, datetime

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_planner_suite.tests.common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPermissionsV111(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = cls.env['l10n_pe.hr.construction.site'].create({
            'name': 'Sede MOMEN (test v111)', 'project_id': cls.project.id,
            'latitude': -12.0464, 'longitude': -77.0428, 'radius_m': 150,
            'company_id': cls.env.company.id})
        cls.worker = cls.env['construction.contractor.worker'].create({
            'name': 'Juan Gonza (test v111)', 'document_number': '44556688',
            'partner_id': cls.contractor.id})
        # El supervisor de obra (Planificador) no tiene ningún grupo de Nómina.
        assert not cls.planner.has_group('hr_payroll.group_hr_payroll_user')

    def _progress(self, day):
        self._generate()
        line = self.plan.line_ids.filtered(lambda l: l.resource_type == 'contract')[0]
        line.partner_id = self.contractor
        self.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for plan_line in self.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            plan_line.price_unit_planned = 10.0
        self.plan.action_request_approval()
        photo = self.env['ir.attachment'].create({'name': 'foto.png', 'raw': 'eA=='})
        return self.env['construction.task.progress'].create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
            'plan_line_id': line.id, 'qty': 1, 'date': day,
            'attachment_ids': [(6, 0, photo.ids)]})

    def test_progress_and_settlement_without_payroll(self):
        progress = self._progress(date(2026, 11, 2))
        self.env['construction.contractor.attendance'].create({
            'worker_id': self.worker.id, 'site_id': self.site.id,
            'check_in': datetime(2026, 11, 2, 12, 30)})
        as_planner = progress.with_user(self.planner)
        # Lista de avances: la columna «Con asistencia».
        self.assertTrue(as_planner.attendance_ok)
        as_planner.web_read({'attendance_ok': {}, 'distance_m': {}})
        # Validar el avance.
        as_planner.action_validate()
        self.assertEqual(progress.state, 'validated')
        # Abrir la liquidación con la pestaña «Avances liquidados».
        settlement = self.env['construction.contract.settlement'].create({
            'partner_id': self.contractor.id, 'project_id': self.project.id,
            'period_start': date(2026, 10, 29)})
        progress.settlement_id = settlement
        self.assertIn(progress, settlement.progress_ids)
        settlement.with_user(self.planner).web_read({
            'name': {}, 'progress_ids': {'fields': {'attendance_ok': {}, 'qty': {}}}})

    def test_menu_without_attendance_matches_admin(self):
        progress = self._progress(date(2026, 11, 3))
        domain = [('attendance_ok', '=', False)]
        Progress = self.env['construction.task.progress']
        self.assertIn(progress, Progress.search(domain))
        self.assertEqual(Progress.with_user(self.planner).search(domain).ids,
                         Progress.search(domain).ids)

    def test_sites_stay_private(self):
        with self.assertRaises(AccessError):
            self.site.with_user(self.planner).read(['name'])
        # La obra se lee entera (exportar, duplicar) sin el campo de las sedes.
        project = self.project.with_user(self.planner)
        self.assertNotIn('construction_hr_site_ids', project.fields_get())
        project.read(['name'])
        # Marcar una obra sin Nómina crea su sede sin error.
        self.env.company.construction_site_auto_create = True
        manager = new_test_user(self.env, 'v111_proyectos', name='Jefe de proyectos (test)',
                                groups='project.group_project_manager')
        new = self.env['project.project'].with_user(manager).create(
            {'name': 'Obra nueva (test v111)'})
        new.is_construction_site = True
        self.assertTrue(new.sudo().construction_hr_site_ids)
