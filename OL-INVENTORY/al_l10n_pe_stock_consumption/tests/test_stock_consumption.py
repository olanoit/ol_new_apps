# -*- coding: utf-8 -*-
import ast

from odoo.tests import tagged

from odoo.addons.stock_account.tests.common import TestStockValuationCommon


@tagged('post_install', '-at_install')
class TestStockConsumption(TestStockValuationCommon):
    # Las pruebas preparan también la configuración contable y de inventario.
    _test_user_groups = (
        'stock.group_stock_manager',
        'account.group_account_manager',
        'analytic.group_analytic_accounting',
        'base.group_system',
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['account.account']
        cls.account_location = Account.create({'code': '659901', 'name': 'Consumo general', 'account_type': 'expense'})
        cls.account_material = Account.create({'code': '613101', 'name': 'Consumo de materiales', 'account_type': 'expense'})
        plan = cls.env['account.analytic.plan'].create({'name': 'Centros consumo'})
        Analytic = cls.env['account.analytic.account']
        cls.center_a = Analytic.create({'name': 'Planta', 'plan_id': plan.id, 'company_id': cls.company.id})
        cls.center_b = Analytic.create({'name': 'Ventas', 'plan_id': plan.id, 'company_id': cls.company.id})
        cls.location = cls.env['stock.location'].create({
            'name': 'Consumo interno',
            'usage': 'inventory',
            'company_id': cls.company.id,
            'valuation_account_id': cls.account_location.id,
            'l10n_pe_is_consumption': True,
            'analytic_distribution': {str(cls.center_a.id): 100.0},
        })

    def _product(self, category):
        return self.env['product.product'].create({
            'name': 'Material', 'is_storable': True, 'categ_id': category.id})

    def _expense(self, account_move, account=None):
        stock_account = self.account_stock_valuation
        return account_move.sudo().line_ids.filtered(
            lambda line: line.account_id == account if account else line.account_id != stock_account)

    def _analytic_total(self, center):
        column = center.plan_id._column_name()
        return sum(self.env['account.analytic.line'].search([(column, '=', center.id)]).mapped('amount'))

    def _consume(self, product, quantity, distribution):
        """Salida a consumo con el centro de costo en la línea."""
        move = self.env['stock.move'].create({
            'product_id': product.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.location.id,
            'uom_id': self.uom.id,
            'product_uom_qty': quantity,
            'picking_type_id': self.picking_type_out.id,
            'analytic_distribution': distribution,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = quantity
        move.picked = True
        move._action_done()
        return move

    def test_real_time_uses_category_account_and_location_center(self):
        self.category_avco_auto.l10n_pe_consumption_account_id = self.account_material
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        out = self._make_out_move(product, 4, location_dest_id=self.location.id)
        self.assertEqual(out.value, -20.0)  # En Odoo 20 la salida es negativa.
        expense = self._expense(out.account_move_id, self.account_material)
        self.assertEqual(expense.debit, 20.0)
        self.assertEqual(expense.analytic_distribution, {str(self.center_a.id): 100.0})
        self.assertEqual(out.account_move_id.state, 'posted')
        self.assertEqual(self._analytic_total(self.center_a), -20.0)

    def test_report_lists_done_consumption_only(self):
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        out = self._make_out_move(product, 1, location_dest_id=self.location.id)
        sale = self._make_out_move(product, 1)
        action = self.env.ref('al_l10n_pe_stock_consumption.action_stock_move_consumption')
        moves = self.env['stock.move'].search(ast.literal_eval(action.domain))
        self.assertIn(out, moves)
        self.assertNotIn(sale, moves)

    def test_real_time_without_category_account_uses_location(self):
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        out = self._make_out_move(product, 1, location_dest_id=self.location.id)
        self.assertEqual(self._expense(out.account_move_id, self.account_location).debit, 5.0)

    def test_line_center_wins_over_location(self):
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        out = self._consume(product, 2, {str(self.center_b.id): 100.0})
        self.assertEqual(self._expense(out.account_move_id).analytic_distribution,
                         {str(self.center_b.id): 100.0})

    def test_moves_with_different_center_do_not_merge(self):
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.location.id,
        })
        moves = self.env['stock.move'].create([{
            'picking_id': picking.id,
            'product_id': product.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.location.id,
            'uom_id': self.uom.id,
            'product_uom_qty': quantity,
            'picking_type_id': self.picking_type_out.id,
            'analytic_distribution': {str(center.id): 100.0},
        } for quantity, center in ((1, self.center_a), (2, self.center_b), (3, self.center_b))])
        picking.action_confirm()
        self.assertEqual(len(moves.exists()), 2, 'Solo se fusionan las líneas del mismo centro')

    def test_return_reverses_the_entry(self):
        self.category_avco_auto.l10n_pe_consumption_account_id = self.account_material
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        self._make_out_move(product, 4, location_dest_id=self.location.id)
        back = self._make_in_move(product, 1, 5, location_id=self.location.id)
        line = self._expense(back.account_move_id, self.account_material)
        self.assertEqual(line.credit, 5.0)
        self.assertEqual(self._analytic_total(self.center_a), -15.0)

    def test_unmarked_inventory_location_stays_native(self):
        """Merma y ajuste de inventario no cambian: conservan su cuenta."""
        self.category_avco_auto.l10n_pe_consumption_account_id = self.account_material
        self.location.l10n_pe_is_consumption = False
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        out = self._make_out_move(product, 1, location_dest_id=self.location.id)
        self.assertEqual(self._expense(out.account_move_id, self.account_location).debit, 5.0)
        self.assertFalse(self._expense(out.account_move_id).analytic_distribution)

    def test_periodic_closing_groups_by_account_and_center(self):
        self.category_avco.l10n_pe_consumption_account_id = self.account_material
        product = self._product(self.category_avco)
        self._make_in_move(product, 10, 5)
        first = self._make_out_move(product, 3, location_dest_id=self.location.id)
        self._consume(product, 2, {str(self.center_b.id): 100.0})
        self.assertFalse(first.account_move_id, 'La valorización periódica no asienta por movimiento')
        closing = self._close()
        lines = self._expense(closing, self.account_material)
        self.assertEqual(
            sorted((line.debit, tuple(line.analytic_distribution)) for line in lines),
            [(10.0, (str(self.center_b.id),)), (15.0, (str(self.center_a.id),))])
        # La existencia queda al valor del inventario (5 unidades a 5).
        stock_balance = sum(closing.line_ids.filtered(
            lambda line: line.account_id == self.account_stock_valuation).mapped('balance'))
        self.assertEqual(stock_balance, 25.0)
        self.assertEqual(self._analytic_total(self.center_a), -15.0)

    def test_periodic_closing_nets_returns(self):
        product = self._product(self.category_avco)
        self._make_in_move(product, 10, 5)
        self._make_out_move(product, 4, location_dest_id=self.location.id)
        self._make_in_move(product, 1, 5, location_id=self.location.id)
        closing = self._close()
        self.assertEqual(self._expense(closing, self.account_location).debit, 15.0)

    def test_move_with_own_analytic_is_not_counted_twice(self):
        """Si el movimiento ya crea su apunte, el asiento no lleva analítica."""
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        distribution = {str(self.center_b.id): 100.0}
        self.patch(type(self.env['stock.move']), '_get_analytic_distribution', lambda move: distribution)
        out = self._make_out_move(product, 2, location_dest_id=self.location.id)
        self.assertFalse(self._expense(out.account_move_id).analytic_distribution)
        self.assertFalse(out.account_move_id.line_ids.analytic_line_ids)
        # El cargo al centro queda solo en el apunte que prepara el movimiento.
        self.assertEqual([vals['amount'] for vals in out._prepare_analytic_lines()], [-10.0])

    def test_destination_entry_follows_the_center(self):
        """Consumo → destino 9/79 por centro, con el costo cargado una vez."""
        if 'l10n_pe_destination_account_id' not in self.env['account.analytic.account']._fields:
            self.skipTest('Requiere al_account_destinations')
        Account = self.env['account.account']
        destination = Account.create({'code': '921901', 'name': 'Costo de planta', 'account_type': 'expense'})
        load = Account.create({'code': '791901', 'name': 'Cargas imputables', 'account_type': 'expense'})
        self.company.account_fiscal_country_id = self.env.ref('base.pe')
        self.company.write({
            'l10n_pe_dest_type': '6a9',
            'l10n_pe_destination_load_account_id': load.id,
            'l10n_pe_destination_journal_id': self.env['account.journal'].create({
                'name': 'Destinos', 'code': 'DSTC', 'type': 'general', 'company_id': self.company.id}).id,
        })
        self.center_a.l10n_pe_destination_account_id = destination
        self.category_avco_auto.l10n_pe_consumption_account_id = self.account_material
        product = self._product(self.category_avco_auto)
        self._make_in_move(product, 10, 5)
        out = self._make_out_move(product, 4, location_dest_id=self.location.id)
        entry = out.account_move_id.l10n_pe_destiny_move_id
        self.assertTrue(entry, 'El consumo debe generar su asiento de destino')
        self.assertEqual(entry.line_ids.filtered(lambda line: line.account_id == destination).debit, 20.0)
        self.assertEqual(entry.line_ids.filtered(lambda line: line.account_id == load).credit, 20.0)
        self.assertEqual(self._analytic_total(self.center_a), -20.0)

    def test_consumption_location_requires_account_and_type(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.location.valuation_account_id = False
        with self.assertRaises(ValidationError):
            self.location.usage = 'internal'
