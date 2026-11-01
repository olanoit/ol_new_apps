# -*- coding: utf-8 -*-
"""Revisión numérica de subsidios (ronda 2, 01/11/2026): obreros de
construcción civil (D4).

Antes el histórico del subsidio solo leía boletas de la estructura BASE
(un obrero con un año de semanas salía con base 0 y subsidio 0) y la
estructura del régimen no tenía reglas SMAR/SENF: al importar, el
subsidio se marcaba pagado pero no llegaba a la boleta.
"""
from datetime import date, timedelta

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestRev2Construction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Subsidios Obras S.A.C.', 'vat': '20512528458',
            'country_id': cls.env.ref('base.pe').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.company.l10n_pe_construction_essalud_rate = 9.0
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.operario = cls.env.ref('al_hr_pe_construction.category_operario')
        cls.env['l10n_pe.hr.construction.wage.table'].create({
            'name': 'Convenio 2026 (subsidios)',
            'company_id': cls.company.id,
            'date_from': date(2025, 1, 1), 'date_to': date(2026, 12, 31),
            'line_ids': [Command.create({
                'category_id': cls.operario.id,
                'daily_wage': 90.0, 'mobility_amount': 8.0})],
        })
        for year in (2025, 2026):
            cls.env['hr.period.generator'].create({
                'year': year, 'company_id': cls.company.id,
            }).action_generate()

        def rule(xmlid):
            return cls.env.ref('al_hr_pe.salary_rule_%s' % xmlid)
        cls.param = cls.env['hr.main.parameter'].get_main_parameter(
            cls.company)
        cls.param.write({
            'basic_sr_id': rule('BAS').id,
            'vacation_sr_id': rule('VAC').id,
            'household_allowance_sr_id': rule('AF').id,
            'commission_sr_ids': [(6, 0, rule('COMI').ids)],
            'extra_hours_sr_id': rule('TOT_EXT').id,
            'otros_sr_ids': [(6, 0, rule('BONR').ids)],
            'lack_sr_ids': [(6, 0, rule('FAL').ids)],
            'maternidad_input_id': rule('SMAR').id,
            'enfermedad_input_id': rule('SENF').id,
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Operario subsidio',
            'company_id': cls.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
        })
        cls.employee.version_id.write({
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': cls.operario.id,
            'membership_id': cls.env.ref('al_hr_pe.membership_ONP').id,
        })
        # Siete semanas de enero y febrero de 2026, de lunes a domingo.
        # La del 26/01 al 01/02 termina en febrero: es de ese mes.
        cls.history = cls.env['hr.payslip']
        monday = date(2026, 1, 5)
        while monday < date(2026, 2, 23):
            slip = cls._payslip(monday, monday + timedelta(days=6),
                                {'DLAB': 6})
            slip.action_payslip_done()
            cls.history |= slip
            monday += timedelta(days=7)

    @classmethod
    def _payslip(cls, date_from, date_to, days):
        payslip = cls.env['hr.payslip'].create({
            'name': 'Semana %s' % date_from,
            'employee_id': cls.employee.id,
            'company_id': cls.company.id,
            'struct_id': cls.structure.id,
            'date_from': date_from, 'date_to': date_to,
        })
        payslip.worked_days_line_ids.unlink()
        payslip.worked_days_line_ids = [Command.create({
            'name': code, 'version_id': payslip.version_id.id,
            'work_entry_type_id': cls.env.ref('al_hr_pe.wd_%s' % code).id,
            'number_of_days': number, 'number_of_hours': number * 8,
            'amount': 0.0,
        }) for code, number in days.items()]
        payslip.compute_sheet()
        return payslip

    @staticmethod
    def _line(payslip, code):
        return round(sum(payslip.line_ids.filtered(
            lambda l: l.code == code).mapped('total')), 2)

    def _maternity(self):
        period = self.env['hr.period'].search([
            ('company_id', '=', self.company.id),
            ('period_type', '=', 'monthly'),
            ('code', '=', '202603')], limit=1)
        suspension = self.env['hr.work.suspension'].create({
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'periodo_id': period.id,
            'suspension_type_id': self.env.ref('al_hr_pe.suspension_22').id,
            'date_from': date(2026, 3, 2), 'date_to': date(2026, 3, 31),
            'days': 30, 'company_id': self.company.id,
        })
        lot = self.env['hr.subsidies.lot'].create({
            'company_id': self.company.id, 'periodo_id': period.id})
        lot.action_process()
        subsidy = lot.line_ids
        self.assertEqual(subsidy.suspension_id, suspension)
        subsidy.action_load_information()
        subsidy.action_compute()
        return subsidy

    def test_d4_historial_semanal_con_base_trem(self):
        """El histórico agrupa las semanas por el mes en que terminan y
        toma su TREM; el subsidio diario es la suma ÷ (30 × 2 meses)."""
        subsidy = self._maternity()
        by_month = {}
        for slip in self.history:
            month = '%04d%02d' % (slip.date_to.year, slip.date_to.month)
            by_month[month] = by_month.get(month, 0.0) \
                + self._line(slip, 'TREM')
        lines = subsidy.subsidies_line_ids
        self.assertEqual(sorted(lines.periodo_id.mapped('code')),
                         ['202601', '202602'])
        for line in lines:
            self.assertAlmostEqual(line.total, by_month[line.periodo_id.code],
                                   places=2)
        self.assertGreater(lines.filtered(
            lambda l: l.periodo_id.code == '202601').wage, 0.0,
            'jornal, dominical y BUC en la columna del básico')
        total = subsidy.subsidies_total_ids
        self.assertGreater(total.total_sub, 0.0)
        self.assertAlmostEqual(
            total.sub_dia, sum(by_month.values()) / 60, places=4)

    def test_d4_subsidio_llega_a_la_boleta_semanal(self):
        """«Importar subsidios» en la semana lleva el subsidio a la regla
        SMAR de la estructura del régimen (0915): suma a los ingresos y a
        la base de la ONP, no a la de EsSalud."""
        rules = self.structure.rule_ids
        self.assertEqual(
            sorted(rules.filtered(
                lambda r: r.code in ('SMAR', 'SENF')).mapped('sunat_code')),
            ['0915', '0916'])
        subsidy = self._maternity()
        amount = sum(subsidy.subsidies_periodo_ids.mapped('total_sub'))
        slip = self._payslip(date(2026, 3, 2), date(2026, 3, 8),
                             {'SMAR': 6})
        slip.import_subsidies()
        self.assertEqual(subsidy.subsidies_periodo_ids.mapped('validation'),
                         ['paid out'])
        slip.compute_sheet()
        self.assertAlmostEqual(self._line(slip, 'SMAR'), round(amount, 2),
                               places=2)
        self.assertEqual(self._line(slip, 'TREM'), 0.0)
        self.assertEqual(self._line(slip, 'ESSALUD'), 0.0,
                         'el subsidio es inafecto a EsSalud')
        self.assertAlmostEqual(
            self._line(slip, 'ONP'),
            -round(amount * slip.l10n_pe_retirement_fund / 100, 2),
            places=2)
        self.assertGreaterEqual(self._line(slip, 'TINGR'), round(amount, 2))
