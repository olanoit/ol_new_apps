# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'al_l10n_pe_account_letter')
class TestLetter(TransactionCase):
    """
    Tests del modelo ``l10n_pe.letter`` (canje de letras): valores por
    defecto, cómputo del dominio de diarios y trazabilidad vía chatter.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Letter = cls.env['l10n_pe.letter']
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Test PE'})

    def _create_letter(self, **vals):
        defaults = {
            'partner_id': self.partner.id,
            'type': 'out_invoice',
            'invoice_date': date(2026, 1, 15),
            'number_letter': 3,
            'range_date': 30,
        }
        defaults.update(vals)
        return self.Letter.create(defaults)

    def test_default_state_is_draft(self):
        letter = self._create_letter()
        self.assertEqual(letter.state, 'draft')

    def test_default_type_payment_total(self):
        letter = self._create_letter()
        self.assertEqual(letter.type_payment, 'total')

    def test_company_currency_is_related(self):
        letter = self._create_letter()
        self.assertEqual(
            letter.company_currency_id, letter.company_id.currency_id
        )

    def test_state_field_is_tracked(self):
        """La trazabilidad de eventos se apoya en mail.thread (state tiene
        tracking=True) en vez de campos-sombra de fecha/usuario manuales."""
        self.assertTrue(self.Letter._fields['state'].tracking)

    def test_domain_letter_ids_filters_by_company(self):
        """El dominio de diarios excluye diarios de otras compañías."""
        letter = self._create_letter(type='out_invoice')
        for journal in letter.domain_letter_ids:
            self.assertEqual(journal.company_id, self.env.company)

    def test_state_selection_values(self):
        selection = dict(self.Letter._fields['state'].selection)
        self.assertEqual(
            set(selection.keys()),
            {'draft', 'checked', 'redeemed', 'banked', 'cancel'},
        )

    def test_type_selection_values(self):
        selection = dict(self.Letter._fields['type'].selection)
        self.assertEqual(
            set(selection.keys()), {'out_invoice', 'in_invoice'}
        )
