# -*- coding: utf-8 -*-
"""Registro del tipo de cambio compra y venta.

Odoo maneja una única tasa (``rate``), expresada como unidades de moneda
extranjera por una de la compañía. En Perú se trabaja con dos tipos de cambio
—compra y venta— y se expresan al revés: soles por dólar. Estos tests fijan
que ambas representaciones digan siempre lo mismo.
"""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_l10n_pe_currency.services import decolecta_rate


@tagged('post_install', '-at_install')
class TestRatePurchaseSale(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref('base.USD')
        cls.Rate = cls.env['res.currency.rate']

    def _create(self, **values):
        vals = {
            'name': '2026-03-20',
            'currency_id': self.usd.id,
            'company_id': self.env.company.id,
        }
        vals.update(values)
        return self.Rate.create(vals)

    # ------------------------------------------------------------------
    # Alta manual
    # ------------------------------------------------------------------
    def test_sale_sets_native_rate(self):
        """Registrar la venta debe fijar la tasa nativa como su inversa."""
        rate = self._create(rate_sale=3.75)
        self.assertAlmostEqual(rate.rate, 1 / 3.75, places=6)

    def test_purchase_defaults_to_sale(self):
        """Sin compra informada se asume la venta, no un cero engañoso."""
        rate = self._create(rate_sale=3.75)
        self.assertAlmostEqual(rate.rate_purchase, 3.75, places=6)

    def test_both_rates_are_kept(self):
        rate = self._create(rate_purchase=3.72, rate_sale=3.75)
        self.assertAlmostEqual(rate.rate_purchase, 3.72, places=6)
        self.assertAlmostEqual(rate.rate_sale, 3.75, places=6)
        self.assertAlmostEqual(rate.rate, 1 / 3.75, places=6)

    def test_native_rate_fills_sale(self):
        """Si solo se toca la tasa nativa, la venta se deduce de ella."""
        rate = self._create(rate=0.25)
        self.assertAlmostEqual(rate.rate_sale, 4.0, places=6)

    # ------------------------------------------------------------------
    # Modificación
    # ------------------------------------------------------------------
    def test_writing_sale_updates_native_rate(self):
        rate = self._create(rate_sale=3.75)
        rate.rate_sale = 3.80
        self.assertAlmostEqual(rate.rate, 1 / 3.80, places=6)

    def test_writing_native_rate_updates_sale(self):
        rate = self._create(rate_sale=3.75)
        rate.rate = 0.25
        self.assertAlmostEqual(rate.rate_sale, 4.0, places=6)

    def test_writing_purchase_alone_keeps_sale(self):
        """La compra no interviene en la conversión contable."""
        rate = self._create(rate_purchase=3.72, rate_sale=3.75)
        rate.rate_purchase = 3.70
        self.assertAlmostEqual(rate.rate_sale, 3.75, places=6)
        self.assertAlmostEqual(rate.rate, 1 / 3.75, places=6)

    def test_write_without_rate_fields_is_untouched(self):
        rate = self._create(rate_purchase=3.72, rate_sale=3.75)
        rate.ref_origin = 'manual'
        self.assertAlmostEqual(rate.rate_sale, 3.75, places=6)

    def test_write_on_multiple_records(self):
        """El write debe funcionar sobre un conjunto, no solo sobre uno."""
        first = self._create(name='2026-03-21', rate_sale=3.75)
        second = self._create(name='2026-03-22', rate_sale=3.80)
        (first | second).write({'rate_sale': 3.90})
        for rate in (first, second):
            self.assertAlmostEqual(rate.rate, 1 / 3.90, places=6)

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    def test_negative_rates_are_rejected(self):
        with self.assertRaises(ValidationError):
            self._create(rate_sale=3.75, rate_purchase=-1)

    def test_origin_includes_all_sources(self):
        origins = dict(self.Rate._fields['ref_origin'].selection)
        for source in ('sunat', 'bcrp', 'decolecta', 'apis_net', 'manual'):
            self.assertIn(source, origins)

    # ------------------------------------------------------------------
    # Fuente Decolecta
    # ------------------------------------------------------------------
    def test_decolecta_parse(self):
        payload = {
            'buy_price': 3.359,
            'sell_price': 3.368,
            'base_currency': 'PEN',
            'quote_currency': 'USD',
            'date': '2026-03-02',
        }
        parsed = decolecta_rate.parse_rate(payload)
        self.assertEqual(parsed, {'date': date(2026, 3, 2),
                                  'compra': 3.359, 'venta': 3.368})

    def test_decolecta_parse_rejects_incomplete(self):
        for payload in ({}, None, {'buy_price': 3.3},
                        {'sell_price': 0}, {'sell_price': 'x'}):
            self.assertIsNone(decolecta_rate.parse_rate(payload))

    def test_decolecta_falls_back_to_sell_price(self):
        parsed = decolecta_rate.parse_rate(
            {'sell_price': 3.368, 'date': '2026-03-02'})
        self.assertEqual(parsed['compra'], 3.368)

    def test_decolecta_without_token_does_nothing(self):
        self.assertIsNone(decolecta_rate.fetch_decolecta('', date=date(2026, 3, 2)))

    def test_decolecta_updates_rate(self):
        with patch.object(decolecta_rate, 'fetch_decolecta',
                          return_value={'date': date(2026, 3, 2),
                                        'compra': 3.359, 'venta': 3.368}):
            done = self.env['res.currency'].l10n_pe_update_date_decolecta(
                date(2026, 3, 2), token='fake')
        self.assertTrue(done)
        rate = self.Rate.search([
            ('currency_id', '=', self.usd.id),
            ('company_id', '=', self.env.company.id),
            ('name', '=', '2026-03-02'),
        ], limit=1)
        self.assertEqual(rate.ref_origin, 'decolecta')
        self.assertAlmostEqual(rate.rate_purchase, 3.359, places=3)
        self.assertAlmostEqual(rate.rate_sale, 3.368, places=3)
