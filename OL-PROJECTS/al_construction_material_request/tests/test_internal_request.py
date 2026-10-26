# -*- coding: utf-8 -*-
"""Requerimiento interno de las áreas (paquete 1.11, M111-10)."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .common import ConstructionRequestCommon

TIER_INTERNAL = 'al_construction_material_request.tier_definition_internal_department_manager'


@tagged('post_install', '-at_install')
class TestInternalRequest(ConstructionRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env['account.analytic.plan'].create({'name': 'Área (test)'})
        cls.company.construction_area_plan_id = plan
        cls.area = cls.env['account.analytic.account'].create({
            'name': 'Comercial (test)', 'plan_id': plan.id, 'company_id': cls.company.id})
        cls.env.ref(TIER_INTERNAL).active = True
        grp = 'al_construction_material_request.group_construction_'
        cls.sales_user = new_test_user(
            cls.env, 'rqi_comercial', groups=f'{grp}requester', name='Vendedora (test)')
        cls.sales_head = new_test_user(
            cls.env, 'rqi_jefe_comercial', groups=f'{grp}approver', name='Jefe comercial (test)')
        cls.has_hr = 'hr.employee' in cls.env
        if cls.has_hr:
            Employee = cls.env['hr.employee']
            head = Employee.create({'name': 'Jefe comercial (test)', 'user_id': cls.sales_head.id})
            department = cls.env['hr.department'].create({
                'name': 'Comercial (test)', 'manager_id': head.id})
            Employee.create({'name': 'Vendedora (test)', 'user_id': cls.sales_user.id,
                             'department_id': department.id})
        Product = cls.env['product.product']
        cls.paper = Product.create({
            'name': 'Papel A4 paquete (test)', 'type': 'consu', 'is_storable': True,
            'standard_price': 12.0})
        cls.marker = Product.create({
            'name': 'Plumón (test)', 'type': 'consu', 'is_storable': True,
            'standard_price': 3.0})

    def _internal_request(self, lines=None):
        return self.env['construction.material.request'].with_user(self.sales_user).create({
            'request_type': 'internal',
            'area_id': self.area.id,
            'line_ids': [(0, 0, {'product_id': product.id, 'product_qty': qty})
                         for product, qty in (lines or [(self.paper, 2), (self.marker, 5)])],
        })

    def _approve(self, request):
        request.action_request_approval()
        if request.state == 'to_approve':
            request.with_user(self.sales_head).validate_tier()
        self.assertEqual(request.state, 'approved')
        return request.with_env(self.env)

    def test_internal_flow(self):
        self._set_stock(self.paper, self.stock, 10)
        request = self._internal_request()
        self.assertFalse(request.project_id)
        self.assertEqual(request.analytic_distribution, {str(self.area.id): 100})
        self.assertEqual(request.line_ids.mapped('analytic_distribution'),
                         [{str(self.area.id): 100}] * 2)
        request = self._approve(request.with_user(self.sales_user))
        if self.has_hr:
            # Lo aprobó el jefe del departamento de la solicitante.
            self.assertEqual(request.construction_department_manager_id, self.sales_head)
            self.assertEqual(request.review_ids.done_by, self.sales_head)
        warehouse = self.stock.warehouse_id
        consumption = warehouse.construction_consumption_location_id
        self.assertEqual(consumption.usage, 'inventory')
        self.assertEqual(request.location_dest_id, consumption)

        request.with_user(self.logistics).action_process()
        dispatch = request.picking_ids.filtered(
            lambda p: p.move_ids.filtered(lambda m: m.procure_method == 'make_to_stock'))
        self.assertEqual(dispatch.picking_type_id, warehouse.construction_internal_type_id)
        self.assertEqual(dispatch.picking_type_id.sequence_code, 'CI')
        self.assertEqual(dispatch.location_dest_id, consumption)
        self.assertEqual(dispatch.move_ids.product_id, self.paper)
        # Sin plumones: requerimiento de compra con la analítica del área.
        purchase = request.purchase_request_ids
        self.assertEqual(purchase.line_ids.product_id, self.marker)
        self.assertEqual(purchase.line_ids.analytic_distribution, {str(self.area.id): 100})
        self.assertIn('Comercial (test)', purchase.description)

        # El almacenero lo ve en «Productos por despachar» y lo valida.
        dispatch.move_ids.picked = True
        dispatch.with_user(self.logistics).button_validate()
        self.assertEqual(dispatch.state, 'done')
        self.assertEqual(self.paper.with_context(location=self.stock.id).qty_available, 8)
        paper_line = request.line_ids.filtered(lambda l: l.product_id == self.paper)
        self.assertEqual(paper_line.line_state, 'done')
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_construction_material_request.action_report_construction_dispatch_slip',
            dispatch.ids)[0].decode()
        self.assertIn('Área', html)
        self.assertIn('Comercial (test)', html)

    def test_internal_expense_analytic(self):
        """El costo va a la cuenta de gasto de la ubicación con la analítica del área."""
        expense = self.env['account.account'].search([
            ('company_ids', 'in', self.company.id), ('account_type', '=', 'expense')], limit=1)
        if not expense or not self.company.account_stock_journal_id:
            self.skipTest('Sin plan contable con diario de inventario.')
        self.paper.categ_id = self.env['product.category'].create({
            'name': 'Útiles (test)', 'property_valuation': 'real_time'})
        self._set_stock(self.paper, self.stock, 10)
        request = self._approve(self._internal_request(lines=[(self.paper, 2)]))
        request.location_dest_id.valuation_account_id = expense
        request.with_user(self.logistics).action_process()
        dispatch = request.picking_ids
        dispatch.move_ids.picked = True
        dispatch.with_user(self.logistics).button_validate()
        lines = dispatch.move_ids.account_move_id.line_ids
        expense_line = lines.filtered(lambda l: l.account_id == expense)
        self.assertTrue(expense_line)
        self.assertEqual(expense_line.analytic_distribution, {str(self.area.id): 100})

    def test_internal_requires_area_and_site_requires_project(self):
        request = self.env['construction.material.request'].with_user(self.sales_user).create({
            'request_type': 'internal',
            'line_ids': [(0, 0, {'product_id': self.paper.id, 'product_qty': 1})],
        })
        with self.assertRaises(UserError):
            request.action_request_approval()
        with self.assertRaises(ValidationError):
            self.env['construction.material.request'].create({
                'request_type': 'site',
                'line_ids': [(0, 0, {'product_id': self.paper.id, 'product_qty': 1})],
            })
        # El interno puede llevar la obra (CREVAL 7.3): se carga a su área.
        internal = self.env['construction.material.request'].create({
            'request_type': 'internal', 'project_id': self.site_a.id,
            'line_ids': [(0, 0, {'product_id': self.paper.id, 'product_qty': 1})],
        })
        self.assertEqual(internal.project_id, self.site_a)

    def test_setup_without_area_plan_as_logistics(self):
        """Procesar en una compañía sin plan de áreas no lee planes
        analíticos: Logística no tiene acceso a ellos."""
        self.company.construction_area_plan_id = False
        self.company.with_user(self.logistics)._al_construction_ensure_setup()
        self.assertFalse(self.company.construction_area_plan_id)
        # «Completar configuración» (administrador) toma el plan «Área».
        self.env['account.analytic.plan'].create({'name': 'Área'})
        settings = self.env['res.config.settings'].create({})
        settings.action_al_construction_setup()
        self.assertEqual(self.company.construction_area_plan_id.name, 'Área')
