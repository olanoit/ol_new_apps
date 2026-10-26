# -*- coding: utf-8 -*-
"""Compra masiva consolidada (v1.6, M16-01).

El caso de la prueba del 14-oct en newallcenter_dev_1 (orden P03012): tres
solicitudes del mismo producto, 100 y 40 consolidadas en una orden y 25
agregada después a la misma orden. OCA dejaba la línea en 100 y luego en 140,
cada solicitud con 140 comprados y el origen de la primera solicitud.
"""
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import ConstructionRequestCommon


@tagged('post_install', '-at_install')
class TestMassPurchase(ConstructionRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env['res.partner'].create({'name': 'Proveedor consolidado (test)'})
        # La segunda obra también la aprueba el jefe de obra de la prueba.
        cls.site_b.user_id = cls.approver

    def _purchase_request_line(self, project, qty):
        """Línea de solicitud de compra (OCA) aprobada que nace de un
        requerimiento de obra sin stock en el central."""
        request = self._new_request(project=project, lines=[(self.cement, qty)], user=self.requester)
        request.action_request_approval()
        request.with_user(self.approver).validate_tier()
        request = request.with_env(self.env)
        request.with_user(self.logistics).action_process()
        purchase_request = request.purchase_request_ids
        self.assertEqual(purchase_request.state, 'approved')
        return purchase_request.line_ids, request.line_ids

    def _make_order(self, pr_lines, order=None):
        wizard = self.env['purchase.request.line.make.purchase.order'].with_context(
            active_model='purchase.request.line', active_ids=pr_lines.ids,
        ).create({'supplier_id': self.vendor.id,
                  'purchase_order_id': order.id if order else False})
        action = wizard.make_purchase_order()
        return self.env['purchase.order'].browse(set(action['domain'][0][2]))

    def test_consolidated_order_sums_and_splits(self):
        line_a, mr_line_a = self._purchase_request_line(self.site_a, 100)
        line_b, mr_line_b = self._purchase_request_line(self.site_b, 40)
        line_c, mr_line_c = self._purchase_request_line(self.site_a, 25)
        self.assertEqual(line_a.al_qty_to_order, 100)

        # Paso 1: dos solicitudes juntas en una orden nueva.
        order = self._make_order(line_a | line_b)
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_qty, 140)

        # Paso 2: la tercera, agregada a la misma orden.
        self._make_order(line_c, order=order)
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_qty, 165)

        # Cada solicitud reporta como comprado solo su parte.
        self.assertEqual((line_a.purchased_qty, line_b.purchased_qty, line_c.purchased_qty),
                         (100, 40, 25))
        self.assertEqual((line_a.al_qty_to_order, line_b.al_qty_to_order, line_c.al_qty_to_order),
                         (0, 0, 0))
        # El requerimiento de cada obra, también.
        self.assertEqual((mr_line_a.qty_purchased, mr_line_b.qty_purchased, mr_line_c.qty_purchased),
                         (100, 40, 25))

        # El origen nombra las tres solicitudes con su obra.
        for line, site in ((line_a, self.site_a), (line_b, self.site_b), (line_c, self.site_a)):
            self.assertIn('%s (%s)' % (line.request_id.name, site.name), order.origin)

        # Stock general: la línea consolidada no lleva analítica de ninguna obra.
        self.assertFalse(order.order_line.analytic_distribution)

    def test_stock_purchase_with_site_analytic(self):
        """CR-16: con el ajuste de la compañía, la compra para el almacén lleva
        la analítica de cada obra (una línea por obra) y la partida."""
        self.env.company.construction_stock_purchase_analytic = True
        line_a, mr_line_a = self._purchase_request_line(self.site_a, 100)
        line_b, _mr_line_b = self._purchase_request_line(self.site_b, 40)
        order = self._make_order(line_a | line_b)
        self.assertEqual(len(order.order_line), 2)
        for po_line, pr_line in ((order.order_line.filtered(lambda l: l.product_qty == 100), line_a),
                                 (order.order_line.filtered(lambda l: l.product_qty == 40), line_b)):
            self.assertTrue(po_line.analytic_distribution)
            self.assertEqual(po_line.analytic_distribution, pr_line.analytic_distribution)
        self.assertEqual(order.order_line.filtered(lambda l: l.product_qty == 100)
                         .construction_request_task_ids, mr_line_a.task_id)

    def test_supplier_rounding_is_shared(self):
        """Si la orden compra más (mínimo del proveedor, redondeo), el exceso
        se reparte en proporción a lo que pidió cada solicitud."""
        line_a, _mr_a = self._purchase_request_line(self.site_a, 100)
        line_b, _mr_b = self._purchase_request_line(self.site_b, 50)
        order = self._make_order(line_a | line_b)
        order.order_line.product_qty = 165
        self.assertAlmostEqual(line_a.purchased_qty, 110)
        self.assertAlmostEqual(line_b.purchased_qty, 55)

    def test_single_request_keeps_oca_behaviour(self):
        line_a, _mr_a = self._purchase_request_line(self.site_a, 100)
        order = self._make_order(line_a)
        order.order_line.product_qty = 120
        self.assertEqual(line_a.purchased_qty, 120)

    def test_cancelled_order_frees_the_quantity(self):
        line_a, _mr_a = self._purchase_request_line(self.site_a, 100)
        order = self._make_order(line_a)
        self.assertEqual(line_a.al_qty_to_order, 0)
        order.button_cancel()
        self.assertEqual(line_a.al_qty_to_order, 100)
        self.assertEqual(line_a.purchased_qty, 0)

    def test_wizard_suggests_only_what_is_left_to_order(self):
        line_a, _mr_a = self._purchase_request_line(self.site_a, 100)
        wizard = self.env['purchase.request.line.make.purchase.order'].with_context(
            active_model='purchase.request.line', active_ids=line_a.ids,
        ).create({'supplier_id': self.vendor.id})
        wizard.item_ids.product_qty = 60
        wizard.make_purchase_order()
        self.assertEqual(line_a.al_qty_to_order, 40)
        again = self.env['purchase.request.line.make.purchase.order'].with_context(
            active_model='purchase.request.line', active_ids=line_a.ids,
        ).create({'supplier_id': self.vendor.id})
        self.assertEqual(again.item_ids.product_qty, 40)

    def test_mass_purchase_screen(self):
        line_a, _mr_a = self._purchase_request_line(self.site_a, 100)
        action = self.env.ref('al_construction_material_request.action_purchase_request_line_mass_purchase')
        domain = safe_eval(action.domain)
        self.assertIn(line_a, self.env['purchase.request.line'].search(domain))
        self._make_order(line_a)
        self.assertNotIn(line_a, self.env['purchase.request.line'].search(domain))
