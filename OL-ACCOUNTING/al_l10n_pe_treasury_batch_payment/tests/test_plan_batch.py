# -*- coding: utf-8 -*-
from datetime import date

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestPlanBatch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        pen = cls.env.ref('base.PEN')
        bcp = cls.env['res.bank'].create({'name': 'BCP (prueba lote)', 'l10n_pe_batch_format': 'bcp'})
        account = cls.env['res.partner.bank'].create({
            'partner_id': cls.company.partner_id.id, 'bank_id': bcp.id, 'account_number': '191-7654321-0-99',
            'currency_id': pen.id})
        cls.journal = cls.env['account.journal'].create({
            'name': 'BCP lote (prueba)', 'code': 'TBLT', 'type': 'bank', 'currency_id': pen.id,
            'bank_account_id': account.id})
        cls.method_line = cls.journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'pe_bank_txt')
        purchase = cls.env['account.journal'].create({
            'name': 'Compras lote', 'code': 'TCLT', 'type': 'purchase', 'l10n_latam_use_documents': False})
        ruc = cls.env.ref('l10n_pe.it_RUC')
        cls.bills = cls.env['account.move']
        for name, vat, number, amount in (('Proveedor lote uno', '20100070970', '193-1111111-0-11', 800.0),
                                          ('Proveedor lote dos', '20131312955', '193-2222222-0-22', 450.0)):
            partner = cls.env['res.partner'].create({
                'name': name, 'is_company': True, 'vat': vat, 'l10n_latam_identification_type_id': ruc.id,
                'country_id': cls.env.ref('base.pe').id})
            cls.env['res.partner.bank'].create({'partner_id': partner.id, 'bank_id': bcp.id, 'account_number': number,
                                                'allow_out_payment': True})
            bill = cls.env['account.move'].create({
                'move_type': 'in_invoice', 'partner_id': partner.id, 'journal_id': purchase.id,
                'invoice_date': date(2026, 10, 1), 'invoice_date_due': date(2026, 10, 15),
                'invoice_line_ids': [Command.create({'name': 'Servicio', 'price_unit': amount,
                                                     'tax_ids': [Command.clear()]})]})
            bill.action_post()
            cls.bills |= bill

    def test_plan_creates_batch(self):
        self.assertTrue(self.method_line)
        plan = self.env['l10n_pe.treasury.payment.plan'].create({
            'journal_id': self.journal.id, 'date': date(2026, 10, 15),
            'payment_method_line_id': self.method_line.id})
        self.env['l10n_pe.treasury.payment.plan.propose'].create({
            'plan_id': plan.id, 'date_due': date(2026, 10, 31),
            'partner_ids': [Command.set(self.bills.partner_id.ids)]}).action_propose()
        self.assertEqual(plan.line_ids.move_id, self.bills)
        self.company.l10n_pe_treasury_plan_approval_amount = 100000.0
        plan.action_submit()
        self.assertEqual(plan.state, 'approved')
        plan.action_pay()
        self.assertTrue(plan.batch_payment_id)
        self.assertEqual(plan.batch_payment_id.payment_ids, plan.payment_ids)
        self.assertEqual(len(plan.payment_ids), 2)
        self.assertEqual(plan.payment_ids.payment_method_line_id, self.method_line)
