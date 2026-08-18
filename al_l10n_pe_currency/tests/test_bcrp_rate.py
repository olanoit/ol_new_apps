# -*- coding: utf-8 -*-
"""Fuente BCRP para el tipo de cambio.

El parseo se prueba sobre respuestas fijas: la lógica de ``services.bcrp_rate``
es pura y no debe depender de que el servicio esté disponible.
"""
from datetime import date
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_l10n_pe_currency.services import bcrp_rate

# Respuesta real del BCRP para las series SBS compra/venta.
BCRP_PAYLOAD = {
    'config': {
        'title': 'Tipo de cambio',
        'series': [
            {'name': 'Tipo de cambio - TC Sistema bancario SBS (S/ por US$) - Compra'},
            {'name': 'Tipo de cambio - TC Sistema bancario SBS (S/ por US$) - Venta'},
        ],
    },
    'periods': [
        {'name': '02.Mar.26', 'values': ['3.359', '3.368']},
        {'name': '03.Mar.26', 'values': ['3.403', '3.408']},
    ],
}


@tagged('post_install', '-at_install')
class TestBcrpRate(TransactionCase):

    # ------------------------------------------------------------------
    # Parseo del periodo
    # ------------------------------------------------------------------
    def test_parse_period(self):
        self.assertEqual(bcrp_rate.parse_period('02.Mar.26'), date(2026, 3, 2))
        self.assertEqual(bcrp_rate.parse_period('31.Dic.25'), date(2025, 12, 31))
        self.assertEqual(bcrp_rate.parse_period('01.Set.26'), date(2026, 9, 1),
                         'el BCRP abrevia setiembre como «Set»')
        self.assertEqual(bcrp_rate.parse_period('01.Sep.26'), date(2026, 9, 1))

    def test_parse_period_rejects_garbage(self):
        for raw in ('', None, 'no es fecha', '99.Xxx.26', '02/03/2026'):
            self.assertIsNone(bcrp_rate.parse_period(raw))

    # ------------------------------------------------------------------
    # Parseo de valores
    # ------------------------------------------------------------------
    def test_parse_value(self):
        self.assertEqual(bcrp_rate.parse_value('3.368'), 3.368)
        self.assertIsNone(bcrp_rate.parse_value('n.d.'),
                          'los días sin publicación llegan como «n.d.»')
        self.assertIsNone(bcrp_rate.parse_value(''))
        self.assertIsNone(bcrp_rate.parse_value(None))
        self.assertIsNone(bcrp_rate.parse_value('0'))

    # ------------------------------------------------------------------
    # Parseo de la respuesta
    # ------------------------------------------------------------------
    def test_parse_response(self):
        rates = bcrp_rate.parse_response(BCRP_PAYLOAD)
        self.assertEqual(len(rates), 2)
        self.assertEqual(rates[0], {'date': date(2026, 3, 2),
                                    'compra': 3.359, 'venta': 3.368})

    def test_parse_response_skips_unpublished_days(self):
        """Sin tipo de cambio venta no hay conversión posible: se descarta."""
        payload = {'periods': [
            {'name': '07.Mar.26', 'values': ['n.d.', 'n.d.']},
            {'name': '09.Mar.26', 'values': ['3.400', '3.410']},
        ]}
        rates = bcrp_rate.parse_response(payload)
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0]['date'], date(2026, 3, 9))

    def test_parse_response_falls_back_to_sell_rate(self):
        """Si falta la compra se usa la venta, para no perder el día."""
        payload = {'periods': [{'name': '09.Mar.26', 'values': ['n.d.', '3.410']}]}
        rates = bcrp_rate.parse_response(payload)
        self.assertEqual(rates[0]['compra'], 3.410)

    def test_parse_response_tolerates_empty(self):
        for payload in ({}, None, {'periods': []}, {'periods': [{'name': 'x'}]}):
            self.assertEqual(bcrp_rate.parse_response(payload), [])

    # ------------------------------------------------------------------
    # Integración con el ORM
    # ------------------------------------------------------------------
    def test_update_range_creates_rates(self):
        usd = self.env.ref('base.USD')
        with patch.object(bcrp_rate, 'fetch_bcrp',
                          return_value=bcrp_rate.parse_response(BCRP_PAYLOAD)):
            loaded = self.env['res.currency'].l10n_pe_update_range_bcrp(
                date(2026, 3, 2), date(2026, 3, 3))
        self.assertEqual(loaded, 2)
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', usd.id),
            ('company_id', '=', self.env.company.id),
            ('name', '=', '2026-03-02'),
        ], limit=1)
        self.assertTrue(rate, 'debería haberse creado el tipo de cambio')
        self.assertEqual(rate.ref_origin, 'bcrp')
        self.assertAlmostEqual(rate.rate_sale, 3.368, places=3)
        self.assertAlmostEqual(rate.rate_purchase, 3.359, places=3)
        self.assertAlmostEqual(rate.rate, 1.0 / 3.368, places=6,
                               msg='la tasa contable es 1 / venta')

    def test_update_range_is_idempotent(self):
        """Recargar el mismo rango actualiza, no duplica."""
        rates = bcrp_rate.parse_response(BCRP_PAYLOAD)
        with patch.object(bcrp_rate, 'fetch_bcrp', return_value=rates):
            self.env['res.currency'].l10n_pe_update_range_bcrp(
                date(2026, 3, 2), date(2026, 3, 3))
            self.env['res.currency'].l10n_pe_update_range_bcrp(
                date(2026, 3, 2), date(2026, 3, 3))
        found = self.env['res.currency.rate'].search_count([
            ('currency_id', '=', self.env.ref('base.USD').id),
            ('company_id', '=', self.env.company.id),
            ('name', '=', '2026-03-02'),
        ])
        self.assertEqual(found, 1)

    def test_service_failure_returns_empty(self):
        """Si el BCRP no responde, no se interrumpe el proceso."""
        with patch.object(bcrp_rate, 'fetch_bcrp', return_value=[]):
            loaded = self.env['res.currency'].l10n_pe_update_range_bcrp(
                date(2026, 3, 2), date(2026, 3, 3))
        self.assertEqual(loaded, 0)
