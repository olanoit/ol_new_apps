# -*- coding: utf-8 -*-
"""Descarga de la plantilla Excel de los importadores.

Regresión: la plantilla debe poder obtenerse ANTES de tener el archivo
y la configuración del asistente. Cuando la descarga era un botón
``type="object"``, el cliente web guardaba el asistente primero y el
guardado fallaba por los campos obligatorios del paso "Configurar"
(``struct_id``, ``payslip_run_id``), dejando la plantilla inalcanzable.
"""
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

WIZARDS = [
    'al.import.hr.attendance.wizard',
    'al.import.hr.salary.rule.wizard',
    'al.import.payslip.input.wizard',
    'al.import.vacation.rest.wizard',
    'al.import.hr.advance.wizard',
    'al.import.hr.version.wizard',
]


@tagged('post_install', '-at_install')
class TestPlantillaImportacion(TransactionCase):

    def test_01_plantilla_sin_registro_guardado(self):
        """Todo asistente genera su plantilla sobre un registro en memoria."""
        for model in WIZARDS:
            with self.subTest(model=model):
                data, filename = self.env[model].new({})._build_xlsx_template()
                self.assertTrue(data.startswith(b'PK'),
                                'la plantilla debe ser un xlsx')
                self.assertTrue(filename.endswith('.xlsx'))

    def test_02_asistente_creable_sin_configuracion(self):
        """El paso 1 no puede exigir campos del paso 2."""
        for model in WIZARDS:
            with self.subTest(model=model):
                wizard = self.env[model].create({})
                self.assertEqual(wizard.state, 'upload')

    def test_03_validacion_al_importar(self):
        """Lo que se quitó de ``required`` se valida al ejecutar."""
        from odoo.exceptions import UserError

        wizard = self.env['al.import.hr.salary.rule.wizard'].create({})
        with self.assertRaises(UserError):
            wizard._validate_config()
        struct = self.env['hr.payroll.structure'].search([], limit=1)
        wizard.struct_id = struct
        self.assertTrue(wizard._validate_config())


@tagged('post_install', '-at_install')
class TestPlantillaHttp(HttpCase):

    def test_04_descarga_http(self):
        new_test_user(
            self.env, login='pe_plantilla',
            groups='base.group_user,hr_payroll.group_hr_payroll_manager')
        self.authenticate('pe_plantilla', 'pe_plantilla')
        res = self.url_open(
            '/al_hr_pe_import/template/al.import.hr.salary.rule.wizard')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content.startswith(b'PK'))
        self.assertIn('.xlsx', res.headers.get('Content-Disposition', ''))

    def test_05_modelo_inexistente(self):
        new_test_user(
            self.env, login='pe_plantilla2',
            groups='base.group_user,hr_payroll.group_hr_payroll_manager')
        self.authenticate('pe_plantilla2', 'pe_plantilla2')
        res = self.url_open('/al_hr_pe_import/template/res.partner')
        self.assertEqual(res.status_code, 404)
