# -*- coding: utf-8 -*-
"""Requerimiento de obra con tableros en planchas enteras (paquete 1.11,
M111-12, regla 8.4)."""
from odoo.tests import tagged

from .test_process import TestProcess


@tagged('post_install', '-at_install')
class TestWholeSheetRequest(TestProcess):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.construction_whole_sheet = True
        square_meter = cls.env.ref('uom.product_uom_square_meter')
        uom_sheet = cls.env['uom.uom'].create({
            'name': 'Plancha 2.14×2.44 m (test)', 'relative_factor': 5.2216,
            'relative_uom_id': square_meter.id, 'construction_whole_sheet': True})
        cls.board = cls.env['product.product'].create({
            'name': 'Melamina blanco RH 18 mm (test)', 'type': 'consu', 'is_storable': True,
            'uom_id': uom_sheet.id, 'standard_price': 150.0})

    def _line(self, request, product):
        return request.line_ids.filtered(lambda l: l.product_id == product)

    # 10: 13.3 con 10.6 libres → despacha 10, compra 4, redondeo 0.7.
    def test_whole_sheets_split(self):
        self._set_stock(self.board, self.stock, 10.6)
        request = self._approved_request(lines=[(self.board, 13.3)])
        self._process(request)
        line = self._line(request, self.board)
        self.assertEqual(line.qty_to_dispatch, 10.0)
        self.assertEqual(line.qty_to_purchase, 4.0)
        self.assertAlmostEqual(line.qty_rounding, 0.7)
        self.assertEqual(self._dispatch_picking(request).move_ids.quantity, 10.0)
        self.assertEqual(request.purchase_request_ids.line_ids.product_qty, 4.0)

    def test_whole_sheets_enough_stock(self):
        self._set_stock(self.board, self.stock, 20)
        request = self._approved_request(lines=[(self.board, 13.3)])
        self._process(request)
        line = self._line(request, self.board)
        self.assertEqual((line.qty_to_dispatch, line.qty_to_purchase), (14.0, 0.0))
        self.assertFalse(request.purchase_request_ids)

    # 19 y criterio 5: sin tableros (o con la casilla apagada), como hoy.
    def test_other_products_unchanged(self):
        self._set_stock(self.cement, self.stock, 2)
        request = self._approved_request(lines=[(self.cement, 3.5)])
        self._process(request)
        line = self._line(request, self.cement)
        self.assertEqual((line.qty_to_dispatch, line.qty_to_purchase), (2.0, 1.5))
        self.assertFalse(line.qty_rounding)

    def test_switch_off(self):
        self.company.construction_whole_sheet = False
        self._set_stock(self.board, self.stock, 10.6)
        request = self._approved_request(lines=[(self.board, 13.3)])
        self._process(request)
        line = self._line(request, self.board)
        self.assertAlmostEqual(line.qty_to_dispatch, 10.6)
        self.assertAlmostEqual(line.qty_to_purchase, 2.7)


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestProcess):
    if _name.startswith('test_') and callable(getattr(TestProcess, _name)) \
            and _name not in vars(TestWholeSheetRequest):
        setattr(TestWholeSheetRequest, _name, None)
