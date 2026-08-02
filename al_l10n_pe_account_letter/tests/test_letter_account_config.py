# -*- coding: utf-8 -*-

import psycopg2

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'al_l10n_pe_account_letter')
class TestLetterAccountConfig(TransactionCase):
    """
    Cubre el modelo ``l10n_pe.letter.account.config`` (mapeo de tipo de cuenta +
    tipo de letra + moneda a una cuenta contable) y, en particular, el
    constraint SQL que impide duplicados sobre la combinación
    (account_type, letter_type, currency_id, company_id).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Configuration = cls.env['l10n_pe.letter.account.config']
        cls.pen = cls.env.ref('base.PEN')
        cls.usd = cls.env.ref('base.USD')
        # l10n_pe.letter.account.config es propio del módulo: se limpia para
        # que el test no dependa de configuraciones ya cargadas en la base
        # (p.ej. por tools/account_letter_demo_data.py).
        cls.Configuration.search([]).unlink()

    def _make(self, **vals):
        defaults = {
            'account_type': 'asset_receivable',
            'letter_type': 'portfolio',
            'currency_id': self.pen.id,
        }
        defaults.update(vals)
        return self.Configuration.create(defaults)

    def test_create_minimal_record(self):
        record = self._make()
        self.assertEqual(record.account_type, 'asset_receivable')
        self.assertEqual(record.letter_type, 'portfolio')
        self.assertEqual(record.document_type, 'letter')
        self.assertEqual(record.currency_id, self.pen)
        self.assertEqual(record.company_id, self.env.company)

    def test_duplicate_combination_raises(self):
        """La constraint SQL (``models.Constraint``) rechaza duplicados de
        forma atómica: create() propaga el psycopg2.errors.UniqueViolation
        de la base (Odoo solo lo traduce a un ValidationError amigable en el
        despacho HTTP real, vía ``odoo.service.model.retrying``)."""
        self._make()
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            with self.env.cr.savepoint():
                self._make()

    def test_distinct_currency_allowed(self):
        self._make(currency_id=self.pen.id)
        record = self._make(currency_id=self.usd.id)
        self.assertEqual(record.currency_id, self.usd)

    def test_distinct_letter_type_allowed(self):
        self._make(letter_type='portfolio')
        record = self._make(letter_type='billing')
        self.assertEqual(record.letter_type, 'billing')

    def test_distinct_account_type_allowed(self):
        self._make(account_type='asset_receivable')
        record = self._make(account_type='liability_payable')
        self.assertEqual(record.account_type, 'liability_payable')

    def test_translation_dicts_match_selections(self):
        config = self.Configuration
        self.assertEqual(
            set(config.account_type_t.keys()),
            {'asset_receivable', 'liability_payable'},
        )
        self.assertEqual(
            set(config.letter_type_t.keys()),
            {'portfolio', 'billing', 'discount', 'protested'},
        )
