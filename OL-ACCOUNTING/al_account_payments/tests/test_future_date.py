# -*- coding: utf-8 -*-
"""Aviso (no bloqueo) de pago con fecha futura (R6)."""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged
from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestFutureDatePayment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'CLIENTE FECHA FUTURA SAC', 'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
            'country_id': cls.env.ref('base.pe').id})
        cls.bank_journal = cls.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1)
        cls.sale_journal = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
        cls.tax_sale = cls.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'), ('company_id', '=', company.id),
            ('l10n_pe_edi_tax_code', '=', '1000')], limit=1)
        cls.income = cls.env['account.account'].search([('account_type', '=', 'income')], limit=1)

    def _invoice(self):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id, 'invoice_date': '2026-03-15',
            'invoice_line_ids': [Command.create({
                'name': 'Servicio', 'quantity': 1, 'price_unit': 1180.0,
                'tax_ids': [Command.set(self.tax_sale.ids)], 'account_id': self.income.id})]})
        move.action_post()
        return move

    def _payment(self, date):
        return self.env['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer',
            'partner_id': self.partner.id, 'amount': 100.0,
            'journal_id': self.bank_journal.id, 'date': date})

    def test_future_date_warns_but_posts(self):
        tomorrow = fields.Date.context_today(self.env.user) + timedelta(days=1)
        payment = self._payment(tomorrow)
        self.assertTrue(payment.l10n_pe_future_date)
        payment.action_post()
        self.assertNotEqual(payment.state, 'draft', 'el aviso no bloquea')
        self.assertIn('fecha futura', payment.message_ids[:1].body)

    def test_today_does_not_warn(self):
        payment = self._payment(fields.Date.context_today(self.env.user))
        self.assertFalse(payment.l10n_pe_future_date)

    def test_register_wizard_flags_future_date(self):
        invoice = self._invoice()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'journal_id': self.bank_journal.id,
                  'payment_date': fields.Date.context_today(self.env.user) + timedelta(days=3)})
        self.assertTrue(wizard.l10n_pe_future_date)
