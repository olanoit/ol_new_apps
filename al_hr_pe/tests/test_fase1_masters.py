# -*- coding: utf-8 -*-
"""Fase 1: tablas maestras, periodos, parámetros y multicompañía."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFase1Masters(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env['res.company'].create({'name': 'PE Alfa SAC'})
        cls.company_b = cls.env['res.company'].create({'name': 'PE Beta SAC'})
        cls.env.user.company_ids |= cls.company_a | cls.company_b

    def test_catalogs_loaded(self):
        """Los datos maestros PLAME quedaron cargados y globales."""
        for model, minimum in [('hr.worker.type', 40), ('hr.situation', 4),
                               ('hr.reasons.leave', 20),
                               ('hr.suspension.type', 25),
                               ('hr.membership', 7)]:
            records = self.env[model].search([])
            self.assertGreaterEqual(len(records), minimum, model)
            self.assertFalse(records.filtered('company_id'),
                             '%s: los datos base deben ser globales' % model)

    def test_identification_types_extended(self):
        dni = self.env.ref('l10n_pe.it_DNI')
        self.assertEqual(dni.l10n_pe_hr_sunat_code, '1')

    def test_catalog_global_or_own(self):
        """Una compañía ve los globales + su override, no los ajenos."""
        Worker = self.env['hr.worker.type']
        own = Worker.create({'code': 'X1', 'name': 'PROPIO ALFA',
                             'company_id': self.company_a.id})
        other = Worker.create({'code': 'X2', 'name': 'PROPIO BETA',
                               'company_id': self.company_b.id})
        visible = Worker.with_company(self.company_a).with_user(
            self.env.user).search([])
        # ir.rule no aplica a admin: probar con un usuario interno
        user = self.env['res.users'].create({
            'name': 'Empleado test', 'login': 'pe_test_user',
            'company_id': self.company_a.id,
            'company_ids': [(6, 0, self.company_a.ids)],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        visible = Worker.with_user(user).search([])
        self.assertIn(own, visible)
        self.assertNotIn(other, visible)

    def test_uit(self):
        self.assertEqual(self.env['l10n_pe.hr.uit'].get_uit(2026), 5350)
        with self.assertRaises(UserError):
            self.env['l10n_pe.hr.uit'].get_uit(1990)

    def test_period_generator_multicompany(self):
        gen = self.env['hr.period.generator'].create({
            'year': 2026, 'company_id': self.company_a.id})
        gen.action_generate()
        periods = self.env['hr.period'].search([
            ('company_id', '=', self.company_a.id), ('year', '=', 2026)])
        self.assertEqual(len(periods), 12)
        january = periods.filtered(lambda p: p.code == '202601')
        self.assertEqual(january.date_end, date(2026, 1, 31))
        self.assertEqual(january.name, 'Enero 2026')
        # Idempotente y aislado por compañía
        gen.action_generate()
        self.assertEqual(self.env['hr.period'].search_count([
            ('company_id', '=', self.company_a.id), ('year', '=', 2026)]), 12)
        self.assertFalse(self.env['hr.period'].search([
            ('company_id', '=', self.company_b.id)]))

    def test_main_parameter_unique_and_helpers(self):
        Param = self.env['hr.main.parameter']
        param = Param.create({'company_id': self.company_a.id, 'rmv': 1130})
        self.assertAlmostEqual(param.family_allowance, 113.0)
        from odoo.tools import mute_logger
        with self.assertRaises(Exception), \
                mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            Param.create({'company_id': self.company_a.id})
            self.env.flush_all()
        # get_main_parameter por compañía
        self.assertEqual(
            Param.get_main_parameter(self.company_a), param)
        with self.assertRaises(UserError):
            Param.get_main_parameter(self.company_b)

    def test_months_days_difference(self):
        """Casos de la convención de mes comercial (base de CTS/grati)."""
        Param = self.env['hr.main.parameter']
        # Semestre completo CTS: 1 nov - 30 abr = 6 meses
        days, months = Param.get_months_days_difference(
            date(2025, 11, 1), date(2026, 4, 30))
        self.assertEqual((days, months), (0, 6))
        # Ingreso a mitad de mes: 15 ene - 31 mar = 2 meses + 17 días
        days, months = Param.get_months_days_difference(
            date(2026, 1, 15), date(2026, 3, 31))
        self.assertEqual((days, months), (17, 2))
        # Normalización 30 días → 1 mes
        self.assertEqual(Param.get_months_of_30_days(31, 2), (1, 3))

    def test_number_to_letter(self):
        Param = self.env['hr.main.parameter']
        self.assertEqual(Param.number_to_letter(1130.50),
                         'UN MIL CIENTO TREINTA CON 50/100')
        self.assertEqual(Param.number_to_letter(0),
                         'CERO CON 00/100')
        self.assertEqual(Param.number_to_letter(2500),
                         'DOS MIL QUINIENTOS CON 00/100')

    def test_employee_plame_name(self):
        employee = self.env['hr.employee'].create({
            'names': 'Juan Carlos',
            'last_name': 'Pérez',
            'm_last_name': 'García',
            'company_id': self.company_a.id,
        })
        self.assertEqual(employee.name, 'Pérez García Juan Carlos')
        employee.write({'m_last_name': 'Gonzales'})
        self.assertEqual(employee.name, 'Pérez Gonzales Juan Carlos')
