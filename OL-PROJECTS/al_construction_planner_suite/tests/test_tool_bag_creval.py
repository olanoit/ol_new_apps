# -*- coding: utf-8 -*-
"""Bolsa de herramientas manuales (requerimiento CREVAL v1.0, 6.1): la compra
de herramientas cargada a la obra consume la línea en % de la mano de obra."""
from datetime import date

from odoo import Command
from odoo.tests import tagged

from .test_income import IncomeCommon


@tagged('post_install', '-at_install')
class TestToolBag(IncomeCommon):

    def test_purchase_consumes_tool_bag(self):
        category = self.env['product.category'].create({'name': 'Herramientas manuales (test)'})
        self.company.construction_hand_tools_categ_id = category
        shovel = self.env['product.product'].create({
            'name': 'Lampa (test)', 'categ_id': category.id, 'purchase_ok': True})
        bag = self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create({
                'plan_id': self.plan.id, 'task_id': self.space.id, 'resource_type': 'equipment',
                'product_uom_id': self.unit.id, 'stage': 'installation',
                'calc_method': 'pct_labor', 'calc_pct': 5.0, 'qty_planned': 0.05,
                'price_unit_planned': 52000.0})
        supplier = self.env['res.partner'].create({'name': 'Ferretería (test)'})
        analytic = {str(self.project.account_id.id): 100.0}
        order = self.env['purchase.order'].create({
            'partner_id': supplier.id, 'order_line': [Command.create({
                'product_id': shovel.id, 'product_qty': 10, 'price_unit': 35.0,
                'analytic_distribution': analytic})]})
        order.button_confirm()
        committed, actual = bag._get_line_execution()[bag]
        self.assertEqual((committed, actual), (350.0, 0.0))
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': supplier.id,
            'invoice_date': date(2026, 11, 3),
            'invoice_line_ids': [Command.create({
                'product_id': shovel.id, 'quantity': 4, 'price_unit': 35.0,
                'purchase_line_id': order.order_line.id, 'tax_ids': [Command.clear()],
                'analytic_distribution': analytic})]})
        if 'l10n_latam_use_documents' in bill._fields and bill.l10n_latam_use_documents:
            bill.l10n_latam_document_number = 'F001-%06d' % bill.id
        bill.action_post()
        committed, actual = bag._get_line_execution()[bag]
        self.assertEqual((committed, actual), (210.0, 140.0))
