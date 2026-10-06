# -*- coding: utf-8 -*-
"""Glosa peruana del asiento y de sus líneas.

La glosa es el texto que SUNAT espera en la columna de descripción de los
libros del PLE. Se guarda en el asiento y, opcionalmente, línea a línea;
no debe arrastrarse al duplicar un documento (sería copiar la descripción
de otra operación a un comprobante nuevo).
"""
from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPeGloss(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', cls.company.id)],
            limit=1)
        cls.account = cls.env['account.account'].search(
            [('account_type', '=', 'expense')], limit=1)

    def _entry(self, gloss='Provisión de servicios de marzo'):
        return self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'l10n_pe_gloss': gloss,
            'line_ids': [
                Command.create({'account_id': self.account.id, 'name': 'D',
                                'debit': 100.0, 'credit': 0.0,
                                'l10n_pe_gloss': 'Glosa de la línea'}),
                Command.create({'account_id': self.account.id, 'name': 'H',
                                'debit': 0.0, 'credit': 100.0}),
            ],
        })

    def test_gloss_is_stored(self):
        """La glosa se guarda en el asiento y en la línea."""
        move = self._entry()
        self.assertEqual(move.l10n_pe_gloss, 'Provisión de servicios de marzo')
        self.assertEqual(move.line_ids[0].l10n_pe_gloss, 'Glosa de la línea')

    def test_gloss_not_copied(self):
        """Duplicar el asiento no arrastra la glosa del original."""
        move = self._entry()
        copy = move.copy()
        self.assertFalse(copy.l10n_pe_gloss)
        self.assertFalse(any(copy.line_ids.mapped('l10n_pe_gloss')))

    def test_gloss_survives_posting(self):
        """Publicar el asiento no pierde la glosa."""
        move = self._entry()
        move.action_post()
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.l10n_pe_gloss, 'Provisión de servicios de marzo')

    def test_is_pe_flag(self):
        """``l10n_pe_is_pe`` distingue los documentos de compañía peruana."""
        move = self._entry()
        self.assertEqual(move.l10n_pe_is_pe(), move.country_code == 'PE')

    def test_gloss_is_searchable(self):
        """La glosa se puede filtrar (los libros la usan como criterio)."""
        move = self._entry('GLOSA BUSCABLE PE')
        found = self.env['account.move'].search(
            [('l10n_pe_gloss', '=', 'GLOSA BUSCABLE PE')])
        self.assertIn(move, found)
