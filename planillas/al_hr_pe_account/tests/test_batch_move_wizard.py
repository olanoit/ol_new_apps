# -*- coding: utf-8 -*-
"""Asistente del asiento de planilla por lote.

La previsualización del asistente y el asiento definitivo salen del mismo
``_pe_prepare_batch_move_lines``: lo que el usuario ve antes de aceptar
tiene que ser lo que se contabiliza. Aquí se comprueba esa equivalencia,
los candados de regeneración y el enlace del asiento con las boletas del
lote (del que depende que anular una boleta revierta el asiento).
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.al_hr_pe_account.tests.test_fase5_account import AccountCaseBase


@tagged('post_install', '-at_install')
class TestBatchMoveWizard(AccountCaseBase):

    def _wizard(self, **vals):
        return self.env['hr.payslip.run.move.wizard'].create(
            dict({'payslip_run_id': self.batch.id}, **vals))

    # ------------------------------------------------------------------
    # Apertura del asistente
    # ------------------------------------------------------------------
    def test_open_wizard_action(self):
        """El botón del lote abre el asistente con el lote precargado."""
        action = self.batch.action_pe_open_batch_move_wizard()
        self.assertEqual(action['res_model'], 'hr.payslip.run.move.wizard')
        self.assertEqual(action['context']['default_payslip_run_id'],
                         self.batch.id)

    def test_open_wizard_blocked_when_move_exists(self):
        """Con asiento ya generado el asistente no se abre."""
        self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)
        with self.assertRaises(UserError):
            self.batch.action_pe_open_batch_move_wizard()

    def test_open_wizard_rejects_multiple_batches(self):
        """El proceso es de un lote a la vez."""
        other = self.batch.copy()
        with self.assertRaises(UserError):
            (self.batch | other).action_pe_open_batch_move_wizard()

    # ------------------------------------------------------------------
    # Previsualización
    # ------------------------------------------------------------------
    def test_preview_is_balanced(self):
        """La previsualización cuadra: debe = haber, diferencia 0."""
        wizard = self._wizard()
        wizard._pe_refresh_lines()
        self.assertTrue(wizard.line_ids, 'el asistente debe listar líneas')
        self.assertAlmostEqual(wizard.debit, wizard.credit, places=2)
        self.assertAlmostEqual(wizard.difference, 0.0, places=2)

    def test_preview_matches_generated_move(self):
        """Lo previsualizado es exactamente lo que se contabiliza."""
        wizard = self._wizard()
        wizard._pe_refresh_lines()
        preview = sorted(
            (line.account_id.id, round(line.debit, 2), round(line.credit, 2))
            for line in wizard.line_ids)
        move = self.batch._pe_generate_batch_move(
            adjust_account=self.acc_ajuste)
        posted = sorted(
            (line.account_id.id, round(line.debit, 2), round(line.credit, 2))
            for line in move.line_ids)
        self.assertEqual(preview, posted)

    def test_preview_refreshes_on_batch_change(self):
        """Al elegir el lote, el onchange rellena la previsualización."""
        wizard = self.env['hr.payslip.run.move.wizard'].new(
            {'payslip_run_id': self.batch.id})
        wizard._onchange_payslip_run_id()
        self.assertTrue(wizard.line_ids)

    def test_analytic_flag_defaults_from_parameters(self):
        """El modo analítico se toma de los Parámetros Principales."""
        self.param.detail_analytic = True
        wizard = self.env['hr.payslip.run.move.wizard'].new(
            {'payslip_run_id': self.batch.id})
        wizard._onchange_payslip_run_id()
        self.assertTrue(wizard.with_analytic)
        self.param.detail_analytic = False

    def test_both_analytic_modes_are_balanced(self):
        """Con y sin analítica el asiento sigue cuadrando."""
        for flag in (False, True):
            lines = self.batch._pe_prepare_batch_move_lines(with_analytic=flag)
            debit = round(sum(line['debit'] for line in lines), 2)
            credit = round(sum(line['credit'] for line in lines), 2)
            self.assertAlmostEqual(debit, credit, places=2,
                                   msg='descuadre con analítica=%s' % flag)

    # ------------------------------------------------------------------
    # Generación desde el asistente
    # ------------------------------------------------------------------
    def test_generate_move_from_wizard(self):
        """Generar desde el asistente publica el asiento y lo abre."""
        wizard = self._wizard(account_id=self.acc_ajuste.id)
        wizard._pe_refresh_lines()
        action = wizard.generate_move()
        self.assertTrue(self.batch.move_id)
        self.assertEqual(self.batch.move_id.state, 'posted')
        self.assertEqual(action['res_model'], 'account.move')

    def test_move_is_linked_to_payslips(self):
        """El asiento se enlaza en las boletas y sincroniza su fecha."""
        move = self.batch._pe_generate_batch_move(
            adjust_account=self.acc_ajuste)
        slips = self.batch._pe_get_batch_slips()
        self.assertTrue(slips)
        self.assertEqual(slips.mapped('move_id'), move)
        self.assertEqual(set(slips.mapped('date')), {self.batch.date_end})

    def test_move_date_and_reference(self):
        """Fecha = fin del lote y referencia PLA + mes + año."""
        move = self.batch._pe_generate_batch_move(
            adjust_account=self.acc_ajuste)
        self.assertEqual(move.date, self.batch.date_end)
        self.assertEqual(move.ref, self.batch._pe_get_batch_move_ref())
        self.assertTrue(move.ref.startswith('PLA'))

    def test_lines_get_default_partner(self):
        """Las líneas sin partner propio toman el de los parámetros."""
        move = self.batch._pe_generate_batch_move(
            adjust_account=self.acc_ajuste)
        self.assertTrue(all(line.partner_id for line in move.line_ids),
                        'ninguna línea debe quedar sin partner')

    def test_regeneration_is_blocked(self):
        """No se puede generar dos veces el asiento del mismo lote."""
        self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)
        with self.assertRaises(UserError):
            self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)

    def test_missing_journal_is_reported(self):
        """Sin diario en los parámetros el proceso avisa, no revienta."""
        self.param.move_journal_id = False
        with self.assertRaises(UserError):
            self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)
        self.param.move_journal_id = self.journal
