# -*- coding: utf-8 -*-
"""Valorización de proyecto por porcentaje arbitrario (v1.8, M18-09) y avance
por sub etapa en la valorización impresa (M18-14).

Criterio: la partida propone el % de su regla y se valoriza a un % escrito a
mano, con motivo; la valorización y su factura lo muestran marcado como
manual, con quién y cuándo."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_income import PRICE, IncomeCommon


@tagged('post_install', '-at_install')
class TestValuationManual(IncomeCommon):

    def test_manual_pct_on_valuation_and_invoice(self):
        first = self._execute_until_week()
        second = self.env['construction.weekly.delivery']._prepare_deliveries(
            today=date(2026, 11, 5), projects=self.project)
        self._confirm(first | second)
        valuation = self._prepare_valuation(date(2026, 11, 11))
        line = valuation.line_ids
        rule = round(second.line_ids.progress_end * 100, 2)
        self.assertAlmostEqual(line.pct_rule, rule, places=2)
        target = rule + 8.0
        with self.assertRaises(UserError):
            line.with_user(self.projects_user).write({'pct_manual': target})
        line.with_user(self.projects_user).write({
            'pct_manual': target, 'manual_reason': 'Avance acordado en la reunión de obra'})
        self.assertTrue(line.is_manual)
        self.assertEqual(line.manual_user_id, self.projects_user)
        self.assertTrue(line.manual_date)
        expected = round(PRICE * target / 100.0, 2)
        self.assertAlmostEqual(line.amount_delivered, expected, places=2)
        self.assertAlmostEqual(line.amount_confirmed, expected, places=2)
        self.assertAlmostEqual(line.progress_cumulative * 100, target, places=2)
        valuation.with_user(self.projects_user).action_send()
        self._confirm_valuation(valuation)
        valuation.with_user(self.finance).action_create_invoice()
        invoice_line = valuation.invoice_id.invoice_line_ids.filtered('sale_line_ids')
        self.assertIn('manual', invoice_line.name)
        self.assertIn('Avance acordado en la reunión de obra', invoice_line.name)
        # Volver a la regla: se borra el porcentaje escrito (en borrador).
        with self.assertRaises(UserError):
            line.write({'pct_manual': 0.0})

    def test_printed_valuation_stage_rows(self):
        first = self._execute_until_week()
        self._confirm(first)
        valuation = self._prepare_valuation(date(2026, 11, 4))
        rows = valuation._construction_stage_progress()
        labels = [row['label'] for row in rows]
        self.assertTrue(labels)
        leaves = [row for row in rows if row['leaf']]
        self.assertAlmostEqual(sum(row['planned'] for row in leaves),
                               sum(valuation.project_id._construction_current_plan()
                                   .line_ids.filtered('stage').mapped('amount_planned')), places=2)
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_construction_planner_sale.report_construction_valuation', valuation.ids)[0]
        self.assertIn(labels[0], html.decode())
