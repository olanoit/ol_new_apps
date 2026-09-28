# -*- coding: utf-8 -*-
"""A qué compañías llega el tipo de cambio y quién puede cargarlo.

* El núcleo prohíbe tasas en las sucursales: cargar el tipo de cambio en una
  base con sucursales no debe fallar, y la tasa va solo a la matriz.
* «1 / venta» solo tiene sentido en compañías cuya moneda es el sol.
* Los métodos de carga son públicos y escriben con ``sudo()``: un usuario sin
  contabilidad no debe poder usarlos.
"""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_l10n_pe_currency.services import decolecta_rate

RATE_DAY = date(2026, 4, 6)


@tagged('post_install', '-at_install')
class TestRateUpdateScope(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.pen = cls.env.ref('base.PEN')
        cls.Rate = cls.env['res.currency.rate']
        cls.root = cls.env['res.company'].create({
            'name': 'MATRIZ PE TC', 'currency_id': cls.pen.id})
        cls.branch = cls.env['res.company'].create({
            'name': 'SUCURSAL PE TC', 'parent_id': cls.root.id})
        clp = cls.env.ref('base.CLP')
        clp.active = True
        cls.foreign_root = cls.env['res.company'].create({
            'name': 'COMPAÑÍA CLP TC', 'currency_id': clp.id})

    def _rates(self, company):
        return self.Rate.search([
            ('currency_id', '=', self.usd.id),
            ('company_id', '=', company.id),
            ('name', '=', RATE_DAY),
        ])

    # ------------------------------------------------------------------
    # Alcance por compañía
    # ------------------------------------------------------------------
    def test_branches_do_not_break_the_update(self):
        """Con sucursales la carga funciona y la tasa queda en la matriz."""
        self.usd._l10n_pe_upsert_rate(RATE_DAY, 3.70, 3.75, 'sunat')
        self.assertEqual(len(self._rates(self.root)), 1)
        self.assertFalse(self._rates(self.branch))

    def test_non_pen_company_is_left_alone(self):
        """Una compañía en otra moneda no recibe «1 / venta»."""
        self.usd._l10n_pe_upsert_rate(RATE_DAY, 3.70, 3.75, 'sunat')
        self.assertFalse(self._rates(self.foreign_root))

    def test_upsert_updates_every_root_without_duplicates(self):
        self.usd._l10n_pe_upsert_rate(RATE_DAY, 3.70, 3.75, 'sunat')
        self.usd._l10n_pe_upsert_rate(RATE_DAY, 3.71, 3.76, 'bcrp')
        rate = self._rates(self.root)
        self.assertEqual(len(rate), 1)
        self.assertAlmostEqual(rate.rate_sale, 3.76, places=3)
        self.assertEqual(rate.ref_origin, 'bcrp')

    # ------------------------------------------------------------------
    # Permisos
    # ------------------------------------------------------------------
    def test_internal_user_cannot_load_rates(self):
        user = new_test_user(self.env, login='tc_sin_contabilidad',
                             groups='base.group_user')
        currency = self.env['res.currency'].with_user(user)
        with patch.object(decolecta_rate, 'fetch_decolecta',
                          return_value={'date': RATE_DAY,
                                        'compra': 3.70, 'venta': 3.75}):
            with self.assertRaises(AccessError):
                currency.l10n_pe_update_date_decolecta(RATE_DAY, token='x')
        with self.assertRaises(AccessError):
            currency.l10n_pe_update_range_bcrp(RATE_DAY, RATE_DAY)
        with self.assertRaises(AccessError):
            currency.l10n_pe_update_today_sunat()
        self.assertFalse(self._rates(self.root))

    def test_accountant_can_load_rates(self):
        user = new_test_user(self.env, login='tc_contable',
                             groups='base.group_user,account.group_account_manager')
        with patch.object(decolecta_rate, 'fetch_decolecta',
                          return_value={'date': RATE_DAY,
                                        'compra': 3.70, 'venta': 3.75}):
            done = self.env['res.currency'].with_user(user) \
                .l10n_pe_update_date_decolecta(RATE_DAY, token='x')
        self.assertTrue(done)
        self.assertTrue(self._rates(self.root))

    # ------------------------------------------------------------------
    # Asistente
    # ------------------------------------------------------------------
    def test_wizard_does_not_preload_tokens(self):
        """El token de la conexión no viaja al navegador."""
        wizard = self.env['l10n_pe.exchange.rate.wizard'].create({})
        self.assertFalse(wizard.decolecta_token)
        self.assertFalse(wizard.apis_net_token)

    def test_wizard_limits_day_by_day_ranges(self):
        """Un rango largo por Decolecta se rechaza sin consultar nada."""
        wizard = self.env['l10n_pe.exchange.rate.wizard'].create({
            'range': 'dates', 'source': 'decolecta',
            'date_start': date(2026, 1, 1), 'date_end': date(2026, 3, 31),
        })
        with patch.object(decolecta_rate, 'fetch_decolecta') as fetch:
            action = wizard.action_process()
        fetch.assert_not_called()
        self.assertEqual(action['params']['type'], 'warning')

    # ------------------------------------------------------------------
    # Alta desde el formulario
    # ------------------------------------------------------------------
    def test_create_with_zero_sale_derives_it_from_native_rate(self):
        """El formulario envía venta 0 al crear: se deduce de la tasa."""
        rate = self.Rate.create({
            'name': '2026-04-07',
            'currency_id': self.usd.id,
            'company_id': self.root.id,
            'rate': 0.25,
            'rate_sale': 0.0,
        })
        self.assertAlmostEqual(rate.rate_sale, 4.0, places=3)
        self.assertAlmostEqual(rate.rate_purchase, 4.0, places=3)
