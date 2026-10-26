# -*- coding: utf-8 -*-
"""Redondeo único entre la valorización y su factura (CREVAL, CR-11): con el
redondeo global de impuestos la factura sumaba cantidad × tarifa sin redondear
y salía un céntimo menos que la valorización. Datos ficticios."""
from datetime import date

from odoo.tests import tagged

from .test_contract_terms_creval import ContractTermsCommon
from .test_corrections_creval import TestCorrectionsCreval


@tagged('post_install', '-at_install')
class TestInvoiceRounding(ContractTermsCommon):

    _prepare = TestCorrectionsCreval._prepare

    def test_invoice_matches_valuation(self):
        self.company.tax_calculation_rounding_method = 'round_globally'
        self.env.ref('product.decimal_price').digits = 4
        wizard = self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True,
        ).create({'stage': 'creval_tab', 'partner_id': self.contractor.id,
                  'condition_id': self.condition.id, 'date_start': date(2026, 11, 2)})
        wizard.line_ids.filtered(lambda r: r.activity_id == self.act_wall).price_unit = 44.74
        wizard.line_ids.filtered(lambda r: r.activity_id == self.act_seal).price_unit = 7.4459
        wizard.action_assign()
        order = self.env['purchase.order'].search([
            ('partner_id', '=', self.contractor.id),
            ('construction_project_id', '=', self.project.id)], order='id desc', limit=1)
        order.button_confirm()
        action = order.action_construction_register_advance()
        self._post(self.env['account.move'].browse(action['res_id']), date(2026, 11, 2))
        # 22.78 × 44.74 = 1,019.1772 y 3 × 7.4459 = 22.3377: por línea 1,041.52;
        # sin redondear 1,041.5149, que Odoo redondea a 1,041.51.
        self._report(self.partida, self.act_wall, 22.78, date(2026, 11, 4))
        self._report(self.extra_task, self.act_seal, 3.0, date(2026, 11, 4))
        settlement = self._prepare()
        self.assertEqual(settlement.amount_direct, 1041.52)
        settlement.action_submit()
        settlement.action_validate()
        invoice = settlement.invoice_id
        self.assertEqual(settlement.amount_invoice_rounding, 0.01)
        rounding = invoice.invoice_line_ids.filtered(lambda l: 'redondeo' in (l.name or ''))
        self.assertEqual(rounding.price_subtotal, 0.01)
        services = invoice.invoice_line_ids.filtered('purchase_line_id')
        self.assertEqual(sum(services.mapped('price_subtotal')), settlement.amount_direct)
        self.assertAlmostEqual(invoice.amount_total,
                               settlement.amount_total - settlement.amount_advance, places=2)
        self.assertFalse(invoice.construction_valuation_difference)
        # Una corrección a mano que cambia el total se avisa en la factura.
        if invoice.state == 'posted':
            invoice.button_draft()
        rounding.unlink()
        self.assertTrue(invoice.construction_valuation_difference)

    def test_invoice_tax_matches_valuation(self):
        """La base cuadra al céntimo pero el IGV no (1.111 × 221.30 =
        245.8643 → IGV 44.26 frente a 44.25 de la valorización): el ajuste
        lleva la base sin redondear al subtotal (re-prueba E14)."""
        self.company.tax_calculation_rounding_method = 'round_globally'
        self.env.ref('product.decimal_price').digits = 4
        wizard = self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True,
        ).create({'stage': 'creval_tab', 'partner_id': self.contractor.id,
                  'condition_id': self.condition.id, 'date_start': date(2026, 11, 2)})
        wizard.line_ids.filtered(lambda r: r.activity_id == self.act_wall).price_unit = 221.30
        wizard.action_assign()
        order = self.env['purchase.order'].search([
            ('partner_id', '=', self.contractor.id),
            ('construction_project_id', '=', self.project.id)], order='id desc', limit=1)
        order.button_confirm()
        action = order.action_construction_register_advance()
        self._post(self.env['account.move'].browse(action['res_id']), date(2026, 11, 2))
        # Cuatro decimales en la cantidad, como en la base del cliente.
        self.env['decimal.precision'].search([('name', '=', 'Product Unit')]).digits = 4
        self._report(self.partida, self.act_wall, 1.111, date(2026, 11, 4))
        settlement = self._prepare()
        settlement.action_submit()
        settlement.action_validate()
        invoice = settlement.invoice_id
        self.assertAlmostEqual(invoice.amount_untaxed, settlement.amount_subtotal
                               - (settlement.amount_advance / 1.18 if settlement.amount_advance else 0),
                               delta=0.011)
        self.assertAlmostEqual(invoice.amount_total,
                               settlement.amount_total - settlement.amount_advance, places=2)
