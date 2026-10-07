# -*- coding: utf-8 -*-
"""Correcciones de la auditoría 2026-09 en los reportes de planilla.

* Confirmación de la boleta: el GET solo pregunta y el POST confirma
  (los escáneres de enlaces del correo no dan la boleta por recibida).
* Plantillas de contrato saneadas (sin XSS) sin perder placeholders.
* Campos propios en hr.version restringidos a nómina.
* Certificados emitidos por la compañía del trabajador.
"""
from datetime import date, datetime, timedelta

from odoo.tests import HttpCase, TransactionCase, tagged


class _PayslipCase:

    @classmethod
    def _setup_payslip(cls):
        cls.company = cls.env['res.company'].create({
            'name': 'PE Auditoría reportes SAC',
            'country_id': cls.env.ref('base.pe').id,
            'city': 'Arequipa',
        })
        cls.employee = cls.env['hr.employee'].create({
            'names': 'Rosa', 'last_name': 'Mamani', 'm_last_name': 'Cruz',
            'company_id': cls.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': 2500.0,
        })
        cls.slip = cls.env['hr.payslip'].create({
            'name': 'Boleta auditoría',
            'employee_id': cls.employee.id,
            'version_id': cls.employee.version_id.id,
            'company_id': cls.company.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })


@tagged('post_install', '-at_install')
class TestVoucherConfirmation(HttpCase, _PayslipCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_payslip()

    def setUp(self):
        super().setUp()
        # Visitante anónimo (el trabajador abre el enlace del correo), pero
        # con la base fijada en la sesión: el servidor de pruebas sirve
        # varias bases sin dbfilter y sin ella la ruta pública da 404.
        self.authenticate(None, None)

    def _path(self, token=None):
        return '/boleta/confirmar/%s/%s' % (
            self.slip.id, token or self.slip._get_voucher_confirm_token())

    def test_get_only_asks(self):
        """Abrir el enlace no confirma: muestra el botón."""
        response = self.url_open(self._path())
        self.assertEqual(response.status_code, 200)
        self.assertIn('Confirmar recepción', response.text)
        self.slip.invalidate_recordset(['is_verified'])
        self.assertFalse(self.slip.is_verified)

    def test_post_confirms(self):
        """El POST del formulario registra la confirmación."""
        response = self.url_open(self._path(), data={'confirm': '1'})
        self.assertEqual(response.status_code, 200)
        self.slip.invalidate_recordset(['is_verified', 'date_confirmation'])
        self.assertTrue(self.slip.is_verified)
        self.assertTrue(self.slip.date_confirmation)

    def test_bad_token_is_rejected(self):
        """Un token que no corresponde no confirma nada."""
        response = self.url_open(self._path('x' * 64), data={'confirm': '1'})
        self.assertEqual(response.status_code, 404)
        self.slip.invalidate_recordset(['is_verified'])
        self.assertFalse(self.slip.is_verified)


    def test_expired_link_is_rejected(self):
        """A los 90 días del envío el enlace caduca; reenviar lo renueva."""
        self.slip.date_send = datetime.now() - timedelta(days=91)
        response = self.url_open(self._path(), data={'confirm': '1'})
        self.assertEqual(response.status_code, 410)
        self.slip.invalidate_recordset(['is_verified'])
        self.assertFalse(self.slip.is_verified)
        self.slip.date_send = datetime.now()
        self.assertFalse(self.slip._is_voucher_link_expired())

@tagged('post_install', '-at_install')
class TestReportsAuditFixes(TransactionCase, _PayslipCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_payslip()

    def test_voucher_with_negative_net(self):
        """Un neto negativo no impide generar la boleta (07/10/2026)."""
        from unittest.mock import patch
        Slip = type(self.slip)
        Param = self.env['hr.main.parameter']
        if not Param.search([('company_id', '=', self.slip.company_id.id)]):
            Param.create({'company_id': self.slip.company_id.id})
        with patch.object(Slip, 'net_wage', -150.5, create=False):
            data = self.slip._get_voucher_report_data()
        self.assertIn('MENOS', data['neto_letras'])

    def test_contract_template_is_sanitized(self):
        """El cuerpo se sanea pero conserva placeholders y estilos."""
        template = self.env['l10n_pe.hr.contract.template'].create({
            'name': 'Plantilla saneada',
            'body': '<p style="text-align: center;">{{nombre_trabajador}}'
                    '</p><script>alert(1)</script>'
                    '<img src="x" onerror="alert(2)"/>',
        })
        body = str(template.body)
        self.assertIn('{{nombre_trabajador}}', body)
        self.assertIn('text-align', body)
        self.assertNotIn('<script', body)
        self.assertNotIn('onerror', body)

    def test_version_fields_are_payroll_only(self):
        """Los campos propios en hr.version no son públicos."""
        fields_ = self.env['hr.version']._fields
        for name in ('l10n_pe_contract_template_id',
                     'l10n_pe_trial_period_regime', 'trial_date_end'):
            self.assertTrue(fields_[name].groups, name)

    def test_contract_report_not_bound_to_print_menu(self):
        """El contrato se imprime desde su botón, que valida los datos."""
        report = self.env.ref('al_hr_pe_reports.action_report_contract')
        self.assertFalse(report.binding_model_id)

    def test_certificate_uses_employee_company(self):
        """El certificado lleva la compañía (membrete y firma) del
        trabajador, no la activa."""
        for model in ('hr.certificate.wizard', 'hr.letter.wizard'):
            values = self.env[model].with_context(
                default_employee_id=self.employee.id).default_get(
                    ['employee_id', 'company_id', 'city'])
            self.assertEqual(values['company_id'], self.company.id, model)
            self.assertEqual(values['city'], 'Arequipa', model)
