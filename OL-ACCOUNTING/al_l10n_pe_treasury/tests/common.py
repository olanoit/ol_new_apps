# -*- coding: utf-8 -*-
from datetime import date

from odoo import Command
from odoo.tests.common import TransactionCase
from odoo.addons.al_account_base.tests.common import use_pe_company

TODAY = date(2026, 3, 16)
USD_RATE = 3.70


class TreasuryCommon(TransactionCase):
    """Compañía peruana con un banco en soles, uno en dólares, una caja y un
    proveedor con dos facturas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.pen = cls.company.currency_id
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id), ('company_id', 'in', (False, cls.company.root_id.id)),
            ('name', '>=', date(2026, 1, 1))]).unlink()
        cls.env['res.currency.rate'].create({
            'currency_id': cls.usd.id, 'company_id': cls.company.root_id.id, 'name': date(2026, 1, 1),
            'inverse_company_rate': USD_RATE})
        Journal = cls.env['account.journal']
        cls.bank_pen = Journal.create({'name': 'BCP soles test', 'code': 'TBP', 'type': 'bank',
                                       'company_id': cls.company.id})
        cls.bank_pen2 = Journal.create({'name': 'BBVA soles test', 'code': 'TBB', 'type': 'bank',
                                        'company_id': cls.company.id})
        cls.bank_usd = Journal.create({'name': 'BCP dólares test', 'code': 'TBU', 'type': 'bank',
                                       'currency_id': cls.usd.id, 'company_id': cls.company.id})
        cls.cash = Journal.create({'name': 'Caja test', 'code': 'TCJ', 'type': 'cash',
                                   'company_id': cls.company.id})
        # Cuentas de pendientes propias: así los pagos tienen asiento y se ven en tránsito.
        Account = cls.env['account.account']
        cls.outstanding_in = Account.create({'name': 'Cobros pendientes (prueba tesorería)', 'code': '104191',
                                             'account_type': 'asset_current', 'reconcile': True})
        cls.outstanding_out = Account.create({'name': 'Pagos pendientes (prueba tesorería)', 'code': '104192',
                                              'account_type': 'asset_current', 'reconcile': True})
        for journal in (cls.bank_pen, cls.bank_pen2, cls.bank_usd, cls.cash):
            journal.inbound_payment_method_line_ids.payment_account_id = cls.outstanding_in
            journal.outbound_payment_method_line_ids.payment_account_id = cls.outstanding_out
        cls.purchase_journal = Journal.create({'name': 'Compras tesorería', 'code': 'TCP', 'type': 'purchase',
                                               'l10n_latam_use_documents': False, 'company_id': cls.company.id})
        cls.vendor = cls.env['res.partner'].create({'name': 'PROVEEDOR TESORERÍA SAC', 'vat': '20100070970'})
        cls.vendor2 = cls.env['res.partner'].create({'name': 'SEGUNDO PROVEEDOR SAC', 'vat': '20100047218'})
        cls.group_user = cls.env.ref('al_l10n_pe_treasury.group_treasury_user')
        cls.group_approver = cls.env.ref('al_l10n_pe_treasury.group_treasury_approver')
        cls.group_manager = cls.env.ref('al_l10n_pe_treasury.group_treasury_manager')
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)]}
        cls.preparer = Users.create({'name': 'Preparador', 'login': 'treasury_preparer',
                                     'group_ids': [Command.set([cls.group_user.id])], **common})
        cls.approver = Users.create({'name': 'Aprobador', 'login': 'treasury_approver',
                                     'group_ids': [Command.set([cls.group_approver.id])], **common})
        cls.manager = Users.create({'name': 'Administrador', 'login': 'treasury_manager',
                                    'group_ids': [Command.set([cls.group_manager.id])], **common})

    @classmethod
    def _bill(cls, partner, amount, due, currency=None):
        bill = cls.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': partner.id, 'invoice_date': date(2026, 3, 1),
            'invoice_date_due': due, 'currency_id': (currency or cls.pen).id,
            'journal_id': cls.purchase_journal.id,
            'invoice_line_ids': [Command.create({'name': 'Servicio', 'quantity': 1, 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        bill.action_post()
        return bill

    @staticmethod
    def _payable_line(bill):
        return bill.line_ids.filtered(lambda l: l.account_id.account_type == 'liability_payable')

    def _post_entry(self, journal_account, amount, day=date(2026, 3, 1), currency=None, amount_currency=None):
        """Asiento directo en la cuenta del banco (saldo inicial)."""
        equity = self.env['account.account'].search([
            *self.env['account.account']._check_company_domain(self.company),
            ('account_type', '=', 'equity')], limit=1)
        misc = self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.company), ('type', '=', 'general')], limit=1)
        currency = currency or self.pen
        amount_currency = amount if amount_currency is None else amount_currency
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': misc.id, 'date': day,
            'line_ids': [
                Command.create({'name': 'Saldo inicial', 'account_id': journal_account.id, 'balance': amount,
                                'currency_id': currency.id, 'amount_currency': amount_currency}),
                Command.create({'name': 'Saldo inicial', 'account_id': equity.id, 'balance': -amount,
                                'currency_id': currency.id, 'amount_currency': -amount_currency}),
            ],
        })
        move.action_post()
        return move
