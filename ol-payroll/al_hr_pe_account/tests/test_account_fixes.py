# -*- coding: utf-8 -*-
"""Correcciones de la auditoría 2026-09 en los asientos de planilla.

* Cuentas ``company_dependent`` de los Parámetros Principales leídas y
  escritas con la compañía del registro, no con la activa.
* Tope al «ajuste por redondeo»: un descuadre real no se esconde.
* Solo boletas validadas o pagadas entran al asiento del lote.
* El asistente de BBSS recalcula las líneas al generar.
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.al_hr_pe_account.tests.test_fase5_account import \
    AccountCaseBase


@tagged('post_install', '-at_install')
class TestAccountFixes(AccountCaseBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_company = cls.env['res.company'].create({
            'name': 'Otra compañía activa SAC',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.env.user.company_ids |= cls.other_company
        # Sesión con la OTRA compañía activa pero acceso a la del caso.
        cls.env_other = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.other_company.id, cls.company.id]))

    # ------------------------------------------------------------------
    # Cuentas company_dependent
    # ------------------------------------------------------------------
    def test_accounts_read_with_record_company(self):
        """Con otra compañía activa se leen las cuentas de la del lote."""
        param = self.env_other['hr.main.parameter'].get_main_parameter(
            self.company)
        self.assertEqual(param.cts_debe_account_id, self.acc_cts_debe)
        self.assertEqual(param.benefits_adjust_account_id, self.acc_ajuste)

    def test_accounts_written_with_record_company(self):
        """Guardar los parámetros de B con A activa escribe en B."""
        param = self.env_other['hr.main.parameter'].browse(self.param.id)
        param.write({'cts_debe_account_id': self.acc_vaca_debe.id})
        self.assertEqual(
            self.param.with_company(self.company).cts_debe_account_id,
            self.acc_vaca_debe)
        self.assertFalse(
            self.param.with_company(self.other_company).cts_debe_account_id,
            'la compañía activa no debe recibir la cuenta de otra')

    def test_web_read_uses_record_company(self):
        """El formulario muestra las cuentas de la compañía del registro."""
        param = self.env_other['hr.main.parameter'].browse(self.param.id)
        value = param.web_read({'cts_debe_account_id': {}})[0][
            'cts_debe_account_id']
        if isinstance(value, dict):
            value = value.get('id')
        self.assertEqual(value, self.acc_cts_debe.id)

    def test_batch_move_with_other_active_company(self):
        """El asiento del lote sale bien aunque la compañía activa sea otra."""
        batch = self.batch.with_env(self.env_other)
        move = batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)
        self.assertEqual(move.company_id, self.company)
        self.assertEqual(move.state, 'posted')

    # ------------------------------------------------------------------
    # Tope del ajuste por redondeo
    # ------------------------------------------------------------------
    def test_real_imbalance_is_not_adjusted(self):
        """Una regla sin cuenta de abono no se esconde en el ajuste."""
        self.rule_neto.with_company(self.company).account_credit = False
        with self.assertRaises(UserError):
            self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)
        self.assertFalse(self.batch.move_id)

    def test_rounding_tolerance(self):
        """Un céntimo por línea se admite; más, no."""
        Param = self.env['hr.main.parameter']
        self.assertTrue(Param.check_rounding_difference(0.03, 3))
        with self.assertRaises(UserError):
            Param.check_rounding_difference(0.04, 3)

    def test_benefits_wizard_rejects_real_imbalance(self):
        """El asistente de BBSS tampoco ajusta un descuadre real."""
        prov = self.env['hr.provisiones'].create({
            'company_id': self.company.id,
            'payslip_run_id': self.batch.id,
        })
        prov.actualizar()
        action = prov.get_move_wizard()
        ctx = action['context']
        self.assertNotIn('move_lines', ctx,
                         'las líneas no deben viajar por el cliente')
        wizard = self.env['hr.benefits.move.wizard'].with_context(
            **ctx).create({'account_id': self.acc_ajuste.id})
        unbalanced = [
            {'account_id': self.acc_cts_debe.id, 'name': 'Gasto',
             'debit': 100.0, 'credit': 0.0, 'partner_id': False,
             'analytic_distribution': False},
            {'account_id': self.acc_cts_haber.id, 'name': 'Pasivo',
             'debit': 0.0, 'credit': 60.0, 'partner_id': False,
             'analytic_distribution': False},
        ]
        with patch.object(type(prov), '_get_move_lines',
                          return_value=unbalanced), \
                self.assertRaises(UserError):
            wizard.generate_move()
        self.assertFalse(prov.account_move_id)

    def test_benefits_wizard_recomputes_lines(self):
        """Al generar se usan las líneas actuales del registro."""
        prov = self.env['hr.provisiones'].create({
            'company_id': self.company.id,
            'payslip_run_id': self.batch.id,
        })
        prov.actualizar()
        ctx = prov.get_move_wizard()['context']
        wizard = self.env['hr.benefits.move.wizard'].with_context(
            **ctx).create({})
        self.assertEqual(wizard.company_id, self.company)
        expected = sum(line['debit'] for line in prov._get_move_lines())
        wizard.generate_move()
        self.assertAlmostEqual(
            sum(prov.account_move_id.line_ids.mapped('debit')),
            expected, places=2)

    # ------------------------------------------------------------------
    # Estados de las boletas del lote
    # ------------------------------------------------------------------
    def test_draft_payslips_block_the_batch_move(self):
        """Con boletas en borrador el asiento del lote no se genera."""
        slip = self.batch.slip_ids[:1]
        slip.write({'state': 'draft'})
        with self.assertRaises(UserError):
            self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)

    def test_cancelled_payslips_are_left_out(self):
        """Las anuladas no entran; solo las validadas o pagadas."""
        slips = self.batch.slip_ids
        self.assertTrue(slips)
        slips[:1].write({'state': 'cancel'})
        self.assertNotIn(slips[:1], self.batch._pe_get_batch_slips())
        self.assertTrue(all(
            slip.state in ('validated', 'paid')
            for slip in self.batch._pe_get_batch_slips()))
