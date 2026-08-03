# -*- coding: utf-8 -*-
"""Periodicidad semanal y agrupación mensual para la PLAME.

Construcción civil paga por semana, pero la PLAME se declara por mes. La
pieza que lo une son los periodos semanales colgados de su mes, cortados
en el fin de mes para que ninguna semana cruce dos declaraciones.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConstructionWeekly(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Semanal Test S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.wd_dlab = cls.env.ref('al_hr_pe.wd_DLAB')
        cls.dni = cls.env.ref('l10n_pe.it_DNI')
        cls.env['hr.period.generator'].create({
            'year': 2026, 'company_id': cls.company.id,
            'generate_weekly': True,
        }).action_generate()
        cls.Period = cls.env['hr.period']

    def _month(self, code):
        return self.Period.search([('code', '=', code),
                                   ('company_id', '=', self.company.id)])

    def _worker(self, seq=1):
        employee = self.env['hr.employee'].create({
            'name': 'Obrero Semanal %d' % seq,
            'company_id': self.company.id,
            'identification_id': '4500000%d' % seq,
            'l10n_latam_identification_type_id': self.dni.id})
        employee.version_id.write({
            # Confirmar la boleta exige vínculo vigente en el periodo.
            'contract_date_start': date(2026, 1, 1),
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': self.env.ref(
                'al_hr_pe_construction.category_operario').id})
        return employee

    def _payslip(self, employee, date_from, date_to, days=6):
        payslip = self.env['hr.payslip'].create({
            'name': 'Semana %s' % date_from,
            'employee_id': employee.id, 'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date_from, 'date_to': date_to})
        payslip.worked_days_line_ids.unlink()
        payslip.worked_days_line_ids = [(0, 0, {
            'name': 'Días', 'work_entry_type_id': self.wd_dlab.id,
            'number_of_days': days, 'number_of_hours': days * 8,
            'amount': 0.0})]
        payslip.compute_sheet()
        return payslip

    # ------------------------------------------------------------------
    # Generación de semanas
    # ------------------------------------------------------------------
    def test_monthly_periods_still_exist(self):
        month = self._month('202603')
        self.assertEqual(month.period_type, 'monthly')
        self.assertEqual(month.date_start, date(2026, 3, 1))
        self.assertEqual(month.date_end, date(2026, 3, 31))
        self.assertFalse(month.parent_id)

    def test_weeks_hang_from_their_month(self):
        month = self._month('202603')
        self.assertTrue(month.child_ids)
        for week in month.child_ids:
            self.assertEqual(week.period_type, 'weekly')
            self.assertEqual(week.parent_id, month)

    def test_weeks_never_cross_the_month(self):
        """Cortadas en el fin de mes: una semana a caballo obligaría a
        prorratear al declarar la PLAME."""
        for code in ('202601', '202602', '202603', '202612'):
            month = self._month(code)
            with self.subTest(mes=code):
                for week in month.child_ids:
                    self.assertGreaterEqual(week.date_start, month.date_start)
                    self.assertLessEqual(week.date_end, month.date_end)

    def test_weeks_cover_the_month_exactly(self):
        """Sin huecos ni solapes: los días de las semanas suman el mes."""
        for code in ('202601', '202602', '202603', '202611'):
            month = self._month(code)
            with self.subTest(mes=code):
                weeks = month.child_ids.sorted('date_start')
                self.assertEqual(weeks[0].date_start, month.date_start)
                self.assertEqual(weeks[-1].date_end, month.date_end)
                self.assertEqual(sum(weeks.mapped('duration_days')),
                                 month.duration_days)
                for previous, following in zip(weeks, weeks[1:]):
                    self.assertEqual(
                        (following.date_start - previous.date_end).days, 1,
                        'ni hueco ni solape entre semanas')

    def test_full_weeks_end_on_sunday(self):
        """Las completas van de lunes a domingo."""
        month = self._month('202603')
        full = month.child_ids.filtered(lambda w: w.duration_days == 7)
        self.assertTrue(full)
        for week in full:
            self.assertEqual(week.date_start.weekday(), 0, 'empieza lunes')
            self.assertEqual(week.date_end.weekday(), 6, 'termina domingo')

    def test_generator_is_idempotent(self):
        before = self.Period.search_count(
            [('company_id', '=', self.company.id)])
        self.env['hr.period.generator'].create({
            'year': 2026, 'company_id': self.company.id,
            'generate_weekly': True}).action_generate()
        self.assertEqual(
            self.Period.search_count([('company_id', '=', self.company.id)]),
            before, 'volver a generar no duplica')

    def test_weekly_period_must_fit_in_its_month(self):
        with self.assertRaises(UserError):
            self.Period.create({
                'code': 'FUERA', 'name': 'Semana fuera de mes',
                'date_start': date(2026, 3, 25), 'date_end': date(2026, 4, 5),
                'period_type': 'weekly',
                'parent_id': self._month('202603').id,
                'company_id': self.company.id})

    # ------------------------------------------------------------------
    # La boleta cae en el periodo correcto
    # ------------------------------------------------------------------
    def test_weekly_payslip_lands_on_the_week(self):
        """El más ajustado: la semana, no el mes que también la contiene."""
        payslip = self._payslip(self._worker(),
                                date(2026, 3, 2), date(2026, 3, 8))
        self.assertEqual(payslip.periodo_id.period_type, 'weekly')
        self.assertEqual(payslip.periodo_id.date_start, date(2026, 3, 2))
        self.assertEqual(payslip.periodo_id.parent_id, self._month('202603'))

    def test_monthly_payslip_lands_on_the_month(self):
        """Una boleta de mes no cabe en ninguna semana."""
        payslip = self._payslip(self._worker(2),
                                date(2026, 3, 1), date(2026, 3, 31), days=26)
        self.assertEqual(payslip.periodo_id.period_type, 'monthly')
        self.assertEqual(payslip.periodo_id, self._month('202603'))

    # ------------------------------------------------------------------
    # Agrupación para la PLAME
    # ------------------------------------------------------------------
    def test_plame_period_is_the_month(self):
        month = self._month('202603')
        week = month.child_ids.sorted('date_start')[0]
        self.assertEqual(week._l10n_pe_plame_period(), month)
        self.assertEqual(month._l10n_pe_plame_period(), month,
                         'un mes se declara en sí mismo')

    def test_run_declares_in_the_month(self):
        month = self._month('202603')
        week = month.child_ids.sorted('date_start')[0]
        run = self.env['hr.payslip.run'].create({
            'name': 'Semana 1 marzo', 'company_id': self.company.id,
            'periodo_id': week.id})
        self.assertEqual(run.l10n_pe_plame_period_id, month)

    def test_plame_takes_every_week_of_the_month(self):
        """Declarar una semana suelta dejaría fuera el resto del mes."""
        worker = self._worker(3)
        month = self._month('202603')
        weeks = month.child_ids.sorted('date_start')
        payslips = self.env['hr.payslip']
        for week in weeks[:3]:
            payslip = self._payslip(worker, week.date_start, week.date_end,
                                    days=min(6, week.duration_days))
            payslip.action_payslip_done()
            payslips |= payslip

        run = self.env['hr.payslip.run'].create({
            'name': 'Semana 1', 'company_id': self.company.id,
            'periodo_id': weeks[0].id})
        run.slip_ids = payslips[0]
        self.assertEqual(len(run.slip_ids), 1)
        self.assertEqual(run._l10n_pe_plame_slips(), payslips,
                         'la PLAME toma las tres semanas confirmadas')

    def test_monthly_run_keeps_its_own_slips(self):
        """Un lote mensual no cambia de comportamiento."""
        worker = self._worker(4)
        month = self._month('202604')
        payslip = self._payslip(worker, date(2026, 4, 1), date(2026, 4, 30),
                                days=26)
        run = self.env['hr.payslip.run'].create({
            'name': 'Abril', 'company_id': self.company.id,
            'periodo_id': month.id})
        run.slip_ids = payslip
        self.assertEqual(run.l10n_pe_plame_period_id, month)
        self.assertEqual(run._l10n_pe_plame_slips(), payslip)

    def test_month_shows_the_payslips_of_its_weeks(self):
        worker = self._worker(5)
        month = self._month('202605')
        week = month.child_ids.sorted('date_start')[1]
        self._payslip(worker, week.date_start, week.date_end)
        action = month.action_view_payslips()
        domain_periods = action['domain'][0][2]
        self.assertIn(week.id, domain_periods)
        self.assertIn(month.id, domain_periods)
