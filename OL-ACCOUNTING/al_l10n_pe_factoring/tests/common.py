# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.addons.al_account_base.tests.common import use_pe_company


class FactoringCommon(TransactionCase):
    """Compañía peruana, diarios, cliente y factor de las pruebas de factoring."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.today = fields.Date.context_today(cls.env['res.users'])
        Account = cls.env['account.account'].with_company(cls.company)
        cls.income = Account.search([('account_type', '=', 'income')], limit=1)
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas factoring test', 'code': 'VFTS', 'type': 'sale',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False})
        cls.bank_journal = cls.env['account.journal'].create({
            'name': 'Banco factoring test', 'code': 'BFTS', 'type': 'bank',
            'company_id': cls.company.id})
        cls.misc_journal = cls.env['account.journal'].create({
            'name': 'Factoring test', 'code': 'FTS', 'type': 'general',
            'company_id': cls.company.id})
        cls.customer = cls.env['res.partner'].create({'name': 'CLIENTE FACTORING SAC', 'vat': '20100070970'})
        cls.factor = cls.env['res.partner'].create({'name': 'FACTOR CAPITAL SAC', 'vat': '20100047218'})
        cls.Config = cls.env['l10n_pe.factoring.account.config']
        for modality in ('without_recourse', 'with_recourse'):
            cls.assertTrue(cls, cls.Config._l10n_pe_get(cls.company, modality, cls.company.currency_id))

    # ------------------------------------------------------------------
    # Ayudantes
    # ------------------------------------------------------------------
    def _invoice(self, amount=1000.0, currency=None):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.customer.id,
            'journal_id': self.sale_journal.id, 'invoice_date': self.today,
            'currency_id': (currency or self.company.currency_id).id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio', 'quantity': 1, 'price_unit': amount,
                'account_id': self.income.id, 'tax_ids': [(6, 0, [])]})],
        })
        move.action_post()
        return move

    def _operation(self, invoices, modality='without_recourse', percent=90.0, currency=None):
        return self.env['l10n_pe.factoring'].create({
            'factor_id': self.factor.id, 'modality': modality, 'journal_id': self.misc_journal.id,
            'currency_id': (currency or self.company.currency_id).id,
            'default_advance_percent': percent,
            'line_ids': [(0, 0, {'move_id': inv.id, 'advance_percent': percent}) for inv in invoices],
        })

    def _wizard(self, operation, kind, **vals):
        wizard = self.env['l10n_pe.factoring.wizard'].create(dict({
            'factoring_id': operation.id, 'operation': kind, 'date': self.today,
            'bank_journal_id': self.bank_journal.id}, **vals))
        if kind in ('settle', 'repurchase', 'write_off') and 'line_ids' not in vals:
            wizard.line_ids = operation.line_ids.filtered(lambda l: l.state == 'assigned')
        wizard.action_apply()
        return wizard

    def _balance(self, operation, account, partner=None):
        lines = operation.move_ids.filtered(lambda m: m.state == 'posted').line_ids.filtered(
            lambda l: l.account_id == account and (not partner or l.partner_id == partner))
        return self.company.currency_id.round(sum(lines.mapped('balance')))

    def _assert_balanced(self, operation):
        for move in operation.move_ids:
            self.assertFalse(self.company.currency_id.round(sum(move.line_ids.mapped('balance'))),
                             'el asiento %s cuadra' % move.ref)
