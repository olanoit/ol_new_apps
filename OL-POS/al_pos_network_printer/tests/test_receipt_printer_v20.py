# -*- coding: utf-8 -*-
"""Odoo 20: la ESC/POS de la caja es una de sus impresoras de recibo."""
import odoo.tests
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.al_pos_network_printer.controllers import main as network_printer_main


@odoo.tests.tagged('post_install', '-at_install')
class TestEscposReceiptPrinter(TestPointOfSaleHttpCommon):

    def _enable(self):
        self.main_pos_config.write({
            'escpos_network_printer_enabled': True,
            'escpos_printer_ip': '203.0.113.30',
            'escpos_printer_port': '9100',
        })
        return self.main_pos_config.al_escpos_receipt_printer_id

    def test_enabling_creates_linked_receipt_printer(self):
        printer = self._enable()
        self.assertEqual(printer.printer_type, 'escpos_network')
        self.assertEqual(printer.use_type, 'receipt')
        self.assertEqual(printer.escpos_printer_ip, '203.0.113.30')
        self.assertIn(printer, self.main_pos_config.receipt_printer_ids)
        self.main_pos_config.escpos_printer_ip = '203.0.113.31'
        self.assertEqual(printer.escpos_printer_ip, '203.0.113.31', 'sigue a la caja')

    def test_disabling_removes_printer_and_target(self):
        printer = self._enable()
        self.main_pos_config.escpos_network_printer_enabled = False
        self.assertFalse(printer.exists())
        self.assertFalse(self.main_pos_config.receipt_printer_ids.filtered(
            lambda p: p.printer_type == 'escpos_network'))
        self.assertFalse(network_printer_main.is_allowed_target(self.env, '203.0.113.30', 9100))

    def test_pos_boots_with_escpos_receipt_printer(self):
        """Antes de portar al plugin de impresión de 20, el TPV no cargaba
        («Cannot read properties of undefined (reading 'id')»)."""
        self._enable()
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pos_network_printer_boot_tour')
