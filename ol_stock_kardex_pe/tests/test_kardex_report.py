from freezegun import freeze_time

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.sale.tests.common import TestSaleCommon
from odoo.tests import Form, tagged

from ..reports.kardex_xlsx import build_kardex_xlsx


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestKardexReport(TestSaleCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].country_id = cls.env.ref('base.pe')
        cls.company_data['company'].vat = '20512528458'
        cls.partner_a.write({
            'country_id': cls.env.ref('base.pe').id,
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.categ_avco = cls.env['product.category'].create({
            'name': 'AVCO Kardex',
            'property_cost_method': 'average',
        })
        cls.product_kdx = cls.env['product.product'].create({
            'name': 'Producto Kardex',
            'default_code': 'KDX-001',
            'is_storable': True,
            'categ_id': cls.categ_avco.id,
            'l10n_pe_type_of_existence': '1',
            'list_price': 100.0,
            'taxes_id': [Command.clear()],
            'supplier_taxes_id': [Command.clear()],
        })

    @classmethod
    def _receive_purchase(cls, qty, price):
        purchase = cls.env['purchase.order'].create({
            'partner_id': cls.partner_a.id,
            'order_line': [Command.create({
                'name': cls.product_kdx.name,
                'product_id': cls.product_kdx.id,
                'product_qty': qty,
                'product_uom_id': cls.product_kdx.uom_id.id,
                'price_unit': price,
                'tax_ids': [Command.clear()],
            })],
        })
        purchase.button_confirm()
        picking = purchase.picking_ids
        picking.move_line_ids.write({'quantity': qty, 'picked': True})
        picking.button_validate()
        return purchase

    @classmethod
    def _deliver_sale(cls, qty):
        sale = cls.env['sale.order'].create({
            'partner_id': cls.partner_a.id,
            'order_line': [Command.create({
                'name': cls.product_kdx.name,
                'product_id': cls.product_kdx.id,
                'product_uom_qty': qty,
                'price_unit': 100.0,
                'tax_ids': [Command.clear()],
            })],
        })
        sale.action_confirm()
        picking = sale.picking_ids
        picking.move_ids.write({'quantity': qty, 'picked': True})
        picking.button_validate()
        return sale

    @freeze_time('2024-01-15')
    def _build_moves(self):
        """10 @ 10.00 + 10 @ 20.00 (compras) y salida de 5 (venta).
        AVCO esperado: saldo 15 uds @ 15.00 = 225.00."""
        purchase = self._receive_purchase(10, 10.0)
        self._receive_purchase(10, 20.0)
        self._deliver_sale(5)

        # Factura de proveedor de la primera compra, para la Tabla 10
        move_form = Form(self.env['account.move'].with_context(
            default_move_type='in_invoice'))
        move_form.partner_id = self.partner_a
        move_form.purchase_vendor_bill_id = self.env['purchase.bill.union'].browse(
            -purchase.id)
        move_form.invoice_date = '2024-01-15'
        move_form.l10n_latam_document_type_id = self.env.ref('l10n_pe.document_type01')
        move_form.l10n_latam_document_number = 'F001-00000123'
        bill = move_form.save()
        bill.action_post()

    def _create_wizard(self, **values):
        defaults = {
            'company_id': self.env.company.id,
            'date_from': '2024-01-01',
            'date_to': '2024-01-31',
            'report_type': '1301',
        }
        defaults.update(values)
        return self.env['l10n_pe.kardex.report.wizard'].create(defaults)

    def _blocks_for(self, wizard, product):
        """Devuelve la lista de bloques (uno por ámbito) del producto."""
        blocks = []
        for scope in wizard._get_report_data():
            for block in scope['products']:
                if block['product'] == product:
                    blocks.append(block)
        return blocks

    def test_01_kardex_valorizado_avco(self):
        self._build_moves()
        wizard = self._create_wizard()
        block = self._blocks_for(wizard, self.product_kdx)[0]
        rows = block['lines']
        total = block['total_line']
        self.assertEqual([r.line_type for r in rows],
                         ['opening', 'move', 'move', 'move'])

        opening, in1, in2, out = rows
        # Saldo inicial cero
        self.assertEqual(opening.operation_type, '16')
        self.assertEqual(opening.balance_qty, 0)
        # Compra 1: 10 @ 10 — comprobante 01 F001-00000123
        self.assertEqual(in1.operation_type, '02')
        self.assertEqual(in1.qty_in, 10)
        self.assertAlmostEqual(in1.cost_unit_in, 10.0, places=2)
        self.assertAlmostEqual(in1.cost_total_in, 100.0, places=2)
        self.assertEqual(in1.document_type_code, '01')
        self.assertEqual(in1.serie, 'F001')
        self.assertEqual(in1.folio, '00000123')
        # Compra 2: 10 @ 20 → saldo 20 @ 15
        self.assertAlmostEqual(in2.cost_total_in, 200.0, places=2)
        self.assertAlmostEqual(in2.balance_qty, 20)
        self.assertAlmostEqual(in2.balance_unit_cost, 15.0, places=2)
        # Salida: 5 @ 15 = 75 (AVCO) — venta sin comprobante → doc interno
        self.assertEqual(out.operation_type, '01')
        self.assertEqual(out.qty_out, 5)
        self.assertAlmostEqual(out.cost_total_out, 75.0, places=2)
        self.assertEqual(out.document_type_code, '00')
        # Totales y cuadratura contra la valorización nativa
        self.assertAlmostEqual(total.qty_in, 20)
        self.assertAlmostEqual(total.cost_total_in, 300.0, places=2)
        self.assertAlmostEqual(total.qty_out, 5)
        self.assertAlmostEqual(total.balance_qty, 15)
        self.assertAlmostEqual(total.balance_value, 225.0, places=2)
        product = self.product_kdx.with_context(to_date='2024-01-31 23:59:59')
        self.assertAlmostEqual(total.balance_qty, product.qty_available, places=2)
        self.assertAlmostEqual(total.balance_value, product.total_value, places=2)

    def test_02_saldo_inicial_periodo_siguiente(self):
        self._build_moves()
        wizard = self._create_wizard(date_from='2024-02-01', date_to='2024-02-29')
        block = self._blocks_for(wizard, self.product_kdx)[0]
        rows = block['lines']
        self.assertEqual([r.line_type for r in rows], ['opening'])
        opening = rows[0]
        self.assertAlmostEqual(opening.balance_qty, 15)
        self.assertAlmostEqual(opening.balance_value, 225.0, places=2)
        self.assertAlmostEqual(opening.balance_unit_cost, 15.0, places=2)

    def test_03_kardex_fisico_por_almacen(self):
        self._build_moves()
        wizard = self._create_wizard(report_type='1201', group_by_warehouse=True)
        blocks = self._blocks_for(wizard, self.product_kdx)
        self.assertTrue(blocks)
        # Saldo final sumado sobre almacenes = 15
        self.assertAlmostEqual(
            sum(b['total_line'].balance_qty for b in blocks), 15)
        # Físico: sin costos
        for b in blocks:
            self.assertFalse(any(r.cost_total_in for r in b['lines']))

    def test_04_vista_sql_sin_poblar(self):
        """La vista SQL entrega el saldo corrido sin poblar registros."""
        self._build_moves()
        Line = self.env['l10n_pe.kardex.line']
        lines = Line.search([('product_id', '=', self.product_kdx.id)], order='date, id')
        # 3 movimientos valorados (2 compras + 1 venta)
        self.assertEqual(len(lines), 3)
        # Saldo corrido consolidado por window function
        self.assertAlmostEqual(lines[0].balance_qty, 10)
        self.assertAlmostEqual(lines[1].balance_qty, 20)
        self.assertAlmostEqual(lines[1].balance_unit_cost, 15.0, places=2)
        self.assertAlmostEqual(lines[2].balance_qty, 15)
        self.assertAlmostEqual(lines[2].balance_value, 225.0, places=2)

    def test_05_renderizadores(self):
        self._build_moves()
        wizard = self._create_wizard()
        content = build_kardex_xlsx(wizard)
        self.assertGreater(len(content), 1000)
        self.assertEqual(content[:2], b'PK')  # firma ZIP/XLSX
        html = self.env['ir.actions.report']._render_qweb_html(
            'ol_stock_kardex_pe.report_kardex', wizard.ids)[0]
        self.assertIn(b'FORMATO 13.1', html)
        self.assertIn(b'KDX-001', html)

    def test_06_generacion_segundo_plano(self):
        self._build_moves()
        report = self.env['l10n_pe.kardex.report'].create({
            'company_id': self.env.company.id,
            'date_from': '2024-01-01', 'date_to': '2024-01-31',
            'report_type': '1301', 'file_format': 'xlsx',
        })
        self.env['l10n_pe.kardex.report']._cron_generate()
        self.assertEqual(report.state, 'done')
        self.assertTrue(report.output_file)
        self.assertTrue(report.output_filename.endswith('.xlsx'))
