from datetime import date

from freezegun import freeze_time

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.sale.tests.common import TestSaleCommon
from odoo.exceptions import UserError
from odoo.tests import Form, tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestWarehouseCost(TestSaleCommon):
    """Costo promedio por almacén.

    Escenario (enero 2024):

    * 10/01 compra 10 @ 10 al almacén principal (100);
    * 11/01 compra 10 @ 20 al almacén Norte (200);
    * 12/01 traslado de 5 del principal al Norte: sale a 10 (50);
      Norte queda con 15 por 250 (16,6667);
    * 13/01 venta de 3 desde Norte: sale a 16,6667 (50); Norte 12 por 200.

    Por almacén: principal 5 por 50, Norte 12 por 200, compañía 17 por 250.
    Odoo, con un solo promedio (15), vende a 45 y valoriza 17 × 15 = 255.
    """

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'
        cls.company.l10n_pe_wh_cost = True
        cls.categ_avco = cls.env['product.category'].create({
            'name': 'AVCO por almacén',
            'property_cost_method': 'average',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Cemento',
            'default_code': 'CEM-42',
            'is_storable': True,
            'categ_id': cls.categ_avco.id,
            'l10n_pe_type_of_existence': '1',
            'list_price': 30.0,
            'taxes_id': [Command.clear()],
            'supplier_taxes_id': [Command.clear()],
        })
        cls.wh_main = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.wh_north = cls.env['stock.warehouse'].create({
            'name': 'Almacén Norte', 'code': 'NOR', 'company_id': cls.company.id,
        })
        cls.Cost = cls.env['l10n_pe.kardex.wh.cost']

    # ------------------------------------------------------------------
    # Movimientos
    # ------------------------------------------------------------------
    def _buy(self, warehouse, qty, price):
        purchase = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'picking_type_id': warehouse.in_type_id.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_qty': qty,
                'price_unit': price,
                'tax_ids': [Command.clear()],
            })],
        })
        purchase.button_confirm()
        picking = purchase.picking_ids
        picking.move_ids.write({'quantity': qty, 'picked': True})
        picking.button_validate()
        return picking.move_ids

    def _transfer(self, source, destination, qty):
        move = self.env['stock.move'].create({
            'product_id': self.product.id,
            'product_uom_qty': qty,
            'product_uom': self.product.uom_id.id,
            'location_id': source.lot_stock_id.id,
            'location_dest_id': destination.lot_stock_id.id,
        })
        move._action_confirm()
        move._action_assign()
        move.write({'quantity': qty, 'picked': True})
        move._action_done()
        return move

    def _sell(self, warehouse, qty):
        sale = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'warehouse_id': warehouse.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': qty,
                'price_unit': 30.0,
                'tax_ids': [Command.clear()],
            })],
        })
        sale.action_confirm()
        picking = sale.picking_ids
        picking.move_ids.write({'quantity': qty, 'picked': True})
        picking.button_validate()
        return picking

    def _scenario(self):
        with freeze_time('2024-01-10 15:00'):
            self.receipt_main = self._buy(self.wh_main, 10, 10.0)
        with freeze_time('2024-01-11 15:00'):
            self.receipt_north = self._buy(self.wh_north, 10, 20.0)
        with freeze_time('2024-01-12 15:00'):
            self.transfer = self._transfer(self.wh_main, self.wh_north, 5)
        with freeze_time('2024-01-13 15:00'):
            self.delivery = self._sell(self.wh_north, 3)
        self.company._l10n_pe_wh_cost_refresh()

    def _row(self, move, k=0):
        return self.Cost.search([('line_key', '=', move.id * 3 + k)])

    def _wh_balance(self, warehouse):
        row = self.Cost.search([('company_id', '=', self.company.id), ('warehouse_id', '=', warehouse.id)],
                               order='date desc, line_key desc', limit=1)
        return round(row.balance_qty_wh, 4), round(row.balance_value_wh, 2)

    # ------------------------------------------------------------------
    # Pruebas
    # ------------------------------------------------------------------
    def test_average_per_warehouse(self):
        self._scenario()
        transfer_out, transfer_in = self._row(self.transfer, 1), self._row(self.transfer, 2)
        self.assertAlmostEqual(transfer_out.value, -50.0)
        self.assertAlmostEqual(transfer_in.value, 50.0)
        self.assertEqual(transfer_in.warehouse_id, self.wh_north)
        sale_row = self._row(self.delivery.move_ids)
        self.assertAlmostEqual(sale_row.value, -50.0, places=2)
        # Odoo vendió al promedio de la compañía.
        self.assertAlmostEqual(self.delivery.move_ids.value, 45.0, places=2)
        self.assertEqual(self._wh_balance(self.wh_main), (5.0, 50.0))
        self.assertEqual(self._wh_balance(self.wh_north), (12.0, 200.0))
        self.assertAlmostEqual(sale_row.balance_qty, 17.0)
        self.assertAlmostEqual(sale_row.balance_value, 250.0, places=2)

    def test_kardex_view_uses_warehouse_cost(self):
        self._scenario()
        line = self.env['l10n_pe.kardex.line'].browse(self.delivery.move_ids.id * 3)
        self.assertAlmostEqual(line.cost_total_out, 50.0, places=2)
        self.assertAlmostEqual(line.balance_value_wh, 200.0, places=2)
        self.assertAlmostEqual(line.balance_value, 250.0, places=2)
        line_in = self.env['l10n_pe.kardex.line'].browse(self.transfer.id * 3 + 2)
        self.assertAlmostEqual(line_in.cost_total_in, 50.0, places=2)

    def test_customer_return_comes_back_at_its_cost(self):
        self._scenario()
        with freeze_time('2024-01-14 15:00'):
            wizard = Form(self.env['stock.return.picking'].with_context(
                active_id=self.delivery.id, active_model='stock.picking')).save()
            wizard.product_return_moves.quantity = 1
            return_picking = self.env['stock.picking'].browse(wizard._create_return().id)
            return_picking.move_ids.write({'quantity': 1, 'picked': True})
            return_picking.button_validate()
        self.company._l10n_pe_wh_cost_refresh()
        row = self._row(return_picking.move_ids)
        self.assertAlmostEqual(row.value, 50.0 / 3, places=2)
        self.assertEqual(self._wh_balance(self.wh_north), (13.0, round(200.0 + 50.0 / 3, 2)))

    def test_stock_value_and_monthly_close(self):
        self._scenario()
        valuation_account = self.product.categ_id.property_stock_valuation_account_id \
            or self.company.account_stock_valuation_id
        with freeze_time('2024-02-05'):
            values = self.company.stock_value(at_date=date(2024, 1, 31))
            self.assertAlmostEqual(values[valuation_account], 250.0, places=2)
            close = self.env['l10n_pe.stock.cost.close'].create({'date': date(2024, 1, 31)})
            close.action_close()
        self.assertEqual(close.state, 'closed')
        self.assertEqual(self.company.l10n_pe_stock_lock_date, date(2024, 1, 31))
        self.assertTrue(close.account_move_id)
        accounting = self.company.stock_accounting_value(at_date=date(2024, 1, 31))
        self.assertAlmostEqual(accounting[valuation_account], 250.0, places=2)
        # El cierre de Odoo lleva la diferencia a la cuenta de variación (69).
        variation = valuation_account.account_stock_variation_id
        self.assertIn(variation, close.account_move_id.line_ids.account_id)

        # Periodo cerrado: ni valor ni revalorización de enero.
        with self.assertRaises(UserError):
            self.receipt_main.value = 150.0
        with self.assertRaises(UserError):
            self.env['product.value'].create({'move_id': self.receipt_main.id, 'value': 150.0})
        wizard = self.env['l10n_pe.wh.cost.recompute.wizard'].create({'date_from': date(2024, 1, 15)})
        with self.assertRaises(UserError):
            wizard.action_recompute()
        # Ni un segundo cierre anterior al vigente.
        with self.assertRaises(UserError):
            self.env['l10n_pe.stock.cost.close'].create({'date': date(2024, 1, 20)}).action_close()

        close.action_reopen()
        self.assertEqual(close.state, 'reopened')
        self.assertFalse(self.company.l10n_pe_stock_lock_date)
        self.assertEqual(close.account_move_id.state, 'cancel')

    def test_revaluation_after_value_change(self):
        self._scenario()
        # Factura tardía: la compra del principal costaba 15, no 10.
        self.env['product.value'].create({'move_id': self.receipt_main.id, 'value': 150.0})
        self.assertTrue(self.company.l10n_pe_wh_cost_dirty_date)
        self.company._l10n_pe_wh_cost_refresh()
        self.assertFalse(self.company.l10n_pe_wh_cost_dirty_date)
        self.assertAlmostEqual(self._row(self.transfer, 1).value, -75.0, places=2)
        # Norte: 10 @ 20 + 5 @ 15 = 275 / 15; vende 3 → 220 por 12.
        self.assertEqual(self._wh_balance(self.wh_north), (12.0, 220.0))
        self.assertEqual(self._wh_balance(self.wh_main), (5.0, 75.0))

    def test_revaluation_wizard(self):
        self._scenario()
        before = self.Cost.search_count([('company_id', '=', self.company.id)])
        wizard = self.env['l10n_pe.wh.cost.recompute.wizard'].create({'date_from': date(2024, 1, 12)})
        wizard.action_recompute()
        self.assertEqual(self.Cost.search_count([('company_id', '=', self.company.id)]), before)
        self.assertEqual(self._wh_balance(self.wh_north), (12.0, 200.0))

    def test_disabled_keeps_odoo_cost(self):
        self.company.l10n_pe_wh_cost = False
        self._scenario()
        self.assertFalse(self.Cost.search_count([('company_id', '=', self.company.id)]))
        line = self.env['l10n_pe.kardex.line'].browse(self.delivery.move_ids.id * 3)
        self.assertAlmostEqual(line.cost_total_out, 45.0, places=2)

    def _ple_rows(self, date_from, date_to):
        wizard = self.env['l10n_pe.stock.ple.wizard'].create({'date_from': date_from, 'date_to': date_to})
        content = wizard._get_ple_report_content('1301')
        i_value_in = wizard._l10n_pe_kardex_columns()[3] + 7
        rows = [line.split('|') for line in content.split('\n') if line]
        product_rows = [r for r in rows if self.product.name in r]
        self.assertTrue(product_rows, content)
        return product_rows, i_value_in

    def test_ple_131_uses_warehouse_cost(self):
        self._scenario()
        rows, i_value_in = self._ple_rows('2024-01-01', '2024-01-31')
        sale = next(r for r in rows if r[1] == str(self.delivery.move_ids.id).zfill(6))
        self.assertEqual(sale[i_value_in + 3], '-50.00')
        self.assertEqual(sale[i_value_in + 2], '16.67')
        # Saldo final: 17 por 250 (Odoo: 255).
        self.assertEqual(rows[-1][i_value_in + 4], '17.00')
        self.assertEqual(rows[-1][i_value_in + 6], '250.00')

        # Febrero abre con el saldo por almacén.
        with freeze_time('2024-02-10 15:00'):
            self._sell(self.wh_main, 1)
        rows, i_value_in = self._ple_rows('2024-02-01', '2024-02-29')
        opening = next(r for r in rows if r[2] == 'A1')
        self.assertEqual(opening[i_value_in + 4], '17.00')
        self.assertEqual(opening[i_value_in + 6], '250.00')
        # Sale del principal a su promedio (10), no al de la compañía.
        self.assertEqual(rows[-1][i_value_in + 6], '240.00')
