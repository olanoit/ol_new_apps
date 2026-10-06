from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from .test_kardex_report import TestKardexReport


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestKardexDocument(TestKardexReport):
    """Sin datos no se genera nada; documento del kardex por movimiento."""

    # ------------------------------------------------------------------
    # Sin datos: ni archivo ni vista, y un mensaje
    # ------------------------------------------------------------------

    def test_20_sin_datos_no_descarga(self):
        wizard = self._create_wizard(date_from='2023-01-01', date_to='2023-01-31')
        for action in (wizard.action_export_xlsx, wizard.action_print_pdf,
                       wizard.action_view, wizard.action_generate_background):
            with self.assertRaisesRegex(UserError, 'No hay datos de kardex'):
                action()
        self.assertFalse(wizard.report_data, 'no se guarda un archivo vacío')
        self.assertFalse(self.env['l10n_pe.kardex.report'].search([
            ('date_from', '=', '2023-01-01')]), 'no se encola nada')

    def test_21_pdf_directo_sin_datos(self):
        wizard = self._create_wizard(date_from='2023-01-01', date_to='2023-01-31')
        with self.assertRaisesRegex(UserError, 'No hay datos de kardex'):
            self.env['ir.actions.report']._render_qweb_pdf('ol_stock_kardex_pe.report_kardex', wizard.ids)

    def test_22_segundo_plano_sin_datos(self):
        report = self.env['l10n_pe.kardex.report'].create({
            'company_id': self.env.company.id,
            'date_from': '2023-01-01', 'date_to': '2023-01-31',
        })
        self.env['l10n_pe.kardex.report']._cron_generate()
        self.assertEqual(report.state, 'empty')
        self.assertFalse(report.output_file)
        self.assertIn('No hay datos de kardex', report.error_message)

    def test_23_saldo_inicial_cuenta_como_dato(self):
        """Sin movimientos en febrero pero con saldo de enero: hay kardex si se piden
        los productos sin movimientos, y no lo hay si no."""
        self._build_moves()
        with_opening = self._create_wizard(date_from='2024-02-01', date_to='2024-02-29',
                                           include_no_movement=True)
        self.assertTrue(with_opening._has_data())
        with_opening.action_export_xlsx()
        self.assertTrue(with_opening.report_data)
        without = self._create_wizard(date_from='2024-02-01', date_to='2024-02-29',
                                      include_no_movement=False)
        with self.assertRaisesRegex(UserError, 'No hay datos de kardex'):
            without.action_export_xlsx()

    def test_24_filtro_sin_resultados(self):
        self._build_moves()
        other = self.env['product.product'].create({'name': 'Sin movimientos', 'is_storable': True})
        wizard = self._create_wizard(product_ids=[(6, 0, other.ids)])
        with self.assertRaisesRegex(UserError, 'No hay datos de kardex'):
            wizard.action_export_xlsx()

    # ------------------------------------------------------------------
    # Documento por movimiento
    # ------------------------------------------------------------------

    def _receipt_moves(self, purchase):
        return purchase.picking_ids.move_ids.filtered(lambda m: m.state == 'done')

    def test_30_factura_de_proveedor_llena_la_recepcion(self):
        self._build_moves()
        bill = self.env['account.move'].search([('move_type', '=', 'in_invoice')]).filtered(
            lambda m: m.l10n_latam_document_number == 'F001-00000123')
        move = bill.invoice_line_ids.purchase_line_id.move_ids
        self.assertEqual(
            (move.l10n_pe_kardex_doc_type, move.l10n_pe_kardex_serie, move.l10n_pe_kardex_number),
            ('01', 'F001', '00000123'))
        self.assertEqual(move.l10n_pe_kardex_invoice_id, bill)
        self.assertFalse(move.l10n_pe_kardex_doc_manual)
        line = self.env['l10n_pe.kardex.line'].search([('move_id', '=', move.id)])
        self.assertEqual((line.document_type_code, line.serie, line.folio), ('01', 'F001', '00000123'))

    def _bill(self, purchase, number, date='2024-01-20'):
        move_form = Form(self.env['account.move'].with_context(default_move_type='in_invoice'))
        move_form.partner_id = self.partner_a
        move_form.purchase_vendor_bill_id = self.env['purchase.bill.union'].browse(-purchase.id)
        move_form.invoice_date = date
        move_form.l10n_latam_document_type_id = self.env.ref('l10n_pe.document_type01')
        move_form.l10n_latam_document_number = number
        bill = move_form.save()
        bill.action_post()
        return bill

    @freeze_time('2024-01-20')
    def test_31_recepcion_en_partes_y_dos_facturas(self):
        """Primera recepción con la primera factura y la segunda con la segunda,
        no las dos con la primera."""
        purchase = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.product_kdx.id, 'product_qty': 10, 'price_unit': 10.0,
                'tax_ids': [Command.clear()]})],
        })
        purchase.button_confirm()
        first = purchase.picking_ids
        first.move_ids.write({'quantity': 6, 'picked': True})
        first.with_context(cancel_backorder=False)._action_done()
        bill_1 = self._bill(purchase, 'F001-00000201')
        second = purchase.picking_ids - first
        second.move_ids.write({'quantity': 4, 'picked': True})
        second.button_validate()
        bill_2 = self._bill(purchase, 'F001-00000202')
        self.assertEqual(first.move_ids.l10n_pe_kardex_invoice_id, bill_1)
        self.assertEqual(first.move_ids.l10n_pe_kardex_number, '00000201')
        self.assertEqual(second.move_ids.l10n_pe_kardex_invoice_id, bill_2)
        self.assertEqual(second.move_ids.l10n_pe_kardex_number, '00000202')

    @freeze_time('2024-01-20')
    def test_32_factura_antes_que_la_recepcion(self):
        purchase = self.env['purchase.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.product_kdx.id, 'product_qty': 3, 'price_unit': 10.0,
                'tax_ids': [Command.clear()]})],
        })
        purchase.button_confirm()
        purchase.order_line.product_id.purchase_method = 'purchase'
        self._bill(purchase, 'F002-00000077')
        picking = purchase.picking_ids
        self.assertFalse(picking.move_ids.l10n_pe_kardex_doc_type, 'aún no está hecho')
        picking.move_ids.write({'quantity': 3, 'picked': True})
        picking.button_validate()
        self.assertEqual(picking.move_ids.l10n_pe_kardex_number, '00000077')

    @freeze_time('2024-01-20')
    def test_33_devolucion_al_proveedor_toma_la_nota_de_credito(self):
        purchase = self._receive_purchase(5, 10.0)
        bill = self._bill(purchase, 'F001-00000301')
        receipt = purchase.picking_ids
        wizard = Form(self.env['stock.return.picking'].with_context(
            active_id=receipt.id, active_model='stock.picking')).save()
        wizard.product_return_moves.quantity = 2
        returned = self.env['stock.picking'].browse(wizard.action_create_returns()['res_id'])
        returned.move_ids.write({'quantity': 2, 'picked': True})
        returned.button_validate()
        refund_form = Form(self.env['account.move'].with_context(default_move_type='in_refund'))
        refund_form.partner_id = self.partner_a
        refund_form.invoice_date = '2024-01-20'
        refund_form.l10n_latam_document_type_id = self.env.ref('l10n_pe.document_type07')
        refund_form.l10n_latam_document_number = 'FC01-00000009'
        with refund_form.invoice_line_ids.new() as line:
            line.product_id = self.product_kdx
            line.quantity = 2
            line.price_unit = 10.0
            line.tax_ids.clear()
        refund = refund_form.save()
        refund.invoice_line_ids.purchase_line_id = purchase.order_line
        refund.action_post()
        self.assertEqual(receipt.move_ids.l10n_pe_kardex_invoice_id, bill)
        self.assertEqual(returned.move_ids.l10n_pe_kardex_invoice_id, refund)
        self.assertEqual(returned.move_ids.l10n_pe_kardex_doc_type, '07')

    def test_34_correccion_manual_protegida(self):
        self._build_moves()
        bill = self.env['account.move'].search([('move_type', '=', 'in_invoice')]).filtered(
            lambda m: m.l10n_latam_document_number == 'F001-00000123')
        move = bill.invoice_line_ids.purchase_line_id.move_ids
        move.write({'l10n_pe_kardex_doc_type': '09', 'l10n_pe_kardex_serie': 'T001',
                    'l10n_pe_kardex_number': '55'})
        self.assertTrue(move.l10n_pe_kardex_doc_manual)
        move.action_l10n_pe_kardex_refresh()
        self.assertEqual(move.l10n_pe_kardex_number, '55', 'lo manual no se recalcula')
        line = self.env['l10n_pe.kardex.line'].search([('move_id', '=', move.id)])
        self.assertEqual((line.document_type_code, line.serie, line.folio), ('09', 'T001', '55'))
        move.action_l10n_pe_kardex_reset_manual()
        self.assertFalse(move.l10n_pe_kardex_doc_manual)
        self.assertEqual(move.l10n_pe_kardex_number, '00000123')

    def test_35_formato_sunat(self):
        self._build_moves()
        move = self.env['stock.move'].search([('product_id', '=', self.product_kdx.id),
                                              ('state', '=', 'done')], limit=1)
        for vals in ({'l10n_pe_kardex_doc_type': '1', 'l10n_pe_kardex_number': '5'},
                     {'l10n_pe_kardex_doc_type': '01', 'l10n_pe_kardex_serie': 'F-01',
                      'l10n_pe_kardex_number': '5'},
                     {'l10n_pe_kardex_doc_type': '01', 'l10n_pe_kardex_number': '0'},
                     {'l10n_pe_kardex_doc_type': '01', 'l10n_pe_kardex_number': '12A'},
                     {'l10n_pe_kardex_doc_type': False, 'l10n_pe_kardex_number': '12'}):
            with self.assertRaises(ValidationError):
                with self.env.cr.savepoint():
                    move.write(vals)

    def test_36_documento_de_la_transferencia(self):
        self._build_moves()
        picking = self.env['stock.picking'].search([
            ('state', '=', 'done'), ('picking_type_code', '=', 'outgoing')], limit=1, order='id desc')
        wizard = self.env['l10n_pe.kardex.document.wizard'].create({
            'picking_id': picking.id, 'doc_type': '03', 'document': 'B001-00004567'})
        wizard.action_apply()
        self.assertEqual(set(picking.move_ids.mapped('l10n_pe_kardex_number')), {'00004567'})
        self.assertTrue(all(picking.move_ids.mapped('l10n_pe_kardex_doc_manual')))
        with self.assertRaisesRegex(UserError, 'número'):
            self.env['l10n_pe.kardex.document.wizard'].create({
                'picking_id': picking.id, 'doc_type': '03', 'document': 'SIN NUMERO'}).action_apply()

    def test_37_guia_sin_comprobante(self):
        """Sin factura, la guía de remisión de la transferencia (Tabla 10 = 09)."""
        self._build_moves()
        picking = self.env['stock.picking'].search([
            ('state', '=', 'done'), ('picking_type_code', '=', 'outgoing')], limit=1, order='id desc')
        if 'l10n_latam_document_number' not in picking._fields:
            self.skipTest('Sin guía de remisión electrónica instalada.')
        picking.l10n_latam_document_number = 'T001-00000088'
        picking.move_ids.action_l10n_pe_kardex_fill_empty()
        self.assertEqual((picking.move_ids.l10n_pe_kardex_doc_type,
                          picking.move_ids.l10n_pe_kardex_number), ('09', '00000088'))


# Los tests heredados ya corren en su propia clase.
for _name in dir(TestKardexReport):
    if _name.startswith('test_') and _name not in TestKardexDocument.__dict__:
        setattr(TestKardexDocument, _name, None)
