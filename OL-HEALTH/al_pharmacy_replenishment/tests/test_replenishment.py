# -*- coding: utf-8 -*-
# Odoo 20: los ayudantes de stock (adjust_inventory) están en pos_stock.
from odoo.addons.pos_stock.tests.common import TestPosStockCommon as TestPoSCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged


@tagged('post_install', '-at_install')
class TestReplenishment(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        # Odoo 20: company_data ya no trae el almacén por defecto.
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.units = cls.env.ref('uom.product_uom_unit')
        cls.box_10 = cls.env['uom.uom'].create({
            'name': 'Caja x 10', 'relative_factor': 10, 'relative_uom_id': cls.units.id})
        cls.vendor_a = cls.env['res.partner'].create({'name': 'Droguería Andina'})
        cls.vendor_b = cls.env['res.partner'].create({'name': 'Distribuidora del Sur'})
        category = cls.env['product.category'].create({'name': 'Farmacia'})
        # Se compra en cajas de 10 al proveedor A.
        cls.losartan = cls.create_product('Losartán 50 mg', category, 0.50)
        cls.losartan.product_tmpl_id.write({
            'pharmacy_ok': True,
            'seller_ids': [(0, 0, {'partner_id': cls.vendor_a.id, 'uom_id': cls.box_10.id,
                                   'price': 3.0})],
        })
        # Se compra por unidad al proveedor B, pero se vende en cajas de 20.
        cls.metformin = cls.create_product('Metformina 850 mg', category, 0.20)
        cls.metformin.product_tmpl_id.write({
            'pharmacy_ok': True,
            'seller_ids': [(0, 0, {'partner_id': cls.vendor_b.id, 'price': 0.08})],
        })
        cls.env['pharmacy.presentation'].create({
            'product_tmpl_id': cls.metformin.product_tmpl_id.id, 'name': 'Caja', 'factor': 20,
            'price': 3.50})
        # Sin ventas: solo un faltante pendiente.
        cls.insulin = cls.create_product('Insulina NPH 100 UI/ml', category, 30.0)
        cls.insulin.product_tmpl_id.write({
            'pharmacy_ok': True,
            'seller_ids': [(0, 0, {'partner_id': cls.vendor_a.id, 'price': 20.0})],
        })
        # Stock antes de vender: después de la venta quedan 5 y 0.
        cls.adjust_inventory([cls.losartan, cls.metformin], [35, 15])

    def _sell_in_pos(self):
        self.open_new_session()
        self._create_orders([
            {'pos_order_lines_ui_args': [(self.losartan, 30)],
             'payments': [(self.cash_pm1, 15.0)]},
            {'pos_order_lines_ui_args': [(self.metformin, 15)],
             'payments': [(self.cash_pm1, 3.0)]},
        ])

    def _incoming_purchase(self, product, qty):
        order = self.env['purchase.order'].create({
            'partner_id': self.vendor_b.id,
            'picking_type_id': self.warehouse.in_type_id.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_qty': qty})],
        })
        order.button_confirm()
        return order

    def _shortage(self, product, qty, **values):
        return self.env['pharmacy.shortage'].create({
            'product_id': product.id if product else False, 'quantity': qty,
            'warehouse_id': self.warehouse.id, **values})

    def _wizard(self, **values):
        return self.env['pharmacy.replenishment.wizard'].create({
            'warehouse_id': self.warehouse.id, 'period_days': 30, 'coverage_days': 15, **values})

    def _line(self, wizard, product):
        return wizard.line_ids.filtered(lambda line: line.product_id == product)

    def test_suggested_quantity_formula(self):
        Wizard = self.env['pharmacy.replenishment.wizard']
        # 1/día × 15 + 2 − 5 − 0 = 12 → múltiplo de 10 → 20
        self.assertEqual(Wizard._suggested_quantity(1.0, 15, 2, 5, 0, 10), 20)
        # Exacto: no sube al siguiente múltiplo.
        self.assertEqual(Wizard._suggested_quantity(1.0, 10, 0, 0, 0, 10), 10)
        # Cubierto por el stock y lo que llega.
        self.assertEqual(Wizard._suggested_quantity(1.0, 15, 0, 10, 5, 10), 0)
        self.assertEqual(Wizard._suggested_quantity(0.5, 15, 0, 0, 4, 1), 4)

    def test_compute_lines(self):
        self._sell_in_pos()
        self._incoming_purchase(self.metformin, 4)
        self._shortage(self.losartan, 2)
        self._shortage(self.insulin, 1)
        self._shortage(False, 3, description='Colirio lubricante 15 ml')
        # Otro local: no cuenta.
        other = self.env['stock.warehouse'].create({'name': 'Botica Norte', 'code': 'BNOR'})
        self._shortage(self.losartan, 50, warehouse_id=other.id)

        wizard = self._wizard()
        wizard.action_compute()
        self.assertEqual(len(wizard.line_ids), 3)
        losartan = self._line(wizard, self.losartan)
        self.assertRecordValues(losartan, [{
            'vendor_id': self.vendor_a.id, 'sold_qty': 30.0, 'avg_daily': 1.0,
            'shortage_qty': 2.0, 'stock_qty': 5.0, 'incoming_qty': 0.0, 'multiple': 10.0,
            # 1 × 15 + 2 − 5 = 12 → 2 cajas de 10
            'suggested_qty': 20.0,
        }])
        metformin = self._line(wizard, self.metformin)
        self.assertRecordValues(metformin, [{
            'vendor_id': self.vendor_b.id, 'sold_qty': 15.0, 'avg_daily': 0.5,
            'stock_qty': 0.0, 'incoming_qty': 4.0, 'multiple': 20.0,
            # 0,5 × 15 − 4 = 3,5 → 1 caja de 20
            'suggested_qty': 20.0,
        }])
        insulin = self._line(wizard, self.insulin)
        self.assertRecordValues(insulin, [{'sold_qty': 0.0, 'shortage_qty': 1.0,
                                           'multiple': 1.0, 'suggested_qty': 1.0}])

    def test_other_deliveries_count_but_not_pos_pickings(self):
        self._sell_in_pos()
        # Entrega de un pedido de venta (no viene del TPV) de 6 losartán.
        self.adjust_inventory([self.losartan], [11])
        customer = self.env['res.partner'].create({'name': 'Clínica San Juan'})
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'partner_id': customer.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'move_ids': [(0, 0, {'product_id': self.losartan.id, 'product_uom_qty': 6,
                                 'uom_id': self.units.id,
                                 'location_id': self.warehouse.lot_stock_id.id,
                                 'location_dest_id': self.env.ref('stock.stock_location_customers').id})],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = 6
        picking.button_validate()
        wizard = self._wizard()
        date_from = wizard._date_from()
        other = wizard._other_deliveries(date_from)
        # Las salidas del TPV no se cuentan dos veces.
        self.assertEqual(other[self.losartan], 6.0)
        self.assertNotIn(self.metformin, other)
        wizard.action_compute()
        self.assertEqual(self._line(wizard, self.losartan).sold_qty, 36.0)

    def test_create_purchase_by_vendor(self):
        self._sell_in_pos()
        shortage = self._shortage(self.losartan, 2)
        free_text = self._shortage(False, 1, description='Colirio lubricante 15 ml')
        wizard = self._wizard()
        wizard.action_compute()
        wizard.action_create_purchase()
        orders = self.env['purchase.order'].search([('origin', '=', 'Sugerido %s' % self.warehouse.name)])
        self.assertEqual(orders.partner_id, self.vendor_a | self.vendor_b)
        order_a = orders.filtered(lambda o: o.partner_id == self.vendor_a)
        self.assertEqual(order_a.state, 'draft')
        self.assertEqual(order_a.picking_type_id, self.warehouse.in_type_id)
        line = order_a.order_line.filtered(lambda l: l.product_id == self.losartan)
        # 20 unidades = 2 cajas de 10.
        self.assertEqual(line.uom_id, self.box_10)
        self.assertEqual(line.product_qty, 2.0)
        self.assertRecordValues(shortage, [{'state': 'ordered', 'purchase_order_id': order_a.id}])
        # El faltante sin producto sigue pendiente.
        self.assertEqual(free_text.state, 'pending')

    def test_create_purchase_requires_vendor(self):
        self._sell_in_pos()
        wizard = self._wizard()
        wizard.action_compute()
        self._line(wizard, self.losartan).vendor_id = False
        with self.assertRaises(UserError):
            wizard.action_create_purchase()

    def test_create_transfer(self):
        self._sell_in_pos()
        shortage = self._shortage(self.losartan, 2)
        central = self.env['stock.warehouse'].create({'name': 'Almacén central', 'code': 'CEN'})
        wizard = self._wizard(source_warehouse_id=central.id)
        wizard.action_compute()
        action = wizard.action_create_transfer()
        picking = self.env['stock.picking'].browse(action['res_id'])
        self.assertEqual(picking.location_id, central.lot_stock_id)
        self.assertEqual(picking.location_dest_id, self.warehouse.lot_stock_id)
        self.assertNotIn(picking.state, ('draft', 'cancel'))
        self.assertEqual(picking.move_ids.filtered(lambda m: m.product_id == self.losartan).product_uom_qty, 20)
        self.assertRecordValues(shortage, [{'state': 'ordered', 'picking_id': picking.id}])
        # Lo trasladado cuenta como «por llegar»: el siguiente cálculo ya no lo pide.
        again = self._wizard()
        again.action_compute()
        self.assertFalse(self._line(again, self.losartan))

    def test_transfer_needs_other_warehouse(self):
        wizard = self._wizard(source_warehouse_id=self.warehouse.id)
        self._shortage(self.insulin, 1)
        wizard.action_compute()
        with self.assertRaises(UserError):
            wizard.action_create_transfer()

    def test_shortage_constraints_and_states(self):
        with self.assertRaises(ValidationError):
            self._shortage(False, 1)
        with self.assertRaises(ValidationError):
            self._shortage(self.insulin, 0)
        shortage = self._shortage(self.insulin, 1)
        self.assertEqual(shortage.display_name, self.insulin.display_name)
        shortage.action_discard()
        self.assertEqual(shortage.state, 'discarded')
        shortage.action_reset()
        shortage.action_done()
        self.assertEqual(shortage.state, 'done')

    def test_create_from_pos(self):
        session = self.open_new_session()
        result = self.env['pharmacy.shortage'].create_from_pos({
            'session_id': session.id, 'product_id': self.insulin.id, 'quantity': 2,
            'reason': 'price'})
        shortage = self.env['pharmacy.shortage'].browse(result['id'])
        self.assertRecordValues(shortage, [{
            'warehouse_id': self.config.picking_type_id.warehouse_id.id, 'pos_session_id': session.id,
            'reason': 'price', 'quantity': 2.0, 'company_id': session.company_id.id}])
        # Motivo desconocido → «Otro».
        result = self.env['pharmacy.shortage'].create_from_pos({
            'session_id': session.id, 'description': 'Vitamina D3 gotas', 'reason': 'x'})
        self.assertEqual(self.env['pharmacy.shortage'].browse(result['id']).reason, 'other')

    def test_wizard_form(self):
        form = Form(self.env['pharmacy.replenishment.wizard'])
        self.assertEqual(form.warehouse_id, self.warehouse)
        self.assertEqual(form.period_days, 30)
        form.coverage_days = 0
        with self.assertRaises(ValidationError):
            form.save()
