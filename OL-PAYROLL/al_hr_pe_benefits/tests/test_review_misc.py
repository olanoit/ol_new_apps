# -*- coding: utf-8 -*-
"""Revisión Odoo 20 (estados, utilidades, adelantos, ingreso y
migración).

Mismo caso de referencia que la Fase 3 (sueldo 3 000, régimen general,
boletas Nov-2025 → Jun-2026 validadas en lotes mensuales). Cada test fija
el defecto que corrige.
"""
import importlib.util
from datetime import date
from pathlib import Path

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestReviewMisc(BenefitsCaseBase):

    def _slip(self, year, month):
        return self.runs[(year, month)].slip_ids.filtered(
            lambda slip: slip.employee_id == self.employee)

    def _utilities(self):
        self.param.write({
            'rule_total_income': self.param.basic_sr_id.id,
            'wd_dtrab': [(6, 0, self.env['hr.work.entry.type'].search(
                [('code', 'in', ('DLAB', 'DOM'))]).ids)],
            'wd_falt': [(6, 0, self.env['hr.work.entry.type'].search(
                [('code', '=', 'FAL')]).ids)],
            'hr_input_for_results': self.env['hr.salary.rule'].search(
                [('input_usage_payslip', '=', True)], limit=1).id,
        })
        return self.env['hr.utilities'].create({
            'company_id': self.company.id, 'year': 2026,
            'annual_rent': 100000.0, 'percentage': 10.0,
            'payslip_run_id': self.batch_jun.id,
        })

    # ------------------------------------------------------------------
    # S1: reprocesar registros cerrados por RPC
    # ------------------------------------------------------------------
    def test_registros_cerrados_no_se_reprocesan(self):
        provision = self.env['hr.provisiones'].create({
            'company_id': self.company.id,
            'payslip_run_id': self.batch.id})
        provision.action_process()
        provision.action_close()
        with self.assertRaises(UserError):
            provision.action_process()

        periodo = self.env['hr.period'].search([
            ('code', '=', '202603'), ('company_id', '=', self.company.id)],
            limit=1)
        lot = self.env['hr.subsidies.lot'].create({
            'company_id': self.company.id, 'periodo_id': periodo.id})
        lot.action_close()
        with self.assertRaises(UserError):
            lot.action_process()

        util = self._utilities()
        util.state = 'exported'
        for method in ('action_process', 'action_recompute',
                       'action_export_to_payslips'):
            with self.assertRaises(UserError):
                getattr(util, method)()

        fortnight = self.env['hr.fortnightly'].create({
            'name': 'Quincena junio', 'company_id': self.company.id,
            'date_start': date(2026, 6, 1), 'date_end': date(2026, 6, 15),
            'payslip_run_id': self.batch_jun.id})
        fortnight.state = 'verify'
        with self.assertRaises(UserError):
            fortnight.action_generate_payslips()

    # ------------------------------------------------------------------
    # C1: exportación a boletas cerradas
    # ------------------------------------------------------------------
    def test_gratificacion_no_exporta_a_boleta_validada(self):
        grati = self.env['hr.gratification'].create({
            'company_id': self.company.id, 'year': 2026, 'type': '07',
            'payslip_run_id': self.batch_jun.id,
            'deposit_date': date(2026, 7, 15)})
        grati.action_process()
        with self.assertRaises(UserError):
            grati.action_export_to_payslips()

    # ------------------------------------------------------------------
    # B3: modalidades formativas sin utilidades
    # ------------------------------------------------------------------
    def test_utilidades_excluye_practicantes(self):
        self.employee.version_id.l10n_pe_labor_regime = 'practicante'
        util = self._utilities()
        util.action_process()
        self.assertFalse(util.utilities_line_ids)

    # ------------------------------------------------------------------
    # M4: adelantos de quincena y ordinarios
    # ------------------------------------------------------------------
    def _advance_types(self, same_input):
        Rule = self.env.ref('al_hr_pe.salary_rule_INDEM')
        input_a = Rule.copy({'name': 'Adelanto prueba', 'code': 'ADE_PA'})
        input_b = input_a if same_input else Rule.copy(
            {'name': 'Adelanto quincena prueba', 'code': 'ADE_PB'})
        Type = self.env['hr.advance.type']
        ordinary = Type.create({'name': 'Adelanto', 'input_id': input_a.id,
                                'company_id': self.company.id})
        quin = Type.create({'name': 'Quincena', 'input_id': input_b.id,
                            'company_id': self.company.id})
        self.param.write({
            'grat_advance_id': Type.create({
                'name': 'Adelanto de gratificación',
                'company_id': self.company.id}).id,
            'quin_advance_id': quin.id,
        })
        return ordinary, quin

    def _advance(self, advance_type, amount, day, paid=False):
        advance = self.env['hr.advance'].create({
            'company_id': self.company.id,
            'employee_id': self.employee.id,
            'advance_type_id': advance_type.id,
            'amount': amount,
            'discount_date': date(2026, 6, day),
        })
        if paid:
            advance.turn_paid_out()
        return advance

    def test_adelanto_quincena_no_se_descuenta_dos_veces(self):
        """El adelanto de quincena ya pagado lo descuenta la exportación
        de la quincena por su input: no se suma otra vez al input del
        adelanto ordinario."""
        ordinary, _quin = self._advance_types(same_input=False)
        self._advance(_quin, 40.0, 10, paid=True)
        self._advance(ordinary, 100.0, 20)
        slip = self._slip(2026, 6)
        slip.write({'state': 'draft'})
        slip.import_advances()
        line = slip.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == ordinary.input_id)
        self.assertAlmostEqual(line.amount, 100.0, places=2)

    def test_quincena_no_pisa_el_adelanto_ordinario(self):
        """Mismo input para ambos tipos: exportar la quincena después de
        importar los adelantos conserva el ordinario (ya marcado pagado)."""
        ordinary, quin = self._advance_types(same_input=True)
        self._advance(quin, 40.0, 10, paid=True)
        self._advance(ordinary, 100.0, 20)
        slip = self._slip(2026, 6)
        slip.write({'state': 'draft'})
        slip.import_advances()
        fortnight_slip = self.env['hr.payslip'].create({
            'name': 'Quincena', 'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 15)})
        self.param.write({
            'fortnightly_input_id': self.env.ref(
                'al_hr_pe.salary_rule_INDEM').copy(
                {'name': 'Quincena prueba', 'code': 'QUIN_P'}).id,
            'net_fortnightly_sr_id': self.param.basic_sr_id.id,
        })
        self.env['hr.fortnightly'].set_amounts(
            fortnight_slip, self.batch_jun, self.param)
        line = slip.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == quin.input_id)
        self.assertAlmostEqual(line.amount, 140.0, places=2)

    # ------------------------------------------------------------------
    # B1 / M6: ingreso del vínculo vigente
    # ------------------------------------------------------------------
    def test_ingreso_del_vinculo_vigente(self):
        """Reingreso tras un cese: el ingreso es el del contrato nuevo.
        Una renovación sin interrupción continúa el vínculo."""
        Param = self.env['hr.main.parameter']
        rehired = self.env['hr.employee'].create({
            'name': 'Reingresado', 'company_id': self.company.id,
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': date(2021, 6, 30), 'wage': 2000.0})
        rehired.create_version({
            'date_version': date(2023, 3, 1),
            'contract_date_start': date(2023, 3, 1),
            'contract_date_end': False})
        self.assertEqual(
            Param.get_first_version(rehired).contract_date_start,
            date(2023, 3, 1))
        self.assertEqual(
            Param.get_first_version(rehired, date(2021, 3, 31))
            .contract_date_start, date(2020, 1, 1))
        renewed = self.env['hr.employee'].create({
            'name': 'Renovado', 'company_id': self.company.id,
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': date(2020, 12, 31), 'wage': 2000.0})
        renewed.create_version({
            'date_version': date(2021, 1, 1),
            'contract_date_start': date(2021, 1, 1),
            'contract_date_end': False})
        self.assertEqual(
            Param.get_first_version(renewed).contract_date_start,
            date(2020, 1, 1))

    # ------------------------------------------------------------------
    # C3: migración 19.0.6 sin el catálogo l10n_pe_hr_uit
    # ------------------------------------------------------------------
    def test_migracion_tramos_sin_tabla_uit(self):
        cr = self.env.cr
        path = Path(__file__).parent.parent / 'migrations' \
            / '19.0.6.20260816' / 'post-migrate.py'
        spec = importlib.util.spec_from_file_location('mig_tramos', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Base migrada a Odoo 20 sin el catálogo (si una base vieja aún lo
        # tiene, se oculta dentro de la transacción de la prueba).
        with cr.savepoint(flush=False) as savepoint:
            cr.execute("SELECT to_regclass('l10n_pe_hr_uit')")
            if cr.fetchone()[0]:
                cr.execute('ALTER TABLE l10n_pe_hr_uit '
                           'RENAME TO l10n_pe_hr_uit_test_hidden')
            module.migrate(cr, '19.0.5')
            savepoint.rollback()
