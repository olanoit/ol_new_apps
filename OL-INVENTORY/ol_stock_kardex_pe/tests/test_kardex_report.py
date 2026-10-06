from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.sale.tests.common import TestSaleCommon
from odoo.exceptions import ValidationError
from odoo.tests import Form, new_test_user, tagged

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
        # Salida: 5 @ 15 = 75 (AVCO) — venta sin comprobante → guía (09),
        # como el TXT PLE de l10n_pe_reports_stock
        self.assertEqual(out.operation_type, '01')
        self.assertEqual(out.qty_out, 5)
        self.assertAlmostEqual(out.cost_total_out, 75.0, places=2)
        self.assertEqual(out.document_type_code, '09')
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

    def test_07_precarga_desde_contexto(self):
        """El botón «Ver Kardex» precarga producto/variante/categoría según el
        modelo activo del contexto."""
        Wizard = self.env['l10n_pe.kardex.report.wizard']
        # Variante de producto
        wiz = Wizard.with_context(
            active_model='product.product',
            active_ids=self.product_kdx.ids).create({})
        self.assertEqual(wiz.product_ids, self.product_kdx)
        # Plantilla → todas sus variantes
        tmpl = self.product_kdx.product_tmpl_id
        wiz = Wizard.with_context(
            active_model='product.template',
            active_ids=tmpl.ids).create({})
        self.assertEqual(wiz.product_ids, tmpl.product_variant_ids)
        # Categoría
        wiz = Wizard.with_context(
            active_model='product.category',
            active_ids=self.categ_avco.ids).create({})
        self.assertEqual(wiz.categ_ids, self.categ_avco)

    @freeze_time('2024-03-10')
    def test_08_periodo_por_mes(self):
        """El modo «Por mes» calcula date_from/date_to del mes seleccionado."""
        wizard = self._create_wizard(period_range='month', month='2', year='2024')
        wizard._sync_period_dates()
        self.assertEqual(str(wizard.date_from), '2024-02-01')
        self.assertEqual(str(wizard.date_to), '2024-02-29')  # bisiesto
        # El default es «Por mes» con el mes/año actuales congelados
        default = self.env['l10n_pe.kardex.report.wizard'].create({})
        self.assertEqual(default.period_range, 'month')
        self.assertEqual(default.month, '3')
        self.assertEqual(default.year, '2024')

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

    # ------------------------------------------------------------------
    # Correcciones de la auditoría (27/09/2026)
    # ------------------------------------------------------------------
    def _warehouse(self):
        return self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1)

    def test_09_recepcion_parcial_sin_pendiente(self):
        """La cantidad es la recibida (6), no la demanda (10) que conserva el
        movimiento cuando se valida sin crear pedido pendiente."""
        with freeze_time('2024-01-10'):
            purchase = self.env['purchase.order'].create({
                'partner_id': self.partner_a.id,
                'order_line': [Command.create({
                    'product_id': self.product_kdx.id,
                    'product_qty': 10,
                    'price_unit': 10.0,
                    'tax_ids': [Command.clear()],
                })],
            })
            purchase.button_confirm()
            picking = purchase.picking_ids
            picking.move_ids.write({'quantity': 6, 'picked': True})
            # Lo que hace «Sin pedido pendiente» del asistente de backorder
            picking.with_context(
                skip_backorder=True,
                picking_ids_not_to_backorder=picking.ids).button_validate()
        self.assertEqual(picking.state, 'done')
        block = self._blocks_for(self._create_wizard(), self.product_kdx)[0]
        self.assertAlmostEqual(block['total_line'].qty_in, 6)
        self.assertAlmostEqual(block['total_line'].balance_qty, 6)
        self.assertAlmostEqual(block['total_line'].balance_value, 60.0, places=2)
        product = self.product_kdx.with_context(to_date='2024-01-31 23:59:59')
        self.assertAlmostEqual(block['total_line'].balance_qty, product.qty_available)

    def test_10_corte_en_hora_de_lima(self):
        """31/01 a las 23:00 de Lima (01/02 04:00 UTC) es de enero."""
        with freeze_time('2024-02-01 04:00:00'):
            self._receive_purchase(10, 10.0)
        jan = self._blocks_for(self._create_wizard(), self.product_kdx)[0]
        move_row = jan['lines'][1]
        self.assertEqual(move_row.qty_in, 10)
        self.assertEqual(str(move_row.date), '2024-01-31')
        feb = self._blocks_for(self._create_wizard(
            date_from='2024-02-01', date_to='2024-02-29'), self.product_kdx)[0]
        self.assertEqual([r.line_type for r in feb['lines']], ['opening'])
        self.assertAlmostEqual(feb['lines'][0].balance_qty, 10)

    def test_11_ajuste_de_inventario_por_almacen(self):
        """Un ajuste de inventario (sin picking ni warehouse_id en el
        movimiento) sale con operación 28 y en el kardex de su almacén."""
        self._build_moves()
        warehouse = self._warehouse()
        with freeze_time('2024-01-25'):
            self.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': self.product_kdx.id,
                'location_id': warehouse.lot_stock_id.id,
                'inventory_quantity': 18,
            }).action_apply_inventory()
        consolidated = self._blocks_for(self._create_wizard(), self.product_kdx)[0]
        adjustment = consolidated['lines'][-1]
        self.assertEqual(adjustment.operation_type, '28')
        self.assertAlmostEqual(adjustment.qty_in, 3)
        self.assertAlmostEqual(consolidated['total_line'].balance_qty, 18)
        by_wh = self._blocks_for(
            self._create_wizard(warehouse_ids=[Command.set(warehouse.ids)]),
            self.product_kdx)
        self.assertEqual(len(by_wh), 1)
        self.assertAlmostEqual(by_wh[0]['total_line'].balance_qty, 18)
        self.assertEqual(by_wh[0]['lines'][-1].operation_type, '28')

    def test_12_traslado_entre_almacenes(self):
        """Salida 11 en el origen y entrada 21 en el destino, al costo
        promedio corriente; el consolidado no cambia."""
        self._build_moves()
        wh1 = self._warehouse()
        wh2 = self.env['stock.warehouse'].create({
            'name': 'Almacén Kardex 2', 'code': 'KDX2',
            'company_id': self.env.company.id,
        })
        with freeze_time('2024-01-20'):
            move = self.env['stock.move'].create({
                'product_id': self.product_kdx.id,
                'product_uom_qty': 4,
                'location_id': wh1.lot_stock_id.id,
                'location_dest_id': wh2.lot_stock_id.id,
            })
            move._action_confirm()
            move._action_assign()
            move.write({'quantity': 4, 'picked': True})
            move._action_done()
        self.assertEqual(move.state, 'done')
        blocks = {scope['warehouse']: b
                  for scope in self._create_wizard(group_by_warehouse=True)._get_report_data()
                  for b in scope['products'] if b['product'] == self.product_kdx}
        out = blocks[wh1]['lines'][-1]
        self.assertEqual((out.operation_type, out.qty_out), ('11', 4))
        self.assertAlmostEqual(out.cost_total_out, 60.0, places=2)
        self.assertAlmostEqual(blocks[wh1]['total_line'].balance_qty, 11)
        inc = blocks[wh2]['lines'][-1]
        self.assertEqual((inc.operation_type, inc.qty_in), ('21', 4))
        self.assertAlmostEqual(blocks[wh2]['total_line'].balance_value, 60.0, places=2)
        consolidated = self._blocks_for(self._create_wizard(), self.product_kdx)[0]
        self.assertEqual(len(consolidated['lines']), 4)  # apertura + 3 movimientos
        self.assertAlmostEqual(consolidated['total_line'].balance_qty, 15)

    def test_13_usuario_solo_inventario(self):
        """Tabla 10 se resuelve aunque el usuario no pueda leer ventas ni
        facturas (compute_sudo)."""
        self._build_moves()
        user = new_test_user(
            self.env, login='kardex_stock_only', groups='stock.group_stock_user',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        # Asistente creado por el propio usuario (los transitorios solo los
        # lee quien los crea)
        wizard = self.env['l10n_pe.kardex.report.wizard'].with_user(user).create({
            'company_id': self.env.company.id,
            'date_from': '2024-01-01', 'date_to': '2024-01-31',
        })
        block = self._blocks_for(wizard, self.product_kdx)[0]
        self.assertEqual(block['lines'][1].document_type_code, '01')
        self.assertEqual(block['lines'][1].folio, '00000123')

    def test_14_multicompania(self):
        other = self.env['res.company'].create({'name': 'Otra compañía Kardex'})
        report = self.env['l10n_pe.kardex.report'].sudo().create({
            'company_id': other.id,
            'date_from': '2024-01-01', 'date_to': '2024-01-31',
        })
        user = new_test_user(
            self.env, login='kardex_mc', groups='stock.group_stock_user',
            company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        Report = self.env['l10n_pe.kardex.report'].with_user(user)
        self.assertFalse(Report.search([('id', '=', report.id)]))
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.kardex.report.wizard'].with_user(user).create({
                'company_id': other.id,
                'date_from': '2024-01-01', 'date_to': '2024-01-31',
            })

    def test_15_error_en_segundo_plano(self):
        """Un error SQL deja el reporte en «Error» y el cursor utilizable."""
        # Con datos: sin ellos el reporte termina en «Sin datos» antes de generar.
        self._build_moves()
        report = self.env['l10n_pe.kardex.report'].create({
            'company_id': self.env.company.id,
            'date_from': '2024-01-01', 'date_to': '2024-01-31',
        })

        def broken(wizard):
            wizard.env.cr.execute("SELECT 1 / 0")

        with patch('odoo.addons.ol_stock_kardex_pe.reports.kardex_xlsx.build_kardex_xlsx',
                   side_effect=broken), self.assertLogs(level='ERROR'):
            self.env['l10n_pe.kardex.report']._cron_generate()
        self.assertEqual(report.state, 'error')
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone(), (1,))
