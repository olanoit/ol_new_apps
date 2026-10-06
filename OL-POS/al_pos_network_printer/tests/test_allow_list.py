# -*- coding: utf-8 -*-
"""
Tests de la allow-list de destinos ESC/POS (`controllers/main.py`).

`is_allowed_target()` es el único control que evita que
`/al_pos_network_printer/print_receipt` (auth='public') se pueda usar
como proxy SSRF: solo deja pasar un IP:puerto que ya esté configurado en
algún `pos.config`/`pos.printer` activo. `print_pdf_bytes()` (para los
comprobantes en PDF que impriman otros módulos) reutiliza la
misma función — se prueba acá también su comportamiento cuando falta la
dependencia opcional `pymupdf`, sin necesitar tenerla instalada de verdad.

No abre ningún socket real: los casos que sí pasarían la allow-list
retornan antes de llegar a `_get_connection()`/network I/O (ver el orden
de checks en `print_pdf_bytes`), así que no hace falta mockear TCP.
"""
from unittest.mock import MagicMock, patch

import odoo.tests
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.al_pos_network_printer.controllers import main as network_printer_main


@odoo.tests.tagged('post_install', '-at_install')
class TestAllowList(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.write({
            'escpos_network_printer_enabled': True,
            'escpos_printer_ip': '203.0.113.10',
            'escpos_printer_port': '9100',
        })
        cls.kitchen_printer = cls.env['pos.printer'].create({
            'name': 'Test Kitchen ESC/POS',
            'printer_type': 'escpos_network',
            'escpos_printer_ip': '203.0.113.20',
            'escpos_printer_port': '9100',
        })

    # ── is_allowed_target() ─────────────────────────────────────────────

    def test_allows_configured_pos_config_receipt_printer(self):
        self.assertTrue(
            network_printer_main.is_allowed_target(self.env, '203.0.113.10', 9100)
        )

    def test_allows_configured_pos_printer_order_printer(self):
        self.assertTrue(
            network_printer_main.is_allowed_target(self.env, '203.0.113.20', 9100)
        )

    def test_rejects_receipt_printer_when_toggle_disabled(self):
        # Toggle "Impresora ESC/POS de red" apagado: la IP sigue guardada,
        # pero el PDV imprime como en el nativo y ese destino deja de ser
        # válido (pedido en vivo 2026-09-28).
        self.main_pos_config.escpos_network_printer_enabled = False
        self.assertFalse(self.main_pos_config._escpos_receipt_printer_active())
        self.assertFalse(
            network_printer_main.is_allowed_target(self.env, '203.0.113.10', 9100)
        )
        # Las impresoras de preparación (pos.printer) no dependen del toggle.
        self.assertTrue(
            network_printer_main.is_allowed_target(self.env, '203.0.113.20', 9100)
        )

    def test_receipt_printer_active_requires_toggle_and_ip(self):
        self.assertTrue(self.main_pos_config._escpos_receipt_printer_active())
        self.main_pos_config.escpos_printer_ip = False
        self.assertFalse(self.main_pos_config._escpos_receipt_printer_active())

    def test_epson_allowed_when_escpos_toggle_disabled(self):
        # Con la ESC/POS apagada se puede configurar Epson aunque la IP de
        # la ESC/POS siga guardada; con la ESC/POS activa, sigue prohibido.
        from odoo.exceptions import ValidationError
        self.main_pos_config.escpos_network_printer_enabled = False
        self.main_pos_config.epson_printer_ip = '203.0.113.99'
        self.main_pos_config.epson_printer_ip = False
        with self.assertRaises(ValidationError):
            self.main_pos_config.write({
                'escpos_network_printer_enabled': True,
                'epson_printer_ip': '203.0.113.99',
            })

    def test_rejects_unconfigured_ip(self):
        self.assertFalse(
            network_printer_main.is_allowed_target(self.env, '10.0.0.1', 9100)
        )

    def test_rejects_configured_ip_with_wrong_port(self):
        # Mismo IP que la impresora de recibo, puerto distinto: no debe
        # bastar con que coincida el IP solo.
        self.assertFalse(
            network_printer_main.is_allowed_target(self.env, '203.0.113.10', 9999)
        )

    def test_port_is_matched_as_string(self):
        # `escpos_printer_port` es un Char ("9100"); is_allowed_target()
        # debe aceptar el puerto como int (así lo manda el controller,
        # después de `int(port)`) y compararlo igual.
        self.assertIsInstance(self.main_pos_config.escpos_printer_port, str)
        self.assertTrue(
            network_printer_main.is_allowed_target(self.env, '203.0.113.10', 9100)
        )

    # ── print_pdf_bytes() ────────────────────────────────────────────────

    def test_print_pdf_bytes_rejects_unlisted_target(self):
        # `fitz` mockeado (truthy) para aislar el chequeo de allow-list del
        # chequeo de dependencia faltante (ver el siguiente test) — sin
        # esto, en un entorno sin pymupdf instalado este caso pasaría por
        # la razón equivocada.
        with patch.object(network_printer_main, 'fitz', MagicMock()):
            result = network_printer_main.print_pdf_bytes(
                self.env, '198.51.100.1', 9100, b'not-a-real-pdf',
            )
        self.assertFalse(result)

    def test_print_pdf_bytes_returns_false_without_pymupdf(self):
        # Con `fitz is None` la función debe volver `False` sin levantar
        # excepción, sin importar si el destino está en la allow-list —
        # es el contrato documentado para un `queue_job` best-effort
        # (ver docstring de print_pdf_bytes).
        with patch.object(network_printer_main, 'fitz', None):
            result = network_printer_main.print_pdf_bytes(
                self.env, '203.0.113.10', 9100, b'not-a-real-pdf',
            )
        self.assertFalse(result)
