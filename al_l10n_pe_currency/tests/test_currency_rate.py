# -*- coding: utf-8 -*-
"""Tests del tipo de cambio SUNAT y su visualización en facturas.

No se depende de la red: se inyecta la tasa con ``_l10n_pe_upsert_rate``.
"""
from datetime import date

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCurrencyRate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.currency_id = cls.env.ref('base.PEN')
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.today = fields.Date.context_today(cls.env.user)

    def test_upsert_dual_rate(self):
        """Compra/venta se guardan y rate = 1/venta; upsert no duplica."""
        self.usd._l10n_pe_upsert_rate(self.today, 3.381, 3.391, 'sunat')
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', self.usd.id),
            ('company_id', '=', self.company.id),
            ('name', '=', self.today)], limit=1)
        self.assertTrue(rate)
        self.assertAlmostEqual(rate.rate_purchase, 3.381, places=3)
        self.assertAlmostEqual(rate.rate_sale, 3.391, places=3)
        self.assertAlmostEqual(rate.rate, 1.0 / 3.391, places=6)
        self.assertEqual(rate.ref_origin, 'sunat')
        # Re-upsert del mismo día actualiza, no duplica (constraint nativa).
        self.usd._l10n_pe_upsert_rate(self.today, 3.400, 3.410, 'apis_net')
        rates = self.env['res.currency.rate'].search([
            ('currency_id', '=', self.usd.id),
            ('company_id', '=', self.company.id),
            ('name', '=', self.today)])
        self.assertEqual(len(rates), 1)
        self.assertAlmostEqual(rates.rate_sale, 3.410, places=3)
        self.assertEqual(rates.ref_origin, 'apis_net')

    def test_invoice_shows_exchange_rate(self):
        """Factura en USD muestra el TC aplicado (S/ por US$) y su fecha."""
        self.usd._l10n_pe_upsert_rate(self.today, 3.381, 3.391, 'sunat')
        partner = self.env['res.partner'].create({'name': 'Cliente USD'})
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'currency_id': self.usd.id,
            'invoice_date': self.today,
            'invoice_line_ids': [Command.create({
                'name': 'Servicio', 'quantity': 1, 'price_unit': 100.0})],
        })
        self.assertAlmostEqual(inv.l10n_pe_exchange_rate, 3.391, places=2)
        self.assertEqual(inv.l10n_pe_exchange_rate_date, self.today)
        # El texto consolidado (un solo campo) incluye tasa y fecha.
        self.assertTrue(inv.l10n_pe_exchange_rate_info)
        self.assertIn('3.391', inv.l10n_pe_exchange_rate_info)

    def test_invoice_same_currency_hidden(self):
        """Factura en la moneda de la compañía no muestra el TC."""
        partner = self.env['res.partner'].create({'name': 'Cliente PEN'})
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'currency_id': self.company.currency_id.id,
            'invoice_line_ids': [Command.create({
                'name': 'X', 'quantity': 1, 'price_unit': 50.0})],
        })
        self.assertFalse(inv.l10n_pe_exchange_rate_info)
        self.assertFalse(inv.l10n_pe_exchange_rate_date)
