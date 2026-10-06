# -*- coding: utf-8 -*-
"""
Tests de la cola de reintento en background para impresiones fallidas
(`controllers/main.py::retry_print_receipt` / `_enqueue_escpos_retry`).

Sin esto, un fallo de impresión tras el retry-once síncrono
(`_execute_with_retry`) se perdía para siempre si el cajero no notaba o no
reintentaba el popup del core — ver «Arquitectura» en el README. Mismo patrón
que recomienda OCA para probar `queue_job`: `trap_jobs()`
intercepta el `with_delay()` sin correr nada async de verdad, y el cuerpo
del job se llama directo para probar su propio comportamiento
(éxito/`RetryableJobError`/descarte silencioso).
"""
import base64
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import odoo.tests
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.addons.queue_job.tests.common import trap_jobs
from odoo.addons.al_pos_network_printer.controllers import main as network_printer_main


def _tiny_jpeg_b64():
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (2, 2)).save(buf, format='JPEG')
    return base64.b64encode(buf.getvalue()).decode()


@odoo.tests.tagged('post_install', '-at_install')
class TestEscposRetryJob(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.write({
            'escpos_network_printer_enabled': True,
            'escpos_printer_ip': '203.0.113.10',
            'escpos_printer_port': '9100',
            # Opt-in explícito: `escpos_retry_queue_enabled` es False por
            # defecto (ver models/pos_config.py) — esta clase existe para
            # probar la cola, así que la prende acá para todos sus tests
            # salvo el que prueba explícitamente el default apagado
            # (test_disabled_flag_does_not_enqueue, más abajo).
            'escpos_retry_queue_enabled': True,
        })

    def setUp(self):
        super().setUp()
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
            # Ver el mismo header en test_print_receipt_controller.py — estas
            # rutas son `auth='public'` a propósito, así que este helper no
            # llama `self.authenticate()` antes, y necesita el header para
            # no depender de que `list_db`/`dbfilter` del servidor bajo
            # prueba puedan autoseleccionar la base sin sesión previa.
            headers={
                'Content-Type': 'application/json',
                'X-Odoo-Database': self.env.cr.dbname,
            },
        )
        self.assertEqual(response.status_code, 200, f"HTTP {response.status_code} en {path}")
        data = response.json()
        self.assertNotIn('error', data, f"JSON-RPC error en {path}: {data.get('error')}")
        return data.get('result', {})

    # ── encolado desde el endpoint HTTP ─────────────────────────────────

    def test_failed_print_enqueues_retry_job(self):
        mock_connection = MagicMock()
        mock_connection.print_image.side_effect = OSError('connection refused')
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            with trap_jobs() as trap:
                result = self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
                    'ip': '203.0.113.10', 'port': 9100, 'img': _tiny_jpeg_b64(),
                })
        self.assertFalse(result['result'])
        self.assertEqual(result['errorCode'], 'PRINTER_NOT_REACHABLE')
        self.assertTrue(result.get('queued'))
        trap.assert_jobs_count(
            1, only=self.main_pos_config._escpos_retry_print_receipt_job
        )

    def test_disabled_flag_does_not_enqueue(self):
        # `escpos_retry_queue_enabled` apagado (el default real — setUpClass
        # lo prende para el resto de esta clase): un fallo se comporta
        # exactamente igual que antes de que existiera la cola, sin encolar
        # nada.
        self.main_pos_config.write({'escpos_retry_queue_enabled': False})
        mock_connection = MagicMock()
        mock_connection.print_image.side_effect = OSError('connection refused')
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            with trap_jobs() as trap:
                result = self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
                    'ip': '203.0.113.10', 'port': 9100, 'img': _tiny_jpeg_b64(),
                })
        self.assertFalse(result['result'])
        self.assertEqual(result['errorCode'], 'PRINTER_NOT_REACHABLE')
        self.assertFalse(result.get('queued'))
        trap.assert_jobs_count(
            0, only=self.main_pos_config._escpos_retry_print_receipt_job
        )

    def test_successful_print_does_not_enqueue_retry_job(self):
        mock_connection = MagicMock()
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            with trap_jobs() as trap:
                self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
                    'ip': '203.0.113.10', 'port': 9100, 'img': _tiny_jpeg_b64(),
                })
        trap.assert_jobs_count(
            0, only=self.main_pos_config._escpos_retry_print_receipt_job
        )

    def test_repeated_failure_with_same_payload_dedups_job(self):
        # Mismo ticket (misma imagen), dos fallos — ej. el cajero aprieta
        # "Reintentar" en el popup nativo mientras el job de la primera
        # falla ya está en cola: no debe duplicarse.
        img = _tiny_jpeg_b64()
        mock_connection = MagicMock()
        mock_connection.print_image.side_effect = OSError('connection refused')
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            with trap_jobs() as trap:
                self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
                    'ip': '203.0.113.10', 'port': 9100, 'img': img,
                })
                self._jsonrpc_call('/al_pos_network_printer/print_receipt', {
                    'ip': '203.0.113.10', 'port': 9100, 'img': img,
                })
        trap.assert_jobs_count(
            1, only=self.main_pos_config._escpos_retry_print_receipt_job
        )

    # ── cuerpo del job (retry_print_receipt) ────────────────────────────

    def test_retry_job_succeeds_when_printer_recovers(self):
        mock_connection = MagicMock()
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            network_printer_main.retry_print_receipt(
                self.env, '203.0.113.10', 9100, _tiny_jpeg_b64(),
            )
        mock_connection.print_image.assert_called_once()

    def test_retry_job_raises_retryable_error_when_still_unreachable(self):
        mock_connection = MagicMock()
        mock_connection.print_image.side_effect = OSError('connection refused')
        with patch.object(network_printer_main, '_get_connection', return_value=mock_connection):
            with self.assertRaises(RetryableJobError):
                network_printer_main.retry_print_receipt(
                    self.env, '203.0.113.10', 9100, _tiny_jpeg_b64(),
                )

    def test_retry_job_drops_silently_if_target_no_longer_configured(self):
        self.main_pos_config.write({'escpos_printer_ip': False})
        with patch.object(network_printer_main, '_get_connection') as mock_get_connection:
            network_printer_main.retry_print_receipt(
                self.env, '203.0.113.10', 9100, _tiny_jpeg_b64(),
            )
        mock_get_connection.assert_not_called()

    def test_retry_job_drops_silently_on_invalid_payload(self):
        garbage_b64 = base64.b64encode(b'this is not an image').decode()
        with patch.object(network_printer_main, '_get_connection') as mock_get_connection:
            network_printer_main.retry_print_receipt(
                self.env, '203.0.113.10', 9100, garbage_b64,
            )
        mock_get_connection.assert_not_called()

    # ── _escpos_retry_queue_enabled() sobre pos.printer ─────────────────

    def test_retry_queue_enabled_for_kitchen_printer_via_any_linked_config(self):
        # Un pos.printer puede estar compartido entre varios PDV
        # (pos_config_ids, m2m del core) — alcanza con que uno solo tenga
        # el opt-in prendido.
        kitchen_printer = self.env['pos.printer'].create({
            'name': 'Test Kitchen ESC/POS (retry flag)',
            'printer_type': 'escpos_network',
            'escpos_printer_ip': '203.0.113.30',
            'escpos_printer_port': '9100',
            'pos_config_ids': [(6, 0, self.main_pos_config.ids)],
        })
        self.assertTrue(
            network_printer_main._escpos_retry_queue_enabled(kitchen_printer)
        )
        self.main_pos_config.write({'escpos_retry_queue_enabled': False})
        self.assertFalse(
            network_printer_main._escpos_retry_queue_enabled(kitchen_printer)
        )
