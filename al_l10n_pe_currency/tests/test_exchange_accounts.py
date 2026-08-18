# -*- coding: utf-8 -*-
"""Cuentas de diferencia de cambio del plan peruano (676 / 776).

Las asigna la localización oficial al cargar el plan; el hook de este módulo
solo cubre el caso de que falten. Lo que se fija aquí es que **no toque nada
cuando ya están puestas**: ambos campos dependen de la compañía activa y una
escritura en el contexto equivocado las borra.
"""
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.al_l10n_pe_currency.hooks import (
    EXCHANGE_ACCOUNTS, _l10n_pe_assign_exchange_accounts)


@tagged('post_install', '-at_install')
class TestExchangeAccounts(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']

    def _company(self):
        """La compañía en su propio contexto: sin esto los campos van vacíos."""
        return self.company.with_company(self.company)

    # ------------------------------------------------------------------
    # Configuración de la localización
    # ------------------------------------------------------------------
    def test_localization_assigns_the_accounts(self):
        """El plan peruano trae las 676 y 776 ya asignadas."""
        company = self._company()
        self.assertTrue(company.expense_currency_exchange_account_id,
                        'falta la cuenta de pérdida de cambio')
        self.assertTrue(company.income_currency_exchange_account_id,
                        'falta la cuenta de ganancia de cambio')

    def test_accounts_are_the_expected_ones(self):
        company = self._company()
        self.assertTrue(
            company.expense_currency_exchange_account_id.code.startswith('676'),
            'la pérdida de cambio va a la 676 del PCGE')
        self.assertTrue(
            company.income_currency_exchange_account_id.code.startswith('776'),
            'la ganancia de cambio va a la 776 del PCGE')

    # ------------------------------------------------------------------
    # Comportamiento del hook
    # ------------------------------------------------------------------
    def test_hook_does_nothing_when_already_set(self):
        """Con las cuentas puestas, el hook no debe tocar la configuración."""
        company = self._company()
        before = (company.income_currency_exchange_account_id,
                  company.expense_currency_exchange_account_id)

        repaired = _l10n_pe_assign_exchange_accounts(self.env)

        self.assertNotIn(self.company, repaired)
        company.invalidate_recordset()
        self.assertEqual(company.income_currency_exchange_account_id, before[0])
        self.assertEqual(company.expense_currency_exchange_account_id, before[1])

    def test_hook_restores_missing_accounts(self):
        """Si faltan, las repone con las del plan."""
        company = self._company()
        expected = (company.income_currency_exchange_account_id,
                    company.expense_currency_exchange_account_id)
        company.write({field: False for field in EXCHANGE_ACCOUNTS})
        self.assertFalse(company.income_currency_exchange_account_id)

        repaired = _l10n_pe_assign_exchange_accounts(self.env)

        self.assertIn(self.company, repaired)
        company.invalidate_recordset()
        self.assertEqual(company.income_currency_exchange_account_id, expected[0])
        self.assertEqual(company.expense_currency_exchange_account_id, expected[1])

    def test_hook_repairs_only_what_is_missing(self):
        """Reponer una no debe alterar la otra."""
        company = self._company()
        income = company.income_currency_exchange_account_id
        company.write({'expense_currency_exchange_account_id': False})

        _l10n_pe_assign_exchange_accounts(self.env)

        company.invalidate_recordset()
        self.assertEqual(company.income_currency_exchange_account_id, income,
                         'la cuenta que ya estaba no debe cambiar')
        self.assertTrue(company.expense_currency_exchange_account_id)

    def test_hook_is_idempotent(self):
        """Ejecutarlo dos veces seguidas no cambia nada la segunda."""
        _l10n_pe_assign_exchange_accounts(self.env)
        repaired = _l10n_pe_assign_exchange_accounts(self.env)
        self.assertNotIn(self.company, repaired)
