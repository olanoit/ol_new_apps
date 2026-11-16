# -*- coding: utf-8 -*-
"""Validar movimientos de almacén con el puente de compras (CR-16): recepción
de proveedor, despacho a obra, devolución y ajuste de inventario. El puente no
depende de Fabricación y ninguno de estos pasos puede leer sus campos. Datos
ficticios."""
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.warehouse = env['stock.warehouse'].search(
            [('company_id', '=', env.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.supplier_location = env.ref('stock.stock_location_suppliers')
        cls.site = env['stock.location'].create({
            'name': 'Obra flujo de almacén (test)', 'usage': 'internal',
            'location_id': cls.warehouse.view_location_id.id})
        cls.product = env['product.product'].create({
            'name': 'Cemento flujo de almacén (test)', 'is_storable': True})

    def _validate(self, picking_type, source, dest, qty):
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source.id, 'location_dest_id': dest.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': qty,
                'product_uom': self.product.uom_id.id,
                'location_id': source.id, 'location_dest_id': dest.id})]})
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        return picking

    def _qty(self, location):
        return self.product.with_context(location=location.id).qty_available

    def test_receipt_dispatch_and_return(self):
        self._validate(self.warehouse.in_type_id, self.supplier_location, self.stock, 5)
        dispatch = self._validate(self.warehouse.int_type_id, self.stock, self.site, 3)
        self.assertEqual(self._qty(self.site), 3)
        wizard = self.env['stock.return.picking'].with_context(
            active_id=dispatch.id, active_ids=dispatch.ids,
            active_model='stock.picking').create({'picking_id': dispatch.id})
        wizard.product_return_moves.quantity = 1
        returned = self.env['stock.picking'].browse(wizard.action_create_returns()['res_id'])
        self.assertEqual(returned.location_dest_id, self.stock)
        returned.move_ids.picked = True
        returned.button_validate()
        self.assertEqual(returned.state, 'done')
        self.assertEqual(self._qty(self.site), 2)
        self.assertEqual(self._qty(self.stock), 3)

    def test_inventory_adjustment(self):
        quant = self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id, 'location_id': self.stock.id,
            'inventory_quantity': 7})
        quant.action_apply_inventory()
        self.assertEqual(self._qty(self.stock), 7)

    def test_client_supply_received_at_site(self):
        """CR-06: lo que el cliente entrega en la obra suma a «Recibido del
        cliente» de su línea del plan; lo que se le devuelve, resta."""
        env = self.env
        env['tier.definition'].search([('model', '=', 'construction.resource.plan')]).active = False
        stage = env['construction.stage'].create({
            'name': 'Equipamiento del cliente (test)', 'code': 'client_supply_test',
            'sequence': 931})
        customer = env['res.partner'].create({'name': 'Cliente de la obra (test)'})
        project = env['project.project'].create({
            'name': 'Obra con suministro del cliente (test)', 'is_construction_site': True,
            'partner_id': customer.id, 'construction_location_id': self.site.id})
        task = env['project.task'].create({'name': '9.01 Televisores (test)',
                                           'project_id': project.id})
        plan = env['construction.resource.plan'].create({'project_id': project.id})
        line = env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'task_id': task.id, 'resource_type': 'material',
            'product_id': self.product.id, 'product_uom_id': self.product.uom_id.id,
            'qty_planned': 4.0, 'stage': stage.code, 'is_client_supply': True,
            'price_unit_planned': 0.0})
        plan.action_request_approval()
        customers = env.ref('stock.stock_location_customers')
        self._validate(self.warehouse.in_type_id, customers, self.site, 3)
        self.assertEqual(line.qty_client_received, 3.0)
        self._validate(self.warehouse.int_type_id, self.site, customers, 1)
        self.assertEqual(line.qty_client_received, 2.0)
        # Lo que llega del almacén central no es del cliente.
        self._validate(self.warehouse.in_type_id, self.supplier_location, self.stock, 5)
        self._validate(self.warehouse.int_type_id, self.stock, self.site, 2)
        self.assertEqual(line.qty_client_received, 2.0)

    def test_site_lookup_once_per_location(self):
        """Una recepción o una entrega que no es de obra busca la obra una vez
        por ubicación, no una vez por movimiento (comparte la base con ventas,
        farmacia y punto de venta)."""
        products = self.product | self.env['product.product'].create([
            {'name': 'Producto sin obra %s (test)' % index, 'is_storable': True}
            for index in range(3)])
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.in_type_id.id,
            'location_id': self.supplier_location.id, 'location_dest_id': self.stock.id,
            'move_ids': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 2,
                'product_uom': product.uom_id.id, 'location_id': self.supplier_location.id,
                'location_dest_id': self.stock.id}) for product in products]})
        picking.action_confirm()
        picking.move_ids.quantity = 2
        picking.move_ids.picked = True
        picking.button_validate()
        moves = picking.move_ids
        self.assertEqual(set(moves.mapped('state')), {'done'})
        Project = self.env.registry['project.project']
        original = Project.search
        lookups = []

        def counting_search(records, domain, *args, **kwargs):
            if 'construction_location_id' in str(domain):
                lookups.append(domain)
            return original(records, domain, *args, **kwargs)

        with patch.object(Project, 'search', counting_search):
            moves._construction_client_supply_received()
        self.assertEqual(len(moves), 4)
        self.assertEqual(len(lookups), 1)

    def test_done_qty_sums_in_the_database(self):
        """Lo hecho se suma en la base; solo los movimientos en otra unidad se
        leen para convertirlos, con el mismo resultado que uno por uno."""
        dozen = self.env.ref('uom.product_uom_dozen')
        self._validate(self.warehouse.in_type_id, self.supplier_location, self.stock, 100)
        for qty in (3, 4.5):
            self._validate(self.warehouse.int_type_id, self.stock, self.site, qty)
        Allocation = self.env['construction.resource.plan.allocation']
        Move = self.env.registry['stock.move']
        domain = [('state', '=', 'done'), ('product_id', '=', self.product.id),
                  ('location_dest_id', 'child_of', self.site.id)]
        with patch.object(Move, 'search', side_effect=AssertionError('lee los movimientos')):
            self.assertAlmostEqual(Allocation._construction_done_qty(self.product, domain), 7.5)
        # Un despacho en docenas: se convierte a la unidad del producto.
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.int_type_id.id,
            'location_id': self.stock.id, 'location_dest_id': self.site.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 2, 'product_uom': dozen.id,
                'location_id': self.stock.id, 'location_dest_id': self.site.id})]})
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        moves = self.env['stock.move'].search(domain)
        one_by_one = sum(move.product_uom._compute_quantity(
            move.quantity, self.product.uom_id, rounding_method='HALF-UP') for move in moves)
        self.assertAlmostEqual(one_by_one, 31.5)
        self.assertAlmostEqual(Allocation._construction_done_qty(self.product, domain), 31.5)

