# -*- coding: utf-8 -*-
"""
Tests para el botón "Probar impresora" (`pos.config.action_test_escpos_printer`)
y el toggle "Imprimir automáticamente al pagar" (`pos.config.escpos_auto_print`).

Mismo criterio que test_print_receipt_controller.py: `EscposNetwork` y la
conexión TCP se mockean siempre — estos tests verifican el contrato Python
(qué se llama, qué se levanta, qué queda escrito en iface_print_auto/
iface_print_skip_screen), no que python-escpos sepa hablarle a una
impresora real.
"""
from unittest.mock import MagicMock, patch

import odoo.tests
from odoo.exceptions import UserError, ValidationError
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.al_pos_network_printer.controllers import main as network_printer_main


@odoo.tests.tagged('post_install', '-at_install')
class TestTestEscposPrinterButton(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.write({
            'escpos_printer_mode': 'backend',
            'escpos_printer_ip': '203.0.113.10',
            'escpos_printer_port': '9100',
        })

    def setUp(self):
        super().setUp()
        patcher = patch.object(network_printer_main, 'EscposNetwork', MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rejects_agent_mode(self):
        self.main_pos_config.escpos_printer_mode = 'agent'
        with self.assertRaises(ValidationError):
            self.main_pos_config.action_test_escpos_printer()

    def test_rejects_missing_ip(self):
        self.main_pos_config.write({
            'escpos_printer_mode': 'backend',
            'escpos_printer_ip': False,
        })
        with self.assertRaises(ValidationError):
            self.main_pos_config.action_test_escpos_printer()

    def test_prints_demo_ticket_on_backend_mode(self):
        mock_connection = MagicMock()
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            result = self.main_pos_config.action_test_escpos_printer()
        mock_connection.print_test_ticket.assert_called_once()
        lines = mock_connection.print_test_ticket.call_args[0][0]
        self.assertIn(self.main_pos_config.name, lines)
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['params']['type'], 'success')

    def test_missing_escpos_library_raises_actionable_error(self):
        with patch.object(network_printer_main, 'EscposNetwork', None):
            with self.assertRaises(UserError):
                self.main_pos_config.action_test_escpos_printer()

    def test_printer_error_is_wrapped_in_validation_error(self):
        mock_connection = MagicMock()
        mock_connection.print_test_ticket.side_effect = OSError('connection refused')
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            with self.assertRaises(ValidationError):
                self.main_pos_config.action_test_escpos_printer()

    def test_res_config_settings_delegates_to_pos_config(self):
        mock_connection = MagicMock()
        settings = self.env['res.config.settings'].create({
            'pos_config_id': self.main_pos_config.id,
        })
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            result = settings.action_test_escpos_printer()
        mock_connection.print_test_ticket.assert_called_once()
        self.assertEqual(result['type'], 'ir.actions.client')


@odoo.tests.tagged('post_install', '-at_install')
class TestEscposAutoPrintToggle(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.write({
            'iface_print_auto': False,
            'iface_print_skip_screen': False,
        })

    def test_enabling_sets_core_auto_print_fields(self):
        self.main_pos_config.escpos_auto_print = True
        self.assertTrue(self.main_pos_config.iface_print_auto)
        self.assertTrue(self.main_pos_config.iface_print_skip_screen)

    def test_disabling_reverts_to_manual_process(self):
        self.main_pos_config.escpos_auto_print = True
        self.main_pos_config.escpos_auto_print = False
        self.assertFalse(self.main_pos_config.iface_print_auto)
        self.assertFalse(self.main_pos_config.iface_print_skip_screen)

    def test_reflects_iface_print_auto_set_elsewhere(self):
        # El toggle no es un campo propio desincronizable — es compute()
        # sobre iface_print_auto, así que cambiarlo por cualquier otra vía
        # (ej. la propia pantalla nativa de Ajustes) también se refleja acá.
        self.main_pos_config.iface_print_auto = True
        self.assertTrue(self.main_pos_config.escpos_auto_print)

    def test_res_config_settings_related_field_round_trips(self):
        settings = self.env['res.config.settings'].create({
            'pos_config_id': self.main_pos_config.id,
            'pos_escpos_auto_print': True,
        })
        settings.execute()
        self.assertTrue(self.main_pos_config.iface_print_auto)
        self.assertTrue(self.main_pos_config.iface_print_skip_screen)
