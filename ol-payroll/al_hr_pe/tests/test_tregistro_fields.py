# -*- coding: utf-8 -*-
"""Campos de `hr.version` para el T-Registro (estructura 05).

Los códigos salen del Anexo 2 de la Planilla Electrónica, así que las
pruebas comprueban contra los valores oficiales, no contra inventos.
"""
from odoo.fields import Date
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestTregistroFields(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'T-Registro Test S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Huamán Ríos Luis', 'company_id': cls.company.id})
        cls.version = cls.employee.version_id
        # La versión inicial nace con `date_version` = hoy; una nueva
        # versión con esa misma fecha reescribiría aquélla en vez de
        # crearse, así que las pruebas fechan siempre a partir de mañana.
        cls.next_date = Date.add(Date.today(), days=1)

    # ------------------------------------------------------------------
    # Catálogos oficiales
    # ------------------------------------------------------------------
    def test_official_catalogs_are_loaded(self):
        """Las tablas del Anexo 2 llegan completas."""
        expected = {
            'l10n_pe.hr.education.level': 21,       # T09
            'l10n_pe.hr.contract.type': 26,         # T12
            'l10n_pe.hr.occupational.category': 11,  # T24
            'l10n_pe.hr.labor.regime': 27,          # T33
            'l10n_pe.hr.dependent.type': 5,         # T19
            'l10n_pe.hr.dependent.end.reason': 8,   # T20
            'l10n_pe.hr.dependent.proof': 11,       # T27
        }
        for model, count in expected.items():
            self.assertGreaterEqual(
                self.env[model].search_count([('company_id', '=', False)]),
                count, 'Faltan registros del catálogo %s' % model)
        self.assertGreater(
            self.env['l10n_pe.hr.occupation'].search_count([]), 4000,
            'La tabla 30 de ocupaciones debe traer ~4 600 códigos')

    def test_official_codes(self):
        """Códigos verificados contra el Anexo 2, no supuestos."""
        self.assertEqual(
            self.env.ref('al_hr_pe.dependent_type_05').name,
            'Hijo menor de edad', 'T19: el 05 es el hijo menor')
        self.assertEqual(
            self.env.ref('al_hr_pe.dependent_type_04').name, 'Gestante',
            'T19: el 04 es la gestante')
        self.assertEqual(
            self.env.ref('al_hr_pe.labor_regime_16').regime_kind, 'micro',
            'T33: el 16 es microempresa')
        self.assertEqual(
            self.env.ref('al_hr_pe.labor_regime_17').regime_kind, 'small',
            'T33: el 17 es pequeña empresa')
        self.assertEqual(
            self.env.ref('al_hr_pe.labor_regime_21').regime_kind,
            'construccion', 'T33: el 21 es construcción civil')
        self.assertEqual(
            self.env.ref('al_hr_pe.contract_type_01').code, '01',
            'T12: el 01 es a plazo indeterminado D.Leg. 728')

    def test_dependent_type_flags_are_exclusive(self):
        """Ningún vínculo puede ser hijo y cónyuge a la vez."""
        for dtype in self.env['l10n_pe.hr.dependent.type'].search([]):
            self.assertFalse(dtype.is_child and dtype.is_partner,
                             '%s no puede ser hijo y cónyuge' % dtype.name)

    # ------------------------------------------------------------------
    # Campos de la versión
    # ------------------------------------------------------------------
    def test_defaults(self):
        self.assertTrue(self.version.l10n_pe_max_working_day,
                        'por defecto sujeto a jornada máxima')
        self.assertTrue(self.version.l10n_pe_fifth_income)
        self.assertEqual(self.version.l10n_pe_pay_periodicity, '1',
                         'T13: mensual')
        self.assertEqual(self.version.l10n_pe_payment_type, '2',
                         'T16: depósito en cuenta')
        self.assertEqual(self.version.l10n_pe_special_situation, '0')
        self.assertEqual(self.version.l10n_pe_double_taxation, '0')

    def test_regime_syncs_calculation_family_on_write(self):
        """Elegir el régimen SUNAT ajusta la familia de cálculo.

        Tiene que funcionar en un ``write`` pelado, no solo en el
        formulario: si no, una importación masiva dejaría la CTS con el
        divisor de otro régimen.
        """
        self.assertEqual(self.version.l10n_pe_labor_regime, 'general')
        self.version.l10n_pe_labor_regime_id = self.env.ref(
            'al_hr_pe.labor_regime_17')          # pequeña empresa
        self.assertEqual(self.version.l10n_pe_labor_regime, 'small',
                         'los divisores de CTS deben seguir al régimen')
        self.version.l10n_pe_labor_regime_id = self.env.ref(
            'al_hr_pe.labor_regime_16')          # microempresa
        self.assertEqual(self.version.l10n_pe_labor_regime, 'micro')

    def test_regime_syncs_on_create(self):
        version = self.employee.create_version({
            'date_version': self.next_date,
            'l10n_pe_labor_regime_id': self.env.ref(
                'al_hr_pe.labor_regime_21').id,   # construcción civil
        })
        self.assertEqual(version.l10n_pe_labor_regime, 'construccion')

    def test_explicit_family_wins(self):
        """Si el llamador fija ambos campos, manda lo que pidió."""
        self.version.write({
            'l10n_pe_labor_regime_id': self.env.ref(
                'al_hr_pe.labor_regime_17').id,   # pequeña empresa
            'l10n_pe_labor_regime': 'general',
        })
        self.assertEqual(self.version.l10n_pe_labor_regime, 'general')

    def test_occupation_allowed_for_category(self):
        """La T30 marca qué ocupaciones admite cada categoría."""
        Occupation = self.env['l10n_pe.hr.occupation']
        category_worker = self.env.ref('al_hr_pe.occ_category_02')  # obrero
        category_exec = self.env.ref('al_hr_pe.occ_category_01')    # ejecutivo
        self.assertEqual(category_worker.occupation_field, 'worker')
        only_exec = Occupation.search(
            [('for_executive', '=', True), ('for_worker', '=', False)],
            limit=1)
        self.assertTrue(only_exec, 'debe haber ocupaciones solo de ejecutivo')
        self.assertTrue(only_exec._l10n_pe_allowed_for(category_exec))
        self.assertFalse(only_exec._l10n_pe_allowed_for(category_worker))

    def test_occupation_cleared_when_category_conflicts(self):
        Occupation = self.env['l10n_pe.hr.occupation']
        only_exec = Occupation.search(
            [('for_executive', '=', True), ('for_worker', '=', False)],
            limit=1)
        self.version.l10n_pe_occupation_id = only_exec
        self.version.l10n_pe_occupational_category_id = self.env.ref(
            'al_hr_pe.occ_category_02')          # obrero
        self.version._onchange_l10n_pe_occupational_category_id()
        self.assertFalse(self.version.l10n_pe_occupation_id,
                         'la ocupación incompatible se limpia')

    def test_public_category_does_not_restrict(self):
        """Las categorías del sector público no tienen columna en la T30."""
        occupation = self.env['l10n_pe.hr.occupation'].search([], limit=1)
        category_public = self.env.ref('al_hr_pe.occ_category_11')
        self.assertFalse(category_public.occupation_field)
        self.assertTrue(occupation._l10n_pe_allowed_for(category_public))

    def test_cas_vat_must_be_11_digits(self):
        with self.assertRaises(ValidationError):
            self.version.l10n_pe_cas_vat = '2051252845'
        self.version.l10n_pe_cas_vat = '20512528458'
        self.assertEqual(self.version.l10n_pe_cas_vat, '20512528458')

    def test_fields_are_versioned(self):
        """Los datos del T-Registro viven en la versión, así que un cambio
        de condición laboral no reescribe el histórico."""
        self.version.l10n_pe_contract_type_id = self.env.ref(
            'al_hr_pe.contract_type_02')          # a tiempo parcial
        new_version = self.employee.create_version({
            'date_version': self.next_date,
            'l10n_pe_contract_type_id': self.env.ref(
                'al_hr_pe.contract_type_01').id,  # a plazo indeterminado
        })
        self.assertEqual(self.version.l10n_pe_contract_type_id.code, '02',
                         'la versión anterior conserva su tipo de contrato')
        self.assertEqual(new_version.l10n_pe_contract_type_id.code, '01')
