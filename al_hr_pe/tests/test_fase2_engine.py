# -*- coding: utf-8 -*-
"""Fase 2: paridad de cálculo del motor de nómina PE.

Fixture de referencia (caso estándar): trabajador régimen general, mes
completo, sueldo 3 000, AFP con comisión sobre flujo, EsSalud 9 %. Las
expectativas se derivan de las TASAS de los datos maestros (no números
mágicos): si la SBS cambia la tasa en data, el test sigue validando la
FÓRMULA.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFase2Engine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE Motor SAC',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.param = cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id, 'rmv': 1130.0})
        cls.afp = cls.env['hr.membership'].search(
            [('is_afp', '=', True), ('company_id', '=', False)], limit=1)
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        cls.employee = cls.env['hr.employee'].create({
            'names': 'María', 'last_name': 'Quispe', 'm_last_name': 'Rojas',
            'company_id': cls.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': 3000.0,
            'structure_type_id': cls.structure.type_id.id,
        })
        cls.employee.version_id.write({
            'membership_id': cls.afp.id,
            'l10n_pe_commission_type': 'flow',
        })

    def _compute_slip(self):
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta PE test',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
        })
        slip.compute_sheet()
        return slip

    def _line(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def test_snapshot(self):
        slip = self._compute_slip()
        self.assertEqual(slip.rmv, 1130.0)
        self.assertAlmostEqual(slip.family_allowance, 113.0)
        self.assertEqual(slip.membership_id, self.afp)
        self.assertAlmostEqual(
            slip.l10n_pe_retirement_fund, self.afp.retirement_fund)
        self.assertAlmostEqual(
            slip.l10n_pe_commission, self.afp.fixed_commision)

    def test_worked_days_zero_lines(self):
        """Todos los códigos PE tienen línea (aunque cero): las fórmulas
        con worked_days['X'] nunca deben reventar."""
        slip = self._compute_slip()
        codes = set(slip.worked_days_line_ids.mapped('code'))
        for code in ('DLAB', 'FAL', 'TAR', 'DMED', 'DVAC', 'DOM'):
            self.assertIn(code, codes)

    def test_base_afp_essalud_net(self):
        slip = self._compute_slip()
        wage = 3000.0
        bas = self._line(slip, 'BAS')
        self.assertTrue(bas, 'Sin línea BAS')
        # Mes completo → básico = sueldo
        self.assertAlmostEqual(bas.total, wage, places=1)
        # Fondo AFP sobre el afecto (mes completo sin variables = wage)
        a_jub = self._line(slip, 'A_JUB')
        self.assertTrue(a_jub, 'Sin línea A_JUB')
        expected_fund = round(wage * self.afp.retirement_fund / 100, 2)
        self.assertAlmostEqual(abs(a_jub.total), expected_fund, places=1)
        # Comisión sobre flujo
        comfi = self._line(slip, 'COMFI')
        self.assertTrue(comfi, 'Sin línea COMFI')
        expected_com = round(wage * self.afp.fixed_commision / 100, 2)
        self.assertAlmostEqual(abs(comfi.total), expected_com, places=1)
        # EsSalud 9 % del afecto (aporte del empleador)
        essalud = self._line(slip, 'ESSALUD')
        self.assertTrue(essalud, 'Sin línea ESSALUD')
        self.assertAlmostEqual(
            abs(essalud.total), round(wage * 0.09, 2), places=1)
        # Totales PLAME por categoría
        self.assertGreater(slip.worker_contributions, 0)
        self.assertGreater(slip.employer_contributions, 0)
        # Neto = total ingresos − aportes trabajador − descuentos al neto
        neto = self._line(slip, 'NETO')
        if neto:
            ing = sum(slip.line_ids.filtered(
                lambda l: l.category_id == self.env.ref('al_hr_pe.ING')
            ).mapped('total'))
            self.assertAlmostEqual(
                neto.total,
                ing - slip.worker_contributions - slip.net_discounts,
                places=1)

    def test_plame_rem_export(self):
        slip = self._compute_slip()
        self.employee.write({
            'l10n_latam_identification_type_id':
                self.env.ref('l10n_pe.it_DNI').id,
            'identification_id': '44556677',
        })
        run = self.env['hr.payslip.run'].create({
            'name': 'Lote PE 2026-03',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
            'company_id': self.company.id,
        })
        slip.payslip_run_id = run
        action = run.export_plame()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'hr.payslip.run'), ('res_id', '=', run.id),
        ], order='id desc', limit=1)
        self.assertTrue(attachment)
        self.assertTrue(attachment.name.endswith('.rem'))
