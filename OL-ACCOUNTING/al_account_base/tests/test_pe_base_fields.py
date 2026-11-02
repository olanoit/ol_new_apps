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
        account = self.env['res.partner.bank'].create({
            'account_number': '00123456789',
            'partner_id': self.partner.id,
            'bank_name': 'BANCO DEMO',
            'l10n_pe_bank_code': '02',
        })
        self.assertEqual(account.l10n_pe_bank_code, '02')

    def test_bank_code_rejects_wrong_format(self):
        account = self.env['res.partner.bank'].create({
            'account_number': '00987654321',
            'partner_id': self.partner.id,
        })
        for wrong in ('2', 'AB', '123'):
            with self.assertRaises(ValidationError,
                                   msg='«%s» no es un código válido' % wrong):
                account.l10n_pe_bank_code = wrong

    def test_native_clearing_number_is_validated(self):
        """Odoo 20: escribir el clearing_number nativo también se valida."""
        account = self.env['res.partner.bank'].create({
            'account_number': '00555666777',
            'partner_id': self.partner.id,
        })
        with self.assertRaises(ValidationError):
            account.clearing_number = 'AB'
        account.clearing_number = '11'
        self.assertEqual(account.l10n_pe_bank_code, '11')

    def test_foreign_clearing_number_not_validated(self):
        """Una cuenta extranjera conserva su número de ruta sin la tabla del PLE."""
        partner = self.env['res.partner'].create({
            'name': 'PROVEEDOR US', 'country_id': self.env.ref('base.us').id})
        account = self.env['res.partner.bank'].create({
            'account_number': '000123456789',
            'partner_id': partner.id,
            'clearing_number': '021000021',
        })
        self.assertEqual(account.clearing_number, '021000021')

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

    # ------------------------------------------------------------------
    # Documento de identidad en el formulario
    # ------------------------------------------------------------------
    def test_dni_is_always_shown_for_peruvian_contacts(self):
        """Sin el selector de Odoo 19, el DNI se ofrece siempre bajo el RUC;
        los demás documentos siguen en el «+»."""
        metadata = self.partner.available_additional_identifiers_metadata
        self.assertEqual(metadata['PE_DNI'].get('display_optional'), 'show')
        self.assertFalse(metadata['PE_CE'].get('display_optional'))
        foreign = self.env['res.partner'].create({
            'name': 'CONTACTO EXTRANJERO', 'country_id': self.env.ref('base.cl').id})
        self.assertNotIn('PE_DNI', foreign.available_additional_identifiers_metadata)

    def test_dni_typed_in_the_form_identifies_the_contact(self):
        partner = self.env['res.partner'].create({
            'name': 'PERSONA CON DNI', 'country_id': self.env.ref('base.pe').id,
            'additional_identifiers': {'PE_DNI': '40000004'}})
        self.assertEqual(partner.l10n_pe_sunat_id_code, '1')
        self.assertEqual(partner.l10n_pe_document_label, 'DNI')
