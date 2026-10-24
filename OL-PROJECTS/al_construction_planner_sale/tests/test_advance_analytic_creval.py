# -*- coding: utf-8 -*-
"""Anticipo del cliente de una obra sin analítica (requerimiento CREVAL v1.0,
CR-13): no es ingreso de la obra. Datos ficticios."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestAdvanceAnalytic(TransactionCase):

    def test_down_payment_without_analytic(self):
        env = self.env
        project = env['project.project'].create({
            'name': 'OBR-02 Oficina de demostración (test)', 'is_construction_site': True,
            'allow_billable': True})
        if not project.account_id:
            project._create_analytic_account()
        partner = env['res.partner'].create({'name': 'Cliente de la obra (test)'})
        product = env['product.product'].create({
            'name': 'Partida de obra (test)', 'type': 'service', 'list_price': 1000.0,
            'invoice_policy': 'order'})
        order = env['sale.order'].create({
            'partner_id': partner.id, 'project_id': project.id,
            'order_line': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 10.0, 'price_unit': 1000.0,
                'analytic_distribution': {str(project.account_id.id): 100.0}})]})
        order.action_confirm()
        self.assertTrue(order._construction_is_site_order())
        wizard = env['sale.advance.payment.inv'].with_context(
            active_model='sale.order', active_ids=order.ids).create({
                'advance_payment_method': 'percentage', 'amount': 30.0})
        invoice = wizard._create_invoices(order)
        line = invoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        self.assertTrue(line.is_downpayment)
        self.assertFalse(line.analytic_distribution)
