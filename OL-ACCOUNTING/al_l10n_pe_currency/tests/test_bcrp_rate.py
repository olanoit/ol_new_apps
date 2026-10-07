# -*- coding: utf-8 -*-
"""Fuente BCRP para el tipo de cambio.

El parseo se prueba sobre respuestas fijas: la lógica de ``services.bcrp_rate``
es pura y no debe depender de que el servicio esté disponible.
"""
from datetime import date
from unittest.mock import MagicMock, patch

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
        """El cierre del 02/03 es el T.C. SUNAT del 03/03, y así."""
        if self.env.company.currency_id != self.env.ref('base.PEN') \
                or self.env.company.parent_id:
            self.skipTest('el tipo de cambio SUNAT solo se carga en '
                          'compañías raíz en soles')
        usd = self.env.ref('base.USD')
        with patch.object(bcrp_rate, 'fetch_bcrp',
                          return_value=bcrp_rate.parse_response(BCRP_PAYLOAD)) as fetch:
            loaded = self.env['res.currency'].l10n_pe_update_range_bcrp(
                date(2026, 3, 3), date(2026, 3, 4))
        self.assertEqual(loaded, 2)
        self.assertEqual(fetch.call_args.args, (date(2026, 2, 21), date(2026, 3, 3)),
                         'se piden los cierres anteriores al rango')
        Rate = self.env['res.currency.rate']
        domain = [('currency_id', '=', usd.id), ('company_id', '=', self.env.company.id)]
        rate = Rate.search(domain + [('name', '=', '2026-03-03')], limit=1)
        self.assertTrue(rate, 'debería haberse creado el tipo de cambio')
        self.assertEqual(rate.ref_origin, 'bcrp')
        self.assertAlmostEqual(rate.rate_sale, 3.368, places=3)
        self.assertAlmostEqual(rate.rate_purchase, 3.359, places=3)
        self.assertAlmostEqual(rate.rate, 1.0 / 3.368, places=6,
                               msg='la tasa contable es 1 / venta')
        self.assertAlmostEqual(
            Rate.search(domain + [('name', '=', '2026-03-04')]).rate_sale, 3.408, places=3)

    def test_update_range_is_idempotent(self):
        """Recargar el mismo rango actualiza, no duplica."""
        if self.env.company.currency_id != self.env.ref('base.PEN') \
                or self.env.company.parent_id:
            self.skipTest('el tipo de cambio SUNAT solo se carga en '
                          'compañías raíz en soles')
        rates = bcrp_rate.parse_response(BCRP_PAYLOAD)
        with patch.object(bcrp_rate, 'fetch_bcrp', return_value=rates):
            self.env['res.currency'].l10n_pe_update_range_bcrp(
                date(2026, 3, 3), date(2026, 3, 4))
            self.env['res.currency'].l10n_pe_update_range_bcrp(
                date(2026, 3, 3), date(2026, 3, 4))
        found = self.env['res.currency.rate'].search_count([
            ('currency_id', '=', self.env.ref('base.USD').id),
            ('company_id', '=', self.env.company.id),
            ('name', '=', '2026-03-03'),
        ])
        self.assertEqual(found, 1)

    # ------------------------------------------------------------------
    # Fecha SUNAT de los cierres del BCRP (datos reales de octubre 2026)
    # ------------------------------------------------------------------
    def test_to_sunat_dates_real_october(self):
        """SUNAT 03, 04 y 05/10 = cierre del viernes 02/10; SUNAT 06/10 = 05/10."""
        closes = [
            {'date': date(2026, 10, 1), 'compra': 3.447, 'venta': 3.454},
            {'date': date(2026, 10, 2), 'compra': 3.437, 'venta': 3.442},
            {'date': date(2026, 10, 5), 'compra': 3.423, 'venta': 3.435},
        ]
        result = {r['date']: (r['compra'], r['venta'])
                  for r in bcrp_rate.to_sunat_dates(closes, date(2026, 10, 1), date(2026, 10, 6))}
        self.assertNotIn(date(2026, 10, 1), result, 'sin cierre anterior no hay tasa')
        self.assertEqual(result[date(2026, 10, 2)], (3.447, 3.454))
        for day in (3, 4, 5):
            self.assertEqual(result[date(2026, 10, day)], (3.437, 3.442))
        self.assertEqual(result[date(2026, 10, 6)], (3.423, 3.435))

    def test_update_range_never_loads_future_dates(self):
        if self.env.company.currency_id != self.env.ref('base.PEN') \
                or self.env.company.parent_id:
            self.skipTest('solo compañías raíz en soles')
        today = date.today()
        closes = [{'date': date(2020, 1, 1), 'compra': 3.3, 'venta': 3.31}]
        with patch.object(bcrp_rate, 'fetch_bcrp', return_value=closes), \
                patch('odoo.fields.Date.context_today', return_value=today):
            self.env['res.currency'].l10n_pe_update_range_bcrp(
                today, today.replace(year=today.year + 1))
        self.assertFalse(self.env['res.currency.rate'].search_count([
            ('currency_id', '=', self.env.ref('base.USD').id),
            ('company_id', '=', self.env.company.id),
            ('name', '>', today)]))

    def test_fetch_retries_a_non_json_answer(self):
        """El BCRP a veces responde algo que no es JSON: se reintenta."""
        bad, good = MagicMock(), MagicMock()
        bad.json.side_effect = ValueError('Expecting value')
        good.json.return_value = BCRP_PAYLOAD
        with patch.object(bcrp_rate.requests, 'get', side_effect=[bad, good]) as get, \
                patch.object(bcrp_rate.time, 'sleep'):
            rates = bcrp_rate.fetch_bcrp(date(2026, 3, 1), date(2026, 3, 3))
        self.assertEqual(get.call_count, 2)
        self.assertEqual(len(rates), 2)

    def test_service_failure_returns_empty(self):
        """Si el BCRP no responde, no se interrumpe el proceso."""
        with patch.object(bcrp_rate, 'fetch_bcrp', return_value=[]):
            loaded = self.env['res.currency'].l10n_pe_update_range_bcrp(
                date(2026, 3, 2), date(2026, 3, 3))
        self.assertEqual(loaded, 0)
