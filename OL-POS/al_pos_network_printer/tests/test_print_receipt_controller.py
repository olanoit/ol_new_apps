# -*- coding: utf-8 -*-
"""
Tests de integración HTTP para PosNetworkPrinterController.

Usa HttpCase (vía TestPointOfSaleHttpCommon) para llamar de verdad a
`/al_pos_network_printer/print_receipt` y `/open_cashbox` como los llama
el POS (`type='jsonrpc'`). `EscposNetwork` y la conexión TCP persistente se
mockean siempre: estos tests verifican el contrato HTTP (allow-list, límite
de tamaño, decodificación de imagen, forma de la respuesta), no que
`python-escpos` sepa hablarle a una impresora real — eso no se puede probar
sin una impresora física, y no es lo que puede romperse por un cambio en
este módulo.
"""
import base64
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import odoo.tests
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.al_pos_network_printer.controllers import main as network_printer_main


def _tiny_jpeg_b64():
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (2, 2)).save(buf, format='JPEG')
    return base64.b64encode(buf.getvalue()).decode()


@odoo.tests.tagged('post_install', '-at_install')
class TestPrintReceiptController(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.write({
            'escpos_network_printer_enabled': True,
            'escpos_printer_ip': '203.0.113.10',
            'escpos_printer_port': '9100',
        })

    def setUp(self):
        super().setUp()
        # `EscposNetwork is None` es la primera guarda de ambas rutas
        # (python-escpos no instalado) — se mockea como presente en todos
        # los tests de este archivo para que se pueda probar el resto del
        # contrato HTTP sin depender de si la librería opcional está
        # instalada en el entorno que corre los tests.
        patcher = patch.object(network_printer_main, 'EscposNetwork', MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _jsonrpc_call(self, path, receipt):
        payload = json.dumps({
            'jsonrpc': '2.0',
            'method': 'call',
            'id': 1,
            'params': {'receipt': receipt},
        }).encode('utf-8')
        response = self.url_open(
            path,
            data=payload,
            # `X-Odoo-Database` explícito: estas rutas son `auth='public'` a
            # propósito (ver Seguridad en README — el POS puede correr en
            # modo kiosco sin sesión de backend), así que estos tests no
            # llaman `self.authenticate()` antes de pegarle (justamente
            # están probando el camino sin sesión). En un servidor con
            # `list_db=True` y varias bases (como cualquier entorno de dev
            # con múltiples proyectos en el mismo cluster de Postgres), sin
            # sesión previa ni este header Odoo no puede autoseleccionar la
            # base para una request pública y devuelve 404 "No database is
            # selected" antes de llegar siquiera al controller — nada que
            # ver con la lógica que se está probando acá.
            headers={
                'Content-Type': 'application/json',
                'X-Odoo-Database': self.env.cr.dbname,
            },
        )
        self.assertEqual(response.status_code, 200, f"HTTP {response.status_code} en {path}")
        data = response.json()
        self.assertNotIn('error', data, f"JSON-RPC error en {path}: {data.get('error')}")
        return data.get('result', {})

    # ── allow-list ───────────────────────────────────────────────────────

    def test_rejects_unconfigured_destination(self):
        result = self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
            'ip': '10.0.0.1', 'port': 9100, 'img': _tiny_jpeg_b64(),
        })
        self.assertFalse(result['result'])
        self.assertEqual(result['errorCode'], 'PRINTER_NOT_CONFIGURED')

    def test_open_cashbox_rejects_unconfigured_destination(self):
        result = self._jsonrpc_call('/al_pos_network_printer/open_cashbox', {
            'ip': '10.0.0.1', 'port': 9100,
        })
        self.assertFalse(result['result'])
        self.assertEqual(result['errorCode'], 'PRINTER_NOT_CONFIGURED')

    def test_rejects_missing_port(self):
        result = self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
            'ip': '203.0.113.10', 'img': _tiny_jpeg_b64(),
        })
        self.assertFalse(result['result'])
        self.assertEqual(result['errorCode'], 'PRINTER_NOT_CONFIGURED')

    # ── límite de tamaño / decodificación ───────────────────────────────

    def test_rejects_oversized_payload(self):
        oversized = 'A' * (network_printer_main.MAX_RECEIPT_IMAGE_BYTES + 1)
        result = self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
            'ip': '203.0.113.10', 'port': 9100, 'img': oversized,
        })
        self.assertFalse(result['result'])
        self.assertEqual(result['errorCode'], 'IMAGE_TOO_LARGE')

    def test_rejects_invalid_image_payload(self):
        garbage_b64 = base64.b64encode(b'this is not an image').decode()
        result = self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
            'ip': '203.0.113.10', 'port': 9100, 'img': garbage_b64,
        })
        self.assertFalse(result['result'])
        self.assertEqual(result['errorCode'], 'INVALID_IMAGE')

    # ── camino feliz (conexión TCP mockeada) ────────────────────────────

    def test_prints_on_configured_destination(self):
        mock_connection = MagicMock()
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            result = self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
                'ip': '203.0.113.10', 'port': 9100, 'img': _tiny_jpeg_b64(),
            })
        self.assertTrue(result['result'])
        mock_connection.print_image.assert_called_once()

    def test_open_cashbox_on_configured_destination(self):
        mock_connection = MagicMock()
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            result = self._jsonrpc_call('/al_pos_network_printer/open_cashbox', {
                'ip': '203.0.113.10', 'port': 9100,
            })
        self.assertTrue(result['result'])
        mock_connection.open_cashbox.assert_called_once()

    def test_reports_unreachable_printer(self):
        mock_connection = MagicMock()
        mock_connection.print_image.side_effect = OSError('connection refused')
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            result = self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
                'ip': '203.0.113.10', 'port': 9100, 'img': _tiny_jpeg_b64(),
            })
        self.assertFalse(result['result'])
        self.assertEqual(result['errorCode'], 'PRINTER_NOT_REACHABLE')
        self.assertTrue(result.get('canRetry'))
