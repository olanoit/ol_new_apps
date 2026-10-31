# -*- coding: utf-8 -*-
"""Renta de 5ta categoría del obrero de construcción civil.

El obrero cobra por semana, en un lote por semana y con la estructura de
construcción: la quinta solo miraba las reglas de BASE y el lote de la
propia quinta, así que nunca se le retenía. UIT 2026: 5 500 (7 UIT =
38 500).

* Operario (jornal 89.30): unos 51 000 al año → retiene.
* Peón (jornal 62.80): unos 36 000 al año, debajo de 7 UIT → no retiene.
"""
from datetime import date

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

#: Semanas completas de marzo de 2026 (lunes a domingo).
MARCH_WEEKS = [(date(2026, 3, 2), date(2026, 3, 8)),
               (date(2026, 3, 9), date(2026, 3, 15)),
               (date(2026, 3, 16), date(2026, 3, 22)),
               (date(2026, 3, 23), date(2026, 3, 29))]


@tagged('post_install', '-at_install')
class TestConstructionFifth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Quinta Obras S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.wd_dlab = cls.env.ref('al_hr_pe.wd_DLAB')
        cls.dni = cls.env.ref('al_hr_pe.l10n_pe_hr_document_type_dni')
        # Quinta configurada como en una instalación real: reglas de BASE.
        cls.param = cls.env['hr.main.parameter'].get_main_parameter(
            cls.company)
        cls.param.write({
            'fifth_afect_sr_id': cls.env.ref('al_hr_pe.salary_rule_ROAQ').id,
            'fifth_extr_sr_id': cls.env.ref('al_hr_pe.salary_rule_REAQ').id,
            'proy_afect_sr_id': cls.env.ref('al_hr_pe.salary_rule_PIAQ').id,
            'fifth_category_input_id': cls.env.ref(
                'al_hr_pe.salary_rule_QUINTA').id,
        })
        cls.param.action_generate_brackets(year=2026)
        cls.operario = cls._worker(1, 'category_operario')
        cls.peon = cls._worker(2, 'category_peon')
        # Un lote por semana, como lo genera el periodo semanal.
        cls.runs = []
        cls.slips = {cls.operario: [], cls.peon: []}
        for date_from, date_to in MARCH_WEEKS:
            run = cls.env['hr.payslip.run'].create({
                'name': 'Semana %s' % date_from,
                'date_start': date_from, 'date_end': date_to,
                'structure_id': cls.structure.id,
                'company_id': cls.company.id})
            cls.runs.append(run)
            for employee in (cls.operario, cls.peon):
                cls.slips[employee].append(
                    cls._payslip(employee, run, date_from, date_to))

    @classmethod
    def _worker(cls, seq, category):
        employee = cls.env['hr.employee'].create({
            'name': 'Obrero Quinta %d' % seq,
            'company_id': cls.company.id,
            'identification_id': '4800000%d' % seq,
            'l10n_pe_document_type_id': cls.dni.id})
        employee.version_id.write({
            'contract_date_start': date(2026, 1, 1),
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': cls.env.ref(
                'al_hr_pe_construction.%s' % category).id,
        })
        return employee

    @classmethod
    def _payslip(cls, employee, run, date_from, date_to):
        payslip = cls.env['hr.payslip'].create({
            'name': 'Semana %s' % date_from,
            'employee_id': employee.id,
            'company_id': cls.company.id,
            'struct_id': cls.structure.id,
            'payslip_run_id': run.id,
            'date_from': date_from, 'date_to': date_to,
        })
        payslip.worked_days_line_ids.unlink()
        payslip.worked_days_line_ids = [Command.create({
            'name': 'Días laborados',
            'version_id': payslip.version_id.id,
            'work_entry_type_id': cls.wd_dlab.id,
            'number_of_days': 6, 'number_of_hours': 48,
            'amount': 0.0})]
        payslip.compute_sheet()
        return payslip

    @staticmethod
    def _line(payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return round(sum(line.mapped('total')), 2)

    def _fifth(self, run):
        fifth = self.env['hr.fifth.category'].create({
            'payslip_run_id': run.id, 'company_id': self.company.id})
        fifth.action_generate()
        return fifth

    # ------------------------------------------------------------------
    # Reglas de la estructura
    # ------------------------------------------------------------------
    def test_taxable_income_excludes_mobility_and_cts(self):
        """Renta del mes: todo lo que paga la boleta menos la movilidad
        (condición de trabajo) y la indemnización (CTS), inafectas."""
        slip = self.slips[self.operario][0]
        self.assertGreater(self._line(slip, 'GRAT'), 0.0)
        self.assertEqual(
            self._line(slip, 'ROAQ'),
            round(self._line(slip, 'TINGR') - self._line(slip, 'MOV')
                  - self._line(slip, 'INDEM'), 2))
        self.assertGreater(self._line(slip, 'PIAQ'), 0.0)
        self.assertEqual(self._line(slip, 'QUINTA'), 0.0,
                         'sin quinta exportada no se retiene')

    # ------------------------------------------------------------------
    # Quinta del mes con las cuatro semanas
    # ------------------------------------------------------------------
    def test_fifth_withholds_from_the_operario_only(self):
        """La quinta del primer lote semanal liquida el mes entero.

        El operario supera 7 UIT al año y retiene; el peón no. La renta
        del mes es la de las cuatro semanas y la retención va a la última
        boleta semanal del mes, aunque esté en otro lote.
        """
        fifth = self._fifth(self.runs[0])
        line = fifth.line_ids.filtered(
            lambda l: l.employee_id == self.operario)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.slip_id, self.slips[self.operario][-1],
                         'la retención va a la última semana del mes')
        self.assertAlmostEqual(
            line.monthly_rem,
            sum(self._line(slip, 'ROAQ')
                for slip in self.slips[self.operario]), places=2)
        self.assertEqual((line.grat_july, line.grat_december), (0.0, 0.0),
                         'la gratificación va en cada planilla: no se '
                         'proyecta aparte')
        self.assertGreater(line.contrac_proy_rem, 0.0)
        self.assertGreater(line.total_proy, 7 * 5500)
        self.assertGreater(line.monthly_ret, 0.0)

        self.assertNotIn(self.peon, fifth.line_ids.employee_id)
        excluded = fifth.line_excluidos_ids.filtered(
            lambda l: l.employee_id == self.peon)
        self.assertEqual(len(excluded), 1, 'el peón se liquida, sin retención')
        self.assertLess(excluded.total_proy, 7 * 5500)

    def test_export_discounts_in_the_last_week(self):
        last = self.slips[self.operario][-1]
        net_before = self._line(last, 'NETO')
        tdes_before = self._line(last, 'TDES')
        fifth = self._fifth(self.runs[-1])
        line = fifth.line_ids.filtered(
            lambda l: l.employee_id == self.operario)
        fifth.action_export_to_payslips()
        retention = round(line.monthly_ret, 2)
        self.assertGreater(retention, 0.0)
        self.assertEqual(self._line(last, 'QUINTA'), retention,
                         'lo retenido, en positivo como en BASE')
        self.assertEqual(self._line(last, 'TDES'),
                         round(tdes_before + retention, 2))
        self.assertEqual(self._line(last, 'NETO'),
                         round(net_before - retention, 2))
        for slip in self.slips[self.operario][:-1]:
            self.assertEqual(self._line(slip, 'QUINTA'), 0.0,
                             'las otras semanas no retienen')
        self.assertEqual(self._line(self.slips[self.peon][-1], 'QUINTA'),
                         0.0)

    def test_previous_weeks_count_as_past_months(self):
        """Las semanas cerradas de meses anteriores entran en la renta de
        los meses previos (y lo retenido en ellas, en las retenciones)."""
        run = self.env['hr.payslip.run'].create({
            'name': 'Semana febrero', 'company_id': self.company.id,
            'structure_id': self.structure.id,
            'date_start': date(2026, 2, 23), 'date_end': date(2026, 2, 28)})
        february = self._payslip(self.operario, run,
                                 date(2026, 2, 23), date(2026, 2, 28))
        february.action_payslip_done()
        self.assertGreater(self._line(february, 'ROAQ'), 0.0)
        fifth = self._fifth(self.runs[0])
        line = fifth.line_ids.filtered(
            lambda l: l.employee_id == self.operario)
        self.assertAlmostEqual(line.past_rem, self._line(february, 'ROAQ'),
                               places=2)

    # ------------------------------------------------------------------
    # Certificado de 5ta y PLAME con boletas de construcción
    # ------------------------------------------------------------------
    def _close_march(self, employee):
        for slip in self.slips[employee]:
            slip.action_payslip_done()

    def test_certificate_includes_construction_income(self):
        """El certificado sumaba solo las reglas configuradas (de BASE):
        la renta del obrero salía en 0."""
        self._close_march(self.operario)
        wizard = self.env['hr.fifth.certificate.wizard'].create({
            'year': 2026, 'company_id': self.company.id,
            'employee_ids': [Command.set(self.operario.ids)]})
        values = wizard._get_certificate_values(self.operario)
        self.assertAlmostEqual(
            values['rem_bruta'],
            sum(self._line(slip, 'ROAQ') for slip in self.slips[self.operario]),
            places=2)
        self.assertGreater(values['rem_bruta'], 0.0)

    def test_plame_rem_declares_contributions_positive(self):
        """Los aportes AFP de construcción se calculan en negativo; en el
        .rem van en positivo, como los de BASE."""
        self.operario.version_id.membership_id = self.env.ref(
            'al_hr_pe.membership_AFP_INTEGRA')
        for slip in self.slips[self.operario]:
            slip.compute_sheet()
        self.assertLess(self._line(self.slips[self.operario][0], 'A_JUB'), 0.0)
        self._close_march(self.operario)
        action = self.runs[0].action_export_plame_rem()
        attachment = self.env['ir.attachment'].browse(
            int(action['url'].split('/')[3].split('?')[0]))
        rows = [row.split('|') for row in
                attachment.raw.decode('utf-8').splitlines()
                if row.split('|')[1:2] == [self.operario.identification_id]]
        amounts = {row[2]: float(row[3]) for row in rows}
        self.assertIn('0608', amounts)
        self.assertGreater(amounts['0608'], 0.0)
        self.assertTrue(all(amount >= 0 for amount in amounts.values()),
                        amounts)
