# -*- coding: utf-8 -*-
"""Orden de corte con dos tableros y tapacanto (datos inventados).

Consumo: tablero blanco S/ 100, tablero roble S/ 200 y 3 m de tapacanto a
S/ 1, más S/ 10 de costo extra: S/ 313.

| Salida     | Tablero | Área | Tapacanto | Tablero  | Tapacanto | General | Costo    |
|------------|---------|------|-----------|----------|-----------|---------|----------|
| Lateral    | blanco  | 0.50 | 2         | 66.6667  | 2         | 3.7037  | 72.3704  |
| Repisa     | blanco  | 0.25 | 0         | 33.3333  | 0         | 1.8519  | 35.1852  |
| Puerta     | roble   | 0.50 | 1         | 200      | 1         | 3.7037  | 204.7037 |
| Principal  | —       | 0.10 | 0         | —        | —         | 0.7407  | 0.7407   |
"""
import io

from odoo.tools import BinaryBytes
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPieceCosting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['product.category'].create({
            'name': 'Piezas de corte (test)', 'property_cost_method': 'average'})
        Product = cls.env['product.product']

        def product(name, cost=0.0, **vals):
            return Product.create(dict({
                'name': name, 'is_storable': True, 'categ_id': cls.category.id,
                'standard_price': cost}, **vals))

        cls.white = product('Tablero blanco (test)', 100.0, default_code='BL18T')
        cls.oak = product('Tablero roble (test)', 200.0, default_code='RO18T')
        cls.edge = product('Tapacanto blanco (test)', 1.0, default_code='TBL22T',
                           piece_is_edge_banding=True)
        cls.side = product('Lateral (test)', piece_is_cut=True, piece_area_m2=0.5,
                           piece_edge_ml=2.0, piece_material_id=cls.white.id)
        cls.shelf = product('Repisa (test)', piece_is_cut=True, piece_area_m2=0.25,
                            piece_material_id=cls.white.id)
        cls.door = product('Puerta (test)', piece_is_cut=True, piece_area_m2=0.5,
                           piece_edge_ml=1.0, piece_material_id=cls.oak.id)
        cls.main = product('Corte OP 999 (test)', piece_area_m2=0.1)
        stock = cls.env.ref('stock.stock_location_stock')
        Quant = cls.env['stock.quant']
        for component, qty in ((cls.white, 5), (cls.oak, 5), (cls.edge, 50)):
            Quant._update_available_quantity(component, stock, qty)
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.main.product_tmpl_id.id, 'product_qty': 1,
            # Odoo 20: la OP toma el costo extra de la LdM al crearse.
            'extra_cost': 10.0,
            'bom_line_ids': [
                Command.create({'product_id': cls.white.id, 'product_qty': 1}),
                Command.create({'product_id': cls.oak.id, 'product_qty': 1}),
                Command.create({'product_id': cls.edge.id, 'product_qty': 3})],
            'byproduct_ids': [
                Command.create({'product_id': piece.id, 'product_qty': 1})
                for piece in (cls.side, cls.shelf, cls.door)],
        })
        cls.picking_type = cls.env['stock.picking.type'].search(
            [('code', '=', 'mrp_operation'), ('company_id', '=', cls.env.company.id)], limit=1)

    def _production(self, **vals):
        production = self.env['mrp.production'].create(dict({
            'product_id': self.main.id, 'bom_id': self.bom.id, 'product_qty': 1,
            'picking_type_id': self.picking_type.id,
            'piece_costing': True}, **vals))
        return production

    def _produce(self, production):
        production.action_confirm()
        with Form(production) as form:
            form.qty_producing = production.product_qty
        production.move_raw_ids.picked = True
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        return production

    def _value(self, production, product):
        return production.move_finished_ids.filtered(lambda m: m.product_id == product).value

    def test_costs_by_area_material_and_edge(self):
        production = self._produce(self._production())
        self.assertAlmostEqual(self._value(production, self.side), 72.37, places=2)
        self.assertAlmostEqual(self._value(production, self.shelf), 35.19, places=2)
        self.assertAlmostEqual(self._value(production, self.door), 204.70, places=2)
        self.assertAlmostEqual(self._value(production, self.main), 0.74, delta=0.011)  # redondeo de 20
        self.assertAlmostEqual(production.piece_total_cost, 313.0, places=2)
        self.assertLessEqual(abs(production.piece_balance_diff), 1.0)
        self.assertFalse(production.piece_has_manual_value)
        door_move = production.move_finished_ids.filtered(lambda m: m.product_id == self.door)
        self.assertAlmostEqual(door_move.cost_share, 204.7037 / 313 * 100, places=2)

    def test_remnant_fixed_cost(self):
        """Retazo del tablero blanco declarado en el corte (paquete 1.11,
        M111-12): sale a su costo fijo (S/ 20), que se descuenta del tablero
        blanco; las piezas se reparten el resto y todo suma el costo de la
        orden."""
        remnant = self.env['product.product'].create({
            'name': 'Retazo blanco (test)', 'is_storable': True, 'categ_id': self.category.id,
            'construction_is_remnant': True,
            'construction_remnant_source_tmpl_id': self.white.product_tmpl_id.id})
        production = self._production()
        production.action_confirm()
        vals = production._get_move_finished_values(remnant.id, 1.0, remnant.uom_id.id)
        vals['construction_fixed_cost'] = 20.0
        production.write({'move_finished_ids': [Command.create(vals)]})
        with Form(production) as form:
            form.qty_producing = production.product_qty
        production.move_raw_ids.picked = True
        production.move_finished_ids.filtered(lambda m: m.product_id == remnant).quantity = 1.0
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        self.assertAlmostEqual(self._value(production, remnant), 20.0, places=2)
        # Lateral: 80 × 0.5 / 0.75 del blanco + 2 de tapacanto + 3.7037 general.
        self.assertAlmostEqual(self._value(production, self.side), 59.04, places=2)
        self.assertAlmostEqual(self._value(production, self.door), 204.70, places=2)
        self.assertAlmostEqual(sum(production.move_finished_ids.mapped('value')), 313.0, places=1)

    def test_without_costing_follows_standard(self):
        production = self._produce(self._production(piece_costing=False))
        self.assertAlmostEqual(self._value(production, self.door), 0.0, places=2)
        self.assertAlmostEqual(self._value(production, self.main), 313.0, places=2)

    def test_default_from_operation_type(self):
        self.picking_type.piece_costing_default = True
        production = self.env['mrp.production'].create({
            'product_id': self.main.id, 'bom_id': self.bom.id,
            'picking_type_id': self.picking_type.id})
        self.assertTrue(production.piece_costing)

    def test_checks_on_confirm(self):
        self.shelf.piece_area_m2 = 0.0
        with self.assertRaisesRegex(UserError, 'no tienen área'):
            self._production().action_confirm()
        self.shelf.piece_area_m2 = 0.25
        self.door.piece_material_id = self.env['product.product'].create(
            {'name': 'Tablero gris (test)'})
        with self.assertRaisesRegex(UserError, 'no consume el tablero'):
            self._production().action_confirm()

    def test_no_backorder_nor_unbuild(self):
        production = self._production()
        production.action_confirm()
        with self.assertRaises(UserError):
            production._get_backorder_mo_vals()
        production = self._produce(self._production())
        unbuild = self.env['mrp.unbuild'].create({
            'product_id': self.main.id, 'bom_id': self.bom.id, 'mo_id': production.id,
            'product_qty': 1})
        with self.assertRaises(UserError):
            unbuild.action_validate()

    def _workbook(self, rows):
        import openpyxl
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(['Obra', 'Mueble terminado', 'Modulo', 'ID pieza', 'Material', 'Largo mm',
                      'Ancho mm', 'Area m2', 'Tapacanto codigo', 'Tapacanto ml', 'Cantidad'])
        for row in rows:
            sheet.append(row)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return BinaryBytes(buffer.getvalue())

    def test_import_pieces(self):
        data = self._workbook([
            ['MC3', 'Cocina', 'MA01', '1', 'BL18T', 700, 560, None, 'TBL22T', 1.26, 2],
            ['MC3', 'Cocina', 'MA01', '2', 'RO18T', 700, 300, 0.25, None, 0, 1],
        ])
        wizard = self.env['mrp.piece.import.wizard'].create({
            'file': data, 'file_name': 'despiece.xlsx', 'categ_id': self.category.id})
        wizard.action_import()
        self.assertEqual(wizard.state, 'done')
        self.assertIn('creadas: 2', wizard.summary)
        self.assertIn('difiere', wizard.summary)
        first = self.env['product.product'].search([('default_code', '=', 'MC3-1')])
        self.assertTrue(first.piece_is_cut)
        self.assertAlmostEqual(first.piece_area_m2, 0.392)
        self.assertEqual(first.piece_material_id, self.white)
        self.assertEqual(first.piece_project_ref, 'MC3')
        # Volver a importar actualiza.
        wizard = self.env['mrp.piece.import.wizard'].create({
            'file': data, 'categ_id': self.category.id})
        wizard.action_import()
        self.assertIn('actualizadas: 2', wizard.summary)

    def test_import_all_or_nothing(self):
        self.edge.piece_is_edge_banding = False
        data = self._workbook([
            ['MC4', 'Cocina', 'MA01', '1', 'BL18T', 700, 560, None, 'TBL22T', 1.26, 1],
            ['MC4', 'Cocina', 'MA01', '1', 'XX99', 700, 560, None, None, 0, 1],
        ])
        wizard = self.env['mrp.piece.import.wizard'].create({
            'file': data, 'categ_id': self.category.id})
        with self.assertRaisesRegex(UserError, 'no se importó nada'):
            wizard.action_import()
        self.assertFalse(self.env['product.product'].search([('default_code', '=', 'MC4-1')]))

    def test_operation_type_view(self):
        with Form(self.picking_type) as form:
            form.piece_costing_default = True
        self.assertTrue(self.picking_type.piece_costing_default)
