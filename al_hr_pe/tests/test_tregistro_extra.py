# -*- coding: utf-8 -*-
"""Estructuras complementarias del T-Registro: E17, E29 y E30."""
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestTregistroExtra(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Extra T-Registro S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.dni = cls.env.ref('l10n_pe.it_DNI')
        cls.location = cls.env['hr.work.location'].create({
            'name': 'Agencia Santa Anita',
            'company_id': cls.company.id,
            'location_type': 'office',
            'address_id': cls.company.partner_id.id,
            'l10n_pe_establishment_code': '0001',
        })
        cls.location2 = cls.env['hr.work.location'].create({
            'name': 'Agencia San Luis',
            'company_id': cls.company.id,
            'location_type': 'office',
            'address_id': cls.company.partner_id.id,
            'l10n_pe_establishment_code': '0018',
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Ruiz Gómez Raúl',
            'last_name': 'Ruiz', 'm_last_name': 'Gómez', 'names': 'Raúl',
            'company_id': cls.company.id,
            'identification_id': '12345678',
            'l10n_latam_identification_type_id': cls.dni.id,
            'birthday': date(1990, 11, 11),
            'sex': 'male',
            'work_location_id': cls.location.id,
        })
        cls.institution = cls.env['l10n_pe.hr.education.institution'].search(
            [], limit=1)
        cls.career = cls.env['l10n_pe.hr.education.career'].search(
            [('institution_id', '=', cls.institution.id)], limit=1)
        cls.level_13 = cls.env.ref('al_hr_pe.education_level_13')
        cls.level_11 = cls.env.ref('al_hr_pe.education_level_11')
        cls.bcp = cls.env['res.bank'].create({
            'name': 'Banco de Crédito del Perú (test)',
            'l10n_pe_financial_entity_id': cls.env.ref(
                'al_hr_pe.fin_entity_002').id,
        })

    def _account(self, number, bank=None):
        return self.env['res.partner.bank'].create({
            'acc_number': number,
            'partner_id': self.employee.work_contact_id.id
            or self.employee.company_id.partner_id.id,
            'bank_id': (bank or self.bcp).id,
        })

    # ------------------------------------------------------------------
    # E17 — establecimientos
    # ------------------------------------------------------------------
    def test_e17_has_five_fields(self):
        rows = self.employee._l10n_pe_e17_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row), 5, 'la E17 tiene 5 columnas')
        self.assertEqual(row[0], '01')
        self.assertEqual(row[1], '12345678')
        self.assertEqual(row[2], '604')
        self.assertEqual(row[3], '20512528458', 'RUC del empleador')
        self.assertEqual(row[4], '0001', 'código de establecimiento')

    def test_e17_several_establishments(self):
        """Un trabajador puede estar en varios locales del mismo RUC."""
        self.employee.l10n_pe_extra_work_location_ids = self.location2
        rows = self.employee._l10n_pe_e17_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(row[4] for row in rows), ['0001', '0018'])

    def test_e17_ignores_repeated_location(self):
        """Si el extra es el mismo local, no se declara dos veces."""
        self.employee.l10n_pe_extra_work_location_ids = self.location
        self.assertEqual(len(self.employee._l10n_pe_e17_rows()), 1)

    def test_establishment_code_must_be_four_digits(self):
        with self.assertRaises(ValidationError):
            self.location.l10n_pe_establishment_code = '12'

    def test_location_without_code_is_skipped(self):
        self.location.l10n_pe_establishment_code = False
        self.assertFalse(self.employee._l10n_pe_e17_rows())

    # ------------------------------------------------------------------
    # E29 — estudios concluidos
    # ------------------------------------------------------------------
    def _study(self, **kwargs):
        vals = {
            'employee_id': self.employee.id,
            'education_level_id': self.level_13.id,
            'in_peru': True,
            'institution_id': self.institution.id,
            'career_id': self.career.id,
            'graduation_year': 2014,
        }
        vals.update(kwargs)
        return self.env['l10n_pe.hr.employee.education'].create(vals)

    def test_e29_has_eight_fields(self):
        self._study()
        rows = self.employee._l10n_pe_e29_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row), 8, 'la E29 tiene 8 columnas')
        self.assertEqual(row[3], '13', 'T09: universitaria completa')
        self.assertEqual(row[4], '1', 'estudió en el Perú')
        self.assertEqual(row[5], self.institution.code)
        self.assertEqual(row[6], self.career.code)
        self.assertEqual(row[7], '2014')

    def test_e29_outside_peru_leaves_the_rest_empty(self):
        """Con el indicador en 0, SUNAT exige los demás campos vacíos."""
        self._study(in_peru=False, institution_id=False, career_id=False,
                    graduation_year=0)
        row = self.employee._l10n_pe_e29_rows()[0]
        self.assertEqual(row[4], '0')
        self.assertEqual(row[5:], ['', '', ''])

    def test_e29_several_studies(self):
        self._study()
        self._study(education_level_id=self.level_11.id, graduation_year=2010)
        self.assertEqual(len(self.employee._l10n_pe_e29_rows()), 2)

    def test_e29_only_higher_education(self):
        with self.assertRaises(ValidationError):
            self._study(education_level_id=self.env.ref(
                'al_hr_pe.education_level_07').id)   # secundaria completa

    def test_e29_year_range(self):
        with self.assertRaises(ValidationError):
            self._study(graduation_year=1949)
        with self.assertRaises(ValidationError):
            self._study(graduation_year=date.today().year + 1)

    def test_e29_career_must_belong_to_institution(self):
        """La pareja cruzada la rechaza SUNAT: se corta antes."""
        other_career = self.env['l10n_pe.hr.education.career'].search(
            [('institution_id', '!=', self.institution.id)], limit=1)
        with self.assertRaises(ValidationError):
            self._study(career_id=other_career.id)

    def test_e29_onchange_clears_the_career(self):
        study = self._study()
        other_institution = self.env['l10n_pe.hr.education.institution'].search(
            [('id', '!=', self.institution.id)], limit=1)
        study.invalidate_recordset()
        form_values = study.new({
            'employee_id': self.employee.id,
            'education_level_id': self.level_13.id,
            'institution_id': other_institution.id,
            'career_id': self.career.id,
        })
        form_values._onchange_institution_id()
        self.assertFalse(form_values.career_id,
                         'al cambiar de institución se limpia la carrera')

    # ------------------------------------------------------------------
    # E30 — cuenta de abono
    # ------------------------------------------------------------------
    def test_e30_has_five_fields(self):
        self.employee.bank_account_ids = self._account('19100000123456')
        rows = self.employee._l10n_pe_e30_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row), 5, 'la E30 tiene 5 columnas')
        self.assertEqual(row[3], '002', 'T36: Banco de Crédito del Perú')
        self.assertEqual(row[4], '19100000123456')

    def test_e30_without_account(self):
        self.assertFalse(self.employee._l10n_pe_e30_rows())

    def test_account_length_by_bank(self):
        """El BCP admite 13, 14 o 20 dígitos, no 16."""
        self.employee.bank_account_ids = self._account('1910000012345678')
        issues = self.employee._l10n_pe_bank_account_issues()
        self.assertTrue(any('13 o 14 o 20' in issue for issue in issues),
                        issues)

    def test_account_cannot_be_a_repeated_digit(self):
        self.employee.bank_account_ids = self._account('11111111111111')
        issues = self.employee._l10n_pe_bank_account_issues()
        self.assertTrue(any('dígito repetido' in issue for issue in issues))

    def test_account_cannot_contain_the_document(self):
        self.employee.bank_account_ids = self._account('19112345678900')
        issues = self.employee._l10n_pe_bank_account_issues()
        self.assertTrue(
            any('documento de identidad' in issue for issue in issues))

    def test_cci_must_start_with_the_entity_code(self):
        self.employee.bank_account_ids = self._account('00212345678901234567')
        self.assertFalse(
            [i for i in self.employee._l10n_pe_bank_account_issues()
             if 'CCI' in i], 'el CCI que empieza por 002 es válido')
        self.employee.bank_account_ids = self._account('99912345678901234567')
        self.assertTrue(
            any('CCI' in issue
                for issue in self.employee._l10n_pe_bank_account_issues()))

    def test_bank_without_sunat_code(self):
        bank = self.env['res.bank'].create({'name': 'Banco sin código'})
        self.employee.bank_account_ids = self._account('19100000123456', bank)
        issues = self.employee._l10n_pe_bank_account_issues()
        self.assertTrue(any('tabla 36' in issue for issue in issues))

    # ------------------------------------------------------------------
    # Integración con el exportador
    # ------------------------------------------------------------------
    def _complete_worker(self):
        self.employee.version_id.write({
            'contract_date_start': date(2024, 1, 15),
            'wage': 3000.0,
            'l10n_pe_labor_regime_id': self.env.ref(
                'al_hr_pe.labor_regime_01').id,
            'l10n_pe_education_level_id': self.env.ref(
                'al_hr_pe.education_level_07').id,   # secundaria: sin E29
            'l10n_pe_occupation_id': self.env['l10n_pe.hr.occupation'].search(
                [('for_employee', '=', True)], limit=1).id,
            'l10n_pe_occupational_category_id': self.env.ref(
                'al_hr_pe.occ_category_03').id,
            'l10n_pe_contract_type_id': self.env.ref(
                'al_hr_pe.contract_type_01').id,
            'worker_type_id': self.env['hr.worker.type'].search([], limit=1).id,
            'situation_id': self.env['hr.situation'].search([], limit=1).id,
            'l10n_pe_payment_type': '1',             # efectivo: sin E30
        })

    def test_export_includes_est(self):
        self._complete_worker()
        files = self.employee._l10n_pe_tregistro_files('alta')
        self.assertIn('RP_20512528458.est', files)
        self.assertNotIn('RP_20512528458.edu', files,
                         'sin estudios concluidos no se envía la E29')
        self.assertNotIn('RP_20512528458.cta', files,
                         'cobrando en efectivo no se envía la E30')

    def test_export_includes_edu_and_cta(self):
        self._complete_worker()
        self.employee.version_id.write({
            'l10n_pe_education_level_id': self.level_13.id,
            'l10n_pe_payment_type': '2',
        })
        self._study()
        self.employee.bank_account_ids = self._account('19100000123456')
        files = self.employee._l10n_pe_tregistro_files('alta')
        self.assertEqual(sorted(files), [
            'RP_20512528458.cta',
            'RP_20512528458.edu',
            'RP_20512528458.est',
            'RP_20512528458.ide',
            'RP_20512528458.per',
            'RP_20512528458.tra',
        ])
        for content in files.values():
            for line in content.splitlines():
                self.assertTrue(line.endswith('|'))

    def test_export_requires_establishment(self):
        self._complete_worker()
        self.employee.work_location_id = False
        with self.assertRaises(UserError) as error:
            self.employee._l10n_pe_tregistro_files('alta')
        self.assertIn('establecimiento', str(error.exception))

    def test_export_requires_studies_for_higher_education(self):
        self._complete_worker()
        self.employee.version_id.l10n_pe_education_level_id = self.level_13
        with self.assertRaises(UserError) as error:
            self.employee._l10n_pe_tregistro_files('alta')
        self.assertIn('estudios concluidos', str(error.exception))

    def test_export_checks_the_account_when_paid_by_deposit(self):
        self._complete_worker()
        self.employee.version_id.l10n_pe_payment_type = '2'
        with self.assertRaises(UserError) as error:
            self.employee._l10n_pe_tregistro_files('alta')
        self.assertIn('cuenta de abono', str(error.exception))

    def test_baja_does_not_send_the_extra_files(self):
        self._complete_worker()
        self.employee.version_id.write({
            'contract_date_end': date(2026, 7, 31),
            'situation_reason_id': self.env['hr.reasons.leave'].search(
                [], limit=1).id,
        })
        files = self.employee._l10n_pe_tregistro_files('baja')
        self.assertEqual(list(files), ['RP_20512528458.per'])
