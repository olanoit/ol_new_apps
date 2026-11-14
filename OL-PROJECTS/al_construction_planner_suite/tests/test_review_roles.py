# -*- coding: utf-8 -*-
"""Revisión por roles del 12-nov-2026: cada opción del menú abre su vista con el
rol que la ve.

* «Consulta» ve el plan, el árbol, el cronograma y el saldo (grupos en dos
  ejes), así que lee lo que esas pantallas muestran.
* Lo que es de Compras (la orden de contrata y sus líneas) se oculta a quien no
  tiene un rol de Compras o de Facturación, como hace Odoo."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user

P = 'al_construction_planner.'


@tagged('post_install', '-at_install')
class TestReviewRoles(TransactionCase):

    def _arch(self, user, model):
        return self.env[model].with_user(user).get_views([(False, 'form')])['views']['form']['arch']

    def test_viewer_reads_what_its_screens_show(self):
        viewer = new_test_user(self.env, login='review_viewer_120',
                               groups='base.group_user,' + P + 'group_planner_plan_viewer')
        # Inicio y Árbol de recursos (avances), ficha del recurso planificado
        # (uso de equipo), ficha de la tarea (roles) y valorización de contrata
        # (su resumen).
        for model in ['construction.task.progress', 'construction.equipment.usage', 'project.role',
                      'construction.contract.settlement.summary', 'construction.contract.deduction',
                      'construction.contract.order.document']:
            if model not in self.env:
                continue
            with self.subTest(model=model):
                self.assertTrue(self.env[model].with_user(viewer).has_access('read'), model)
                self.assertFalse(self.env[model].with_user(viewer).has_access('write'), model)

    def test_purchase_fields_need_a_purchase_role(self):
        executor = new_test_user(self.env, login='review_executor_120',
                                 groups='base.group_user,' + P + 'group_planner_user')
        buyer = new_test_user(self.env, login='review_buyer_120',
                              groups='base.group_user,purchase.group_purchase_user,' + P + 'group_planner_user')
        if 'construction.contract.intervention' in self.env:
            self.assertNotIn('purchase_order_id', self._arch(executor, 'construction.contract.intervention'))
            self.assertIn('purchase_order_id', self._arch(buyer, 'construction.contract.intervention'))
        if 'construction_purchase_line_ids' in self.env['construction.change.order']._fields:
            arch = self._arch(executor, 'construction.change.order')
            self.assertNotIn('construction_purchase_order_id', arch)
            self.assertNotIn('construction_purchase_line_ids', arch)
            self.assertIn('construction_purchase_line_ids', self._arch(buyer, 'construction.change.order'))
        # «Órdenes de contrata» queda en el menú para quien tiene Compras.
        menu = self.env.ref('al_construction_planner_subcontract.menu_planner_service_orders',
                            raise_if_not_found=False)
        if menu:
            Menu = self.env['ir.ui.menu']
            self.assertNotIn(menu.id, Menu.with_user(executor)._visible_menu_ids())
            self.assertIn(menu.id, Menu.with_user(buyer)._visible_menu_ids())

    def test_viewer_home_with_sale_order(self):
        """Inicio muestra el nombre de la venta de la obra a quien consulta el
        plan, sin el rol de Ventas."""
        if 'construction_sale_order_id' not in self.env['project.project']._fields:
            self.skipTest('Sin el puente de ventas')
        viewer = new_test_user(self.env, login='review_home_viewer_120',
                               groups='base.group_user,' + P + 'group_planner_plan_viewer')
        partner = self.env['res.partner'].create({'name': 'Cliente revisión 1.20 (test)'})
        order = self.env['sale.order'].create({'partner_id': partner.id})
        project = self.env['project.project'].create({
            'name': 'Obra con venta (test revisión)', 'is_construction_site': True,
            'construction_sale_order_id': order.id})
        self.assertFalse(self.env['sale.order'].with_user(viewer).has_access('read'))
        self.env.invalidate_all()
        data = self.env['construction.planner.home'].with_user(viewer).get_home_data()
        rows = [row for key in ('works', 'unplanned') for row in data.get(key) or []
                if row.get('project_id') == project.id]
        self.assertTrue(rows)
