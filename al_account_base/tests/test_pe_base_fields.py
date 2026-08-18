# -*- coding: utf-8 -*-
"""Campos base de la localización peruana que alimentan los libros SUNAT."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPeBaseFields(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'CONTACTO BASE PE',
            'country_id': cls.env.ref('base.pe').id,
        })

    # ------------------------------------------------------------------
    # Establecimiento anexo
    # ------------------------------------------------------------------
    def test_annex_code_accepts_four_digits(self):
        self.partner.l10n_pe_annex_code = '0000'
        self.assertEqual(self.partner.l10n_pe_annex_code, '0000')
        self.partner.l10n_pe_annex_code = '0012'
        self.assertEqual(self.partner.l10n_pe_annex_code, '0012')

    def test_annex_code_rejects_wrong_format(self):
        for wrong in ('12', 'ABCD', '12a4'):
            with self.assertRaises(ValidationError,
                                   msg='«%s» no es un anexo válido' % wrong):
                self.partner.l10n_pe_annex_code = wrong

    def test_annex_code_can_be_empty(self):
        self.partner.l10n_pe_annex_code = False
        self.assertFalse(self.partner.l10n_pe_annex_code)

    # ------------------------------------------------------------------
    # Código SUNAT del banco
    # ------------------------------------------------------------------
    def test_bank_code_accepts_two_digits(self):
        bank = self.env['res.bank'].create({'name': 'BANCO DEMO'})
        account = self.env['res.partner.bank'].create({
            'acc_number': '00123456789',
            'partner_id': self.partner.id,
            'bank_id': bank.id,
            'l10n_pe_bank_code': '02',
        })
        self.assertEqual(account.l10n_pe_bank_code, '02')

    def test_bank_code_rejects_wrong_format(self):
        account = self.env['res.partner.bank'].create({
            'acc_number': '00987654321',
            'partner_id': self.partner.id,
        })
        for wrong in ('2', 'AB', '123'):
            with self.assertRaises(ValidationError,
                                   msg='«%s» no es un código válido' % wrong):
                account.l10n_pe_bank_code = wrong

    # ------------------------------------------------------------------
    # Naturaleza del diario
    # ------------------------------------------------------------------
    def test_journal_kind_defaults_to_movement(self):
        journal = self.env['account.journal'].create({
            'name': 'Diario base PE',
            'code': 'PEB',
            'type': 'general',
        })
        self.assertEqual(journal.l10n_pe_journal_kind, 'movement')
        self.assertFalse(journal.l10n_pe_exclude_from_books)

    def test_journal_can_be_marked_opening_and_excluded(self):
        journal = self.env['account.journal'].create({
            'name': 'Apertura PE',
            'code': 'PEA',
            'type': 'general',
            'l10n_pe_journal_kind': 'opening',
            'l10n_pe_exclude_from_books': True,
        })
        self.assertEqual(journal.l10n_pe_journal_kind, 'opening')
        self.assertTrue(journal.l10n_pe_exclude_from_books)
