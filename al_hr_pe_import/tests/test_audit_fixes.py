# -*- coding: utf-8 -*-
"""Regresiones de la auditoría del framework de importación.

* La compañía del asistente debe ser una de las permitidas del usuario.
* El importador de versiones toma el catálogo global o el de SU
  compañía (nunca el override de otra) y escribe sin sudo.
* Una salida vacía no borra la ya registrada.
* Límite de filas y marcado de importaciones sin avance.
"""
from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import SQL

from odoo.addons.al_hr_pe_import.models import import_payroll_mixin
from odoo.addons.al_hr_pe_import.models import import_payroll_progress
from .test_fase8_import import _xlsx


@tagged('post_install', '-at_install')
class TestImportAuditFixes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pen = cls.env.ref('base.PEN')
        pen.active = True
        Company = cls.env['res.company']
        cls.company = Company.create({
            'name': 'PE Auditoría SAC',
            'country_id': cls.env.ref('base.pe').id,
            'currency_id': pen.id,
        })
        cls.company_b = Company.create({
            'name': 'PE Auditoría Beta SAC',
            'country_id': cls.env.ref('base.pe').id,
            'currency_id': pen.id,
        })
        # Compañía a la que el usuario NO tiene acceso en este contexto.
        cls.company_out = Company.create({
            'name': 'PE Ajena SAC',
            'country_id': cls.env.ref('base.pe').id,
            'currency_id': pen.id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id, cls.company_b.id]))
        cls.env.user.company_ids |= cls.company | cls.company_b
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        structure = cls.env.ref('al_hr_pe.base_structure')
        cls.employee = cls.env['hr.employee'].with_company(
            cls.company).create({
                'names': 'Luz', 'last_name': 'Quispe',
                'm_last_name': 'Mamani',
                'company_id': cls.company.id,
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'wage': 2500.0,
                'structure_type_id': structure.type_id.id,
            })
        cls.employee.version_id.identification_id = '70123456'

    def _version_wizard(self, rows, company=None):
        wizard = self.env['al.import.hr.version.wizard'].create({
            'file_data': _xlsx({'VERSIONES': [
                ['NRO DOCUMENTO', 'RÉGIMEN', 'CUSPP', 'COMISIÓN',
                 'AFILIACIÓN']] + rows}),
            'file_name': 'versiones.xlsx',
            'company_id': (company or self.company).id,
        })
        wizard.action_load_file()
        return wizard

    @staticmethod
    def _run(wizard):
        rows = wizard._preprocess_rows(wizard._iter_data_rows())
        return wizard._process_all_rows(rows)

    # ------------------------------------------------------------------
    # Compañía del asistente
    # ------------------------------------------------------------------
    def test_company_outside_allowed_is_rejected(self):
        wizard = self._version_wizard(
            [['70123456', 'general', '', '', '']], company=self.company_out)
        with self.assertRaises(UserError):
            self._run(wizard)
        with self.assertRaises(UserError):
            wizard.action_run_import()

    # ------------------------------------------------------------------
    # Catálogos global-or-own
    # ------------------------------------------------------------------
    def test_membership_never_from_other_company(self):
        Membership = self.env['hr.membership']
        global_afp = Membership.create({
            'name': 'AFP AUDITORIA', 'is_afp': True})
        Membership.create({
            'name': 'AFP AUDITORIA', 'is_afp': True,
            'company_id': self.company_b.id})
        _res, counts, _log, _ids = self._run(self._version_wizard(
            [['70123456', '', '', '', 'AFP AUDITORIA']]))
        self.assertEqual(counts['updated'], 1)
        self.assertEqual(self.employee.version_id.membership_id, global_afp)

        # Con override propio de la compañía, gana el propio.
        own_afp = Membership.create({
            'name': 'AFP AUDITORIA', 'is_afp': True,
            'company_id': self.company.id})
        self._run(self._version_wizard(
            [['70123456', '', '', '', 'AFP AUDITORIA']]))
        self.assertEqual(self.employee.version_id.membership_id, own_afp)

    def test_version_import_writes_without_sudo(self):
        """El empleado se busca sin sudo: la escritura respeta reglas."""
        # Un usuario de nómina real (no el superusuario de los tests): con
        # el sudo anterior, el empleado encontrado volvía con env.su=True.
        payroll_user = self.env['res.users'].create({
            'name': 'Nómina auditoría', 'login': 'al_hr_pe_import_nomina',
            'company_id': self.company.id,
            'company_ids': [(6, 0, (self.company | self.company_b).ids)],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('hr_payroll.group_hr_payroll_manager').id])],
        })
        wizard = self._version_wizard(
            [['70123456', 'small', '', '', '']]).with_user(payroll_user)
        employee = wizard._find_employee_by_doc('70123456')
        self.assertEqual(employee, self.employee)
        self.assertFalse(employee.env.su)
        self._run(wizard)
        self.assertEqual(
            self.employee.version_id.l10n_pe_labor_regime, 'small')

    # ------------------------------------------------------------------
    # Asistencias: salida vacía
    # ------------------------------------------------------------------
    def test_empty_check_out_does_not_clear(self):
        def wizard(salida):
            wiz = self.env['al.import.hr.attendance.wizard'].create({
                'file_data': _xlsx({'ASISTENCIAS': [
                    ['EMPLEADO', 'ENTRADA', 'SALIDA'],
                    [self.employee.name, '2026-05-04 08:00:00', salida]]}),
                'file_name': 'asistencias.xlsx',
                'company_id': self.company.id,
                'tz': 'America/Lima',
            })
            wiz.action_load_file()
            return wiz
        _res, _c, _log, ids = self._run(wizard('2026-05-04 17:00:00'))
        attendance = self.env['hr.attendance'].browse(ids[0])
        self._run(wizard(''))
        self.assertEqual(attendance.check_out, datetime(2026, 5, 4, 22, 0))

    # ------------------------------------------------------------------
    # Límites y progreso atascado
    # ------------------------------------------------------------------
    def test_row_limit(self):
        wizard = self._version_wizard([
            ['70123456', 'general', '', '', ''],
            ['70123457', 'general', '', '', ''],
        ])
        with patch.object(import_payroll_mixin, 'MAX_ROWS', 1):
            with self.assertRaises(UserError):
                wizard._iter_data_rows()

    def test_stale_progress_is_marked_as_error(self):
        Progress = self.env['al.import.payroll.progress']
        progress = Progress.create({
            'wizard_model': 'al.import.hr.version.wizard',
            'wizard_id': 1,
            'status': 'running',
            'company_id': self.company.id,
        })
        fresh = progress.get_progress_data()
        self.assertEqual(fresh['status'], 'running')

        old = datetime.now() - timedelta(
            minutes=import_payroll_progress.STALE_MINUTES + 5)
        self.env.flush_all()
        self.env.cr.execute(SQL(
            'UPDATE al_import_payroll_progress SET write_date = %s '
            'WHERE id = %s', old, progress.id))
        progress.invalidate_recordset(['write_date'])
        data = progress.get_progress_data()
        self.assertEqual(data['status'], 'error')
        self.assertTrue(data['error_detail'])
