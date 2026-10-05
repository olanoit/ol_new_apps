# -*- coding: utf-8 -*-
"""CONAFOVICER: retención semanal y liquidación mensual.

Los importes de la tabla oficial son el fixture: el operario retiene
12.50 a la semana, el oficial 9.77 y el peón 8.79. Esos números son los
que demuestran cuál es la base.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConafovicer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Conafovicer Test S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.wd_dlab = cls.env.ref('al_hr_pe.wd_DLAB')
        cls.dni = cls.env.ref('l10n_pe.it_DNI')
        cls.env['hr.period.generator'].create({
            'year': 2026, 'company_id': cls.company.id,
            'generate_weekly': True}).action_generate()
        cls.month = cls.env['hr.period'].search(
            [('code', '=', '202603'), ('company_id', '=', cls.company.id)])
        cls.weeks = cls.month.child_ids.sorted('date_start')

    def _worker(self, seq=1, category='category_operario'):
        employee = self.env['hr.employee'].create({
            'name': 'Obrero CONAF %d' % seq, 'company_id': self.company.id,
            'identification_id': '4600000%d' % seq,
            'l10n_latam_identification_type_id': self.dni.id})
        employee.version_id.write({
            'contract_date_start': date(2026, 1, 1),
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': self.env.ref(
                'al_hr_pe_construction.%s' % category).id})
        return employee

    def _payslip(self, employee, week, days=6, confirm=False):
        payslip = self.env['hr.payslip'].create({
            'name': 'Semana %s' % week.code,
            'employee_id': employee.id, 'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': week.date_start, 'date_to': week.date_end})
        payslip.worked_days_line_ids.unlink()
        payslip.worked_days_line_ids = [(0, 0, {
            'name': 'Días', 'work_entry_type_id': self.wd_dlab.id,
            'number_of_days': days, 'number_of_hours': days * 8,
            'amount': 0.0})]
        payslip.compute_sheet()
        if confirm:
            payslip.action_payslip_done()
        return payslip

    @staticmethod
    def _line(payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return round(line.total, 2) if line else 0.0

    def _full_week(self):
        return self.weeks.filtered(lambda w: w.duration_days == 7)[0]

    # ------------------------------------------------------------------
    # La base: lo que demuestra la tabla oficial
    # ------------------------------------------------------------------
    def test_retention_matches_the_official_table(self):
        expected = {'category_operario': 12.50,
                    'category_oficial': 9.77,
                    'category_peon': 8.79}
        for index, (category, amount) in enumerate(expected.items(), start=1):
            with self.subTest(categoria=category):
                payslip = self._payslip(
                    self._worker(index, category), self._full_week())
                self.assertEqual(self._line(payslip, 'CONAF'), -amount,
                                 'se descuenta al trabajador')

    def test_base_includes_the_dso(self):
        """Sobre el jornal solo, el operario retendría 10.72, no 12.50."""
        payslip = self._payslip(self._worker(4), self._full_week())
        base = payslip._l10n_pe_construction_conafovicer_base()
        self.assertEqual(round(base, 2), 625.10, '535.80 + 89.30')
        self.assertEqual(
            round(payslip._l10n_pe_construction_amount('jornal') * 0.02, 2),
            10.72, 'el 2 % del jornal solo no llega a los 12.50 oficiales')

    def test_rate_is_a_parameter(self):
        self.company.l10n_pe_conafovicer_rate = 3.0
        payslip = self._payslip(self._worker(5), self._full_week())
        self.assertEqual(self._line(payslip, 'CONAF'), -18.75,
                         '3 % de 625.10')

    # ------------------------------------------------------------------
    # De paso: la base afecta a ONP que quedó por confirmar en la fase 3
    # ------------------------------------------------------------------
    def test_taxable_base_matches_the_official_onp_discount(self):
        """La tabla descuenta 103.55 de ONP al operario: 13 % de 796.56.

        Ese 796.56 es jornal + D.S.O. + BUC, o sea el `TREM` que calcula
        el módulo. Confirma dos cosas que estaban pendientes: **el BUC sí
        está afecto** y **la movilidad no**.
        """
        expected = {'category_operario': (796.56, 103.55),
                    'category_oficial': (613.80, 79.79),
                    'category_peon': (552.64, 71.84)}
        for index, (category, (base, onp)) in enumerate(expected.items(),
                                                        start=6):
            with self.subTest(categoria=category):
                payslip = self._payslip(
                    self._worker(index, category), self._full_week())
                self.assertEqual(self._line(payslip, 'TREM'), base)
                self.assertEqual(round(base * 0.13, 2), onp,
                                 'el 13 % de la base da el ONP oficial')
                self.assertNotIn(
                    self._line(payslip, 'MOV'), (0.0,),
                    'la movilidad se paga…')
                self.assertLess(base, self._line(payslip, 'JOR')
                                + self._line(payslip, 'DSO')
                                + self._line(payslip, 'BUC')
                                + self._line(payslip, 'MOV'),
                                '…pero queda fuera de la base afecta')

    # ------------------------------------------------------------------
    # Liquidación mensual
    # ------------------------------------------------------------------
    def _summary(self):
        return self.env['l10n_pe.hr.conafovicer'].create({
            'period_id': self.month.id, 'company_id': self.company.id})

    def test_summary_consolidates_every_week(self):
        worker = self._worker(10)
        full_weeks = self.weeks.filtered(lambda w: w.duration_days == 7)[:3]
        for week in full_weeks:
            self._payslip(worker, week, confirm=True)

        summary = self._summary()
        summary.action_compute()
        self.assertEqual(summary.state, 'computed')
        self.assertEqual(len(summary.line_ids), 3, 'una línea por semana')
        self.assertEqual(summary.employee_count, 1)
        self.assertEqual(round(summary.amount_total, 2), 37.50,
                         '12.50 × 3 semanas')
        self.assertEqual(round(summary.amount_base, 2), 1875.30)

    def test_summary_ignores_unconfirmed_payslips(self):
        worker = self._worker(11)
        self._payslip(worker, self._full_week(), confirm=False)
        summary = self._summary()
        summary.action_compute()
        self.assertFalse(summary.line_ids,
                         'solo entra lo confirmado o pagado')

    def test_summary_covers_several_workers(self):
        week = self._full_week()
        for index, category in enumerate(
                ('category_operario', 'category_oficial', 'category_peon'),
                start=12):
            self._payslip(self._worker(index, category), week, confirm=True)
        summary = self._summary()
        summary.action_compute()
        self.assertEqual(summary.employee_count, 3)
        self.assertEqual(round(summary.amount_total, 2),
                         round(12.50 + 9.77 + 8.79, 2))

    def test_due_date_is_the_15th_of_the_next_month(self):
        summary = self._summary()
        self.assertEqual(summary.date_due, date(2026, 4, 15))

    def test_one_summary_per_period(self):
        self._summary()
        with self.assertRaises(Exception):
            self._summary()
            self.env.flush_all()

    def test_recompute_replaces_the_detail(self):
        worker = self._worker(20)
        self._payslip(worker, self._full_week(), confirm=True)
        summary = self._summary()
        summary.action_compute()
        first = len(summary.line_ids)
        summary.action_compute()
        self.assertEqual(len(summary.line_ids), first, 'no se acumula')

    def test_paid_summary_is_locked(self):
        worker = self._worker(21)
        self._payslip(worker, self._full_week(), confirm=True)
        summary = self._summary()
        summary.action_compute()
        summary.action_mark_paid()
        with self.assertRaises(UserError):
            summary.action_compute()

    def test_cannot_pay_before_computing(self):
        summary = self._summary()
        with self.assertRaises(UserError):
            summary.action_mark_paid()

    def test_export_needs_lines(self):
        summary = self._summary()
        with self.assertRaises(UserError):
            summary.action_export_xlsx()

    def test_export_detail(self):
        import base64
        import io
        from openpyxl import load_workbook

        worker = self._worker(22)
        document = worker.identification_id
        self._payslip(worker, self._full_week(), confirm=True)
        summary = self._summary()
        summary.action_compute()
        action = summary.action_export_xlsx()
        self.assertEqual(action['type'], 'ir.actions.act_url')

        attachment = self.env['ir.attachment'].search(
            [('res_model', '=', summary._name), ('res_id', '=', summary.id)],
            limit=1)
        sheet = load_workbook(
            io.BytesIO(base64.b64decode(attachment.datas))).active
        rows = list(sheet.values)
        self.assertEqual(rows[0][:2], ('Empleador', self.company.name))
        self.assertEqual(rows[1][:2], ('RUC', '20512528458'))
        # Cabecera del detalle y la fila del trabajador
        header = [row for row in rows if row and row[0] == 'Tipo doc.'][0]
        self.assertIn('Base', header)
        detail = rows[rows.index(header) + 1]
        self.assertEqual(detail[1], document)
        self.assertEqual(round(detail[7], 2), 625.10)
        self.assertEqual(round(detail[8], 2), 12.50)
