# -*- coding: utf-8 -*-
"""Boleta por jornal y aportes del empleador (EsSalud y SCTR)."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConstructionReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Boleta Obra S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.report = cls.env.ref(
            'al_hr_pe_construction.action_report_boleta_construccion')
        cls.wd_dlab = cls.env.ref('al_hr_pe.wd_DLAB')
        cls.dni = cls.env.ref('l10n_pe.it_DNI')
        # El QWeb de la boleta lee los Parámetros Principales (firma del
        # representante, categorías de conceptos).
        # El parámetro de neto apunta a la regla del régimen general: es
        # el caso real: solo admite una regla y la boleta de construcción
        # tiene la suya.
        cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id,
            'net_to_pay_sr_id': cls.env.ref(
                'al_hr_pe.salary_rule_NETO').id})
        cls.site = cls.env['l10n_pe.hr.construction.site'].create({
            'name': 'Edificio Torre Lima', 'code': 'TL01',
            'company_id': cls.company.id})

    def _worker(self, seq=1, **version_vals):
        employee = self.env['hr.employee'].create({
            'name': 'Obrero Boleta %d' % seq, 'company_id': self.company.id,
            'identification_id': '4800000%d' % seq,
            'l10n_latam_identification_type_id': self.dni.id})
        vals = {
            'contract_date_start': date(2026, 1, 1),
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': self.env.ref(
                'al_hr_pe_construction.category_operario').id,
            'l10n_pe_construction_site_id': self.site.id,
        }
        vals.update(version_vals)
        employee.version_id.write(vals)
        return employee

    def _payslip(self, employee, days=6):
        payslip = self.env['hr.payslip'].create({
            'name': 'Semana', 'employee_id': employee.id,
            'company_id': self.company.id, 'struct_id': self.structure.id,
            'date_from': date(2026, 3, 2), 'date_to': date(2026, 3, 8)})
        payslip.worked_days_line_ids.unlink()
        payslip.worked_days_line_ids = [(0, 0, {
            'name': 'Días', 'work_entry_type_id': self.wd_dlab.id,
            'number_of_days': days, 'number_of_hours': days * 8,
            'amount': 0.0})]
        payslip.compute_sheet()
        return payslip

    @staticmethod
    def _line(payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return round(line.total, 2) if line else 0.0

    # ------------------------------------------------------------------
    # La boleta del régimen
    # ------------------------------------------------------------------
    def test_structure_prints_its_own_variant(self):
        """El botón «Imprimir» nativo saca la boleta de construcción."""
        payslip = self._payslip(self._worker())
        self.assertEqual(self.structure.report_id, self.report)
        self.assertEqual(list(payslip._get_pdf_reports()), [self.report])

    def test_report_name_keeps_the_l10n_pe_marker(self):
        """`_get_pdf_reports` mira ese marcador para no pisar la elección."""
        self.assertIn('l10n_pe', self.report.report_name)

    def test_voucher_shows_the_daily_wage_not_a_salary(self):
        payslip = self._payslip(self._worker())
        html = self.env['ir.actions.report']._render_qweb_html(
            self.report.report_name, payslip.ids)[0].decode()
        self.assertIn('Jornal básico', html)
        self.assertNotIn('Remuneración básica', html,
                         'en este régimen no hay sueldo mensual')
        self.assertIn('89.30', html)

    def test_voucher_shows_category_and_site(self):
        payslip = self._payslip(self._worker())
        html = self.env['ir.actions.report']._render_qweb_html(
            self.report.report_name, payslip.ids)[0].decode()
        self.assertIn('Operario', html)
        self.assertIn('Edificio Torre Lima', html)

    def test_voucher_shows_the_bae_specialty(self):
        bae = self.env.ref('al_hr_pe_construction.bonus_bae_electromecanico')
        payslip = self._payslip(
            self._worker(2, l10n_pe_construction_bae_id=bae.id))
        html = self.env['ir.actions.report']._render_qweb_html(
            self.report.report_name, payslip.ids)[0].decode()
        self.assertIn('Electromecánico', html)

    def test_general_voucher_is_untouched(self):
        """La variante es `primary`: el original no cambia."""
        general = self.env.ref('al_hr_pe_reports.action_report_boleta_pago')
        self.assertNotEqual(general, self.report)
        template = self.env['ir.ui.view'].search(
            [('key', '=',
              'al_hr_pe_reports.report_l10n_pe_boleta_pago_page')], limit=1)
        self.assertIn('Remuneración básica', template.arch,
                      'la boleta del régimen general sigue con su sueldo')

    def test_report_renders_without_error(self):
        """En tests Odoo devuelve el HTML en vez de llamar a wkhtmltopdf,
        así que se comprueba que el render no revienta y trae contenido."""
        payslip = self._payslip(self._worker(3))
        content, dummy = self.env['ir.actions.report']._render_qweb_pdf(
            self.report.id, payslip.ids)
        self.assertTrue(content)
        self.assertIn(b'Jornal', content)

    # ------------------------------------------------------------------
    # Neto y sobretiempo: lo que la boleta tiene que cuadrar
    # ------------------------------------------------------------------
    def test_net_to_pay_is_income_minus_discounts(self):
        payslip = self._payslip(self._worker(11))
        self.assertEqual(self._line(payslip, 'TDES'), 12.50,
                         'el total de descuentos se publica en positivo')
        self.assertEqual(self._line(payslip, 'NETO'),
                         self._line(payslip, 'TINGR') - 12.50)

    def test_voucher_resolves_the_net_by_code(self):
        """El parámetro apunta a la regla del régimen general; la boleta
        de construcción la reconoce por su código."""
        payslip = self._payslip(self._worker(12))
        data = payslip._get_voucher_report_data()
        self.assertEqual(data['neto'], self._line(payslip, 'NETO'))
        self.assertNotEqual(data['neto'], 0.0)
        self.assertNotIn('CERO CON 00/100', data['neto_letras'])

    def test_voucher_counts_the_60_percent_overtime(self):
        """Las extras del régimen entran en «horas sobretiempo»."""
        employee = self._worker(13)
        payslip = self._payslip(employee)
        payslip.worked_days_line_ids = [(0, 0, {
            'name': 'Horas extras 60%',
            'work_entry_type_id': self.env.ref(
                'al_hr_pe_construction.wd_HE60').id,
            'number_of_days': 0, 'number_of_hours': 4, 'amount': 0.0})]
        payslip.compute_sheet()
        data = payslip._get_voucher_report_data()
        self.assertEqual(data['horas_sobretiempo'], '04:00')
        self.assertIn('60%', ' '.join(
            item['nombre'] for item in data['horas_extras']))

    # ------------------------------------------------------------------
    # Aportes del empleador
    # ------------------------------------------------------------------
    def test_essalud_over_the_taxable_base(self):
        payslip = self._payslip(self._worker(4))
        self.assertEqual(self._line(payslip, 'TREM'), 796.56)
        self.assertEqual(self._line(payslip, 'ESSALUD'), 71.69,
                         '9 % de 796.56')

    def test_sctr_only_for_the_covered_worker(self):
        self.company.write({'l10n_pe_sctr_health_rate': 1.55,
                            'l10n_pe_sctr_pension_rate': 1.23})
        plain = self._payslip(self._worker(5))
        self.assertEqual(self._line(plain, 'SCTRS'), 0.0)
        self.assertEqual(self._line(plain, 'SCTRP'), 0.0,
                         'sin cobertura marcada no se aporta')

        covered = self._payslip(self._worker(
            6, l10n_pe_sctr_health=True, l10n_pe_sctr_pension=True))
        self.assertEqual(self._line(covered, 'SCTRS'), 12.35,
                         '1.55 % de 796.56')
        self.assertEqual(self._line(covered, 'SCTRP'), 9.80,
                         '1.23 % de 796.56')

    def test_sctr_coverages_are_independent(self):
        self.company.write({'l10n_pe_sctr_health_rate': 1.55,
                            'l10n_pe_sctr_pension_rate': 1.23})
        payslip = self._payslip(self._worker(7, l10n_pe_sctr_health=True))
        self.assertGreater(self._line(payslip, 'SCTRS'), 0.0)
        self.assertEqual(self._line(payslip, 'SCTRP'), 0.0)

    def test_sctr_needs_a_rate(self):
        """Sin tasa contratada no se inventa un aporte."""
        payslip = self._payslip(self._worker(
            8, l10n_pe_sctr_health=True, l10n_pe_sctr_pension=True))
        self.assertEqual(self._line(payslip, 'SCTRS'), 0.0)
        self.assertEqual(self._line(payslip, 'SCTRP'), 0.0)

    def test_employer_contributions_are_not_paid_to_the_worker(self):
        """Van en su columna, no suman al ingreso del trabajador."""
        self.company.l10n_pe_sctr_health_rate = 1.55
        payslip = self._payslip(self._worker(9, l10n_pe_sctr_health=True))
        self.assertEqual(self._line(payslip, 'TINGR'), 1111.90,
                         'el total de ingresos no incluye los aportes')
        self.assertGreater(self._line(payslip, 'ESSALUD'), 0.0)

    def test_voucher_shows_the_employer_contributions(self):
        self.company.l10n_pe_sctr_health_rate = 1.55
        payslip = self._payslip(self._worker(10, l10n_pe_sctr_health=True))
        html = self.env['ir.actions.report']._render_qweb_html(
            self.report.report_name, payslip.ids)[0].decode()
        self.assertIn('EsSalud', html)
        self.assertIn('SCTR salud', html)
