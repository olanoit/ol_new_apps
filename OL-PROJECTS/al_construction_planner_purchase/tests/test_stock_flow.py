# -*- coding: utf-8 -*-
"""Validar movimientos de almacén con el puente de compras (CR-16): recepción
de proveedor, despacho a obra, devolución y ajuste de inventario. El puente no
depende de Fabricación y ninguno de estos pasos puede leer sus campos. Datos
ficticios."""
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
