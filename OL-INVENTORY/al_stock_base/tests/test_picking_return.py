# -*- coding: utf-8 -*-
"""Devolución de transferencias: aviso claro sin cantidades y destino de
respaldo cuando otro módulo lo deja vacío (mrp_subcontracting con el
asistente sin líneas)."""
from unittest.mock import patch

from odoo.addons.stock.wizard.stock_picking_return import StockReturnPicking
from odoo.exceptions import UserError
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
                'product_uom': cls.product.uom_id.id,
                'location_id': cls.stock.id, 'location_dest_id': cls.site.id})]})
        cls.picking.action_confirm()
        cls.picking.action_assign()
        cls.picking.move_ids.picked = True
        cls.picking.button_validate()

    def _wizard(self):
        return self.env['stock.return.picking'].with_context(
            active_id=self.picking.id, active_ids=self.picking.ids,
            active_model='stock.picking').create({'picking_id': self.picking.id})

    def test_return_without_quantity(self):
        wizard = self._wizard()
        with self.assertRaisesRegex(UserError, 'al menos un producto'):
            wizard.action_create_returns()
        wizard.product_return_moves = [(5,)]
        with self.assertRaisesRegex(UserError, 'al menos un producto'):
            wizard.action_create_returns()

    def test_return_destination_fallback(self):
        wizard = self._wizard()
        wizard.product_return_moves.quantity = 2
        native = StockReturnPicking._prepare_picking_default_values

        def without_destination(self):
            return dict(native(self), location_dest_id=False)

        with patch.object(StockReturnPicking, '_prepare_picking_default_values',
                          without_destination):
            action = wizard.action_create_returns()
        returned = self.env['stock.picking'].browse(action['res_id'])
        self.assertEqual(returned.location_id, self.site)
        self.assertEqual(returned.location_dest_id, self.stock)
        self.assertEqual(returned.move_ids.product_uom_qty, 2)
