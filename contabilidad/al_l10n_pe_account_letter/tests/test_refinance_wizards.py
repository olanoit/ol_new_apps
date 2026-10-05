# -*- coding: utf-8 -*-

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'al_l10n_pe_account_letter')
class TestRefinanceWizards(TransactionCase):
    """
    Tests de los asistentes de refinanciación de canjes de letras:
    individual (``l10n_pe.letter.refinance.wizard``) y masiva
    (``l10n_pe.letter.refinance.massive.wizard``).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Letter = cls.env['l10n_pe.letter']
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Test PE'})
        cls.other_partner = cls.env['res.partner'].create({'name': 'Otro cliente PE'})

    def _make_letter(self, partner=None):
        return self.Letter.create({
            'partner_id': (partner or self.partner).id,
            'type': 'out_invoice',
            'invoice_date': date(2026, 1, 15),
        })

    def test_individual_refinance_default_fields(self):
        letter = self._make_letter()
        wizard = self.env['l10n_pe.letter.refinance.wizard'].create({
            'letter_id': letter.id,
            'refinance_date': date(2026, 2, 15),
        })
        self.assertEqual(wizard.letter_id, letter)
        self.assertEqual(wizard.refinance_date, date(2026, 2, 15))

    def test_massive_wizard_requires_active_ids(self):
        with self.assertRaises(UserError):
            self.env['l10n_pe.letter.refinance.massive.wizard'].with_context(
                active_ids=[]
            ).create({})

    def test_massive_wizard_picks_up_first_letter_metadata(self):
        letter = self._make_letter()
        wizard = self.env['l10n_pe.letter.refinance.massive.wizard'].with_context(
            active_ids=letter.ids,
            default_refinance_date=date(2026, 3, 1),
        ).create({})
        self.assertIn(letter, wizard.letter_ids)
        self.assertEqual(wizard.partner_id, letter.partner_id)
        self.assertEqual(wizard.refinance_date, date(2026, 3, 1))

    def test_massive_wizard_action_confirm_requires_selection(self):
        letter = self._make_letter()
        wizard = self.env['l10n_pe.letter.refinance.massive.wizard'].with_context(
            active_ids=letter.ids,
        ).create({})
        # Forzamos que no haya letras seleccionadas para verificar el guard.
        wizard.letter_ids = [(5, 0, 0)]
        with self.assertRaises(UserError):
            wizard.action_confirm()
