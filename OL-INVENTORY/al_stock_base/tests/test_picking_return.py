# -*- coding: utf-8 -*-
"""Devolución de transferencias (Odoo 20: albarán de devolución directo)."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPickingReturn(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.site = cls.env['stock.location'].create({
            'name': 'Obra devolución (test)', 'usage': 'internal',
            'location_id': cls.warehouse.view_location_id.id})
        cls.product = cls.env['product.product'].create({
            'name': 'Tornillo devolución (test)', 'is_storable': True})
        cls.env['stock.quant']._update_available_quantity(cls.product, cls.stock, 10)
        cls.picking = cls.env['stock.picking'].create({
            'picking_type_id': cls.warehouse.int_type_id.id,
            'location_id': cls.stock.id, 'location_dest_id': cls.site.id,
            'move_ids': [(0, 0, {
                'product_id': cls.product.id, 'product_uom_qty': 3,
                'uom_id': cls.product.uom_id.id,
                'location_id': cls.stock.id, 'location_dest_id': cls.site.id})]})
        cls.picking.action_confirm()
        cls.picking.action_assign()
        cls.picking.move_ids.picked = True
        cls.picking.button_validate()

    def test_return_with_quantity(self):
        # Odoo 20: la devolución es un albarán borrador con las cantidades
        # de la transferencia, que se ajustan antes de validarla.
        returned = self.picking._create_return()
        self.assertEqual(returned.location_id, self.site)
        self.assertEqual(returned.location_dest_id, self.stock)
        returned.move_ids.product_uom_qty = 2
        self.assertEqual(returned.move_ids.product_uom_qty, 2)
