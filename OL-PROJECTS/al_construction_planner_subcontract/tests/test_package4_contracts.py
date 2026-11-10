# -*- coding: utf-8 -*-
"""Paquete 4 de CREVAL: contratas. Datos ficticios.

* CR-34: «Intervenir» guarda la preliquidación aunque el navegador solo
  mande la línea de la orden y la marca.
* CR-33: la orden de contrata anulada libera la línea del plan.
* CR-36: del día de la intervención vale solo lo reportado antes de
  confirmarla.
"""
from datetime import date

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import SQL

from .test_contract_intervention import TestContractIntervention
from .test_contract_terms_creval import ContractTermsCommon


@tagged('post_install', '-at_install')
class TestPackage4Contracts(ContractTermsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contractor_b = cls.env['res.partner'].create({'name': 'Drywall Sur SAC (test)'})

    _first_valuation = TestContractIntervention._first_valuation

    def _browser_wizard(self, order, po_line):
        """El asistente como lo guarda el navegador: las columnas de solo
        lectura no viajan; la línea llega con la orden y la marca."""
        return self.env['construction.contract.intervention.wizard'].create({
            'purchase_order_id': order.id, 'date': date(2026, 11, 25),
            'reason': 'Abandono de la obra',
            'line_ids': [Command.clear(), Command.create({
                'purchase_line_id': po_line.id, 'intervene': True})],
        })

    def test_cr34_intervention_keeps_the_preliquidation(self):
        order = self._first_valuation()
        wall_po = order.order_line.filtered(lambda l: l.construction_task_id == self.partida)
        wizard = self._browser_wizard(order, wall_po)
        self.assertFalse(wizard.line_ids.qty_new)
        action = wizard.action_confirm()
        intervention = self.env['construction.contract.intervention'].browse(action['res_id'])
        line = intervention.line_ids
        self.assertEqual(line.qty_contracted, 2000.0)
        self.assertEqual(line.qty_validated, 1200.0)
        self.assertEqual(line.qty_valued, 1000.0)
        self.assertEqual(line.qty_new, 1200.0)
        self.assertEqual(line.qty_released, 800.0)
        self.assertAlmostEqual(intervention.amount_released, 800 * 38.20, places=2)
        # La orden baja a lo ejecutado, no a 0.
        self.assertEqual(wall_po.product_qty, 1200.0)

    def test_cr36_same_day_progress_after_the_intervention(self):
        order = self._first_valuation()
        # Avance del mismo día, reportado antes de confirmar: vale.
        before = self._report(self.partida, self.act_wall, 10.0, date(2026, 11, 25))
        self.assertEqual(before.state, 'validated')
        wall_po = order.order_line.filtered(lambda l: l.construction_task_id == self.partida)
        action = self._browser_wizard(order, wall_po).action_confirm()
        intervention = self.env['construction.contract.intervention'].browse(action['res_id'])
        # En la prueba todo ocurre en la misma transacción: la confirmación
        # se mueve un minuto atrás.
        self.env.cr.execute(SQL(
            "UPDATE construction_contract_intervention "
            "SET create_date = create_date - interval '1 minute' WHERE id = %s",
            intervention.id))
        intervention.invalidate_recordset(['create_date'])
        with self.assertRaisesRegex(ValidationError, intervention.name):
            self._report(self.partida, self.act_wall, 5.0, date(2026, 11, 25))

    def test_cr33_cancelled_order_frees_the_plan_line(self):
        _wizard, order = self._assign()
        plan_lines = self.plan.line_ids.filtered(lambda l: l.partner_id == self.contractor)
        self.assertTrue(plan_lines)
        order.button_cancel()
        self.assertEqual(order.state, 'cancel')
        self.assertFalse(plan_lines.filtered('partner_id'))
        # La partida vuelve a «Asignar contrata» con otra contrata.
        assign = self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.partida.ids,
        ).create({'stage': 'creval_tab', 'partner_id': self.contractor_b.id,
                  'condition_id': self.condition.id, 'date_start': date(2026, 11, 26)})
        self.assertTrue(assign.line_ids)
        assign.action_assign()
        self.assertEqual(
            plan_lines.filtered(lambda l: l.task_id == self.partida).partner_id,
            self.contractor_b)
