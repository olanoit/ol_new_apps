# -*- coding: utf-8 -*-
import base64
from datetime import date

from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models import bank_formats
from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestBatchPayment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.pen = cls.env.ref('base.PEN')
        Bank = cls.env['res.bank']
        cls.bcp = Bank.create({'name': 'BCP (test)', 'l10n_pe_batch_format': 'bcp'})
        cls.bbva = Bank.create({'name': 'BBVA (test)', 'l10n_pe_batch_format': 'bbva'})
        cls.ibk = Bank.create({'name': 'Interbank (test)', 'l10n_pe_batch_format': 'interbank'})
        ruc = cls.env.ref('l10n_pe.it_RUC')

        def journal(name, code, bank, account):
            acc = cls.env['res.partner.bank'].create({
                'partner_id': cls.company.partner_id.id, 'bank_id': bank.id,
                'acc_number': account, 'currency_id': cls.pen.id})
            return cls.env['account.journal'].create({
                'name': name, 'code': code, 'type': 'bank', 'currency_id': cls.pen.id,
                'bank_account_id': acc.id})

        cls.j_bcp = journal('BCP soles (test)', 'TBCP', cls.bcp, '191-1234567-0-11')
        cls.j_bbva = journal('BBVA soles (test)', 'TBBV', cls.bbva, '0011-0123-0100012345')

        def supplier(name, vat, bank, account, cci=False):
            partner = cls.env['res.partner'].create({
                'name': name, 'is_company': True, 'vat': vat,
                'l10n_latam_identification_type_id': ruc.id,
                'country_id': cls.env.ref('base.pe').id})
            bank_account = cls.env['res.partner.bank'].create({
                'partner_id': partner.id, 'bank_id': bank.id, 'acc_number': account,
                'l10n_pe_cci': cci, 'allow_out_payment': True})
            return partner, bank_account

        cls.s1 = supplier('Proveedor Uno (test)', '20100070970', cls.bcp, '193-7654321-0-22',
                          '00219300765432102211')
        cls.s2 = supplier('Proveedor Dos (test)', '20131312955', cls.bbva, '0011-0456-0200098765',
                          '01145600020009876512')
        cls.s3 = supplier('Proveedor Tres (test)', '20100047218', cls.ibk, '200-3001234567',
                          '00320000300123456713')

    def _payments(self, journal, amounts=(1000.0, 250.5, 80.0), suppliers=None):
        line = journal.outbound_payment_method_line_ids.filtered(
            lambda l: l.code == 'pe_bank_txt')
        self.assertTrue(line, 'el diario ofrece el pago masivo')
        payments = self.env['account.payment']
        for (partner, bank), value in zip(suppliers or (self.s1, self.s2, self.s3), amounts):
            payments |= self.env['account.payment'].create({
                'payment_type': 'outbound', 'partner_type': 'supplier',
                'partner_id': partner.id, 'partner_bank_id': bank.id, 'amount': value,
                'journal_id': journal.id, 'payment_method_line_id': line.id,
                'date': date(2026, 10, 12)})
        payments.action_post()
        return payments

    def _batch(self, journal, payments):
        return self.env['account.batch.payment'].create({
            'journal_id': journal.id, 'batch_type': 'outbound',
            'payment_method_id': self.env.ref(
                'al_l10n_pe_batch_payment.account_payment_method_pe_bank_txt').id,
            'payment_ids': [(6, 0, payments.ids)]})

    def _export(self, batch):
        batch.validate_batch()
        self.assertTrue(batch.export_file)
        return base64.b64decode(batch.export_file).decode('latin-1').split('\r\n')[:-1]

    def test_bcp_file_with_three_suppliers_in_three_banks(self):
        batch = self._batch(self.j_bcp, self._payments(self.j_bcp))
        rows = self._export(batch)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0][:7], '1000003')
        self.assertIn('00000000001330.50', rows[0], 'total con punto decimal')
        self.assertTrue(rows[1].startswith('2C' + '1937654321022'), 'mismo banco: su cuenta')
        self.assertTrue(rows[2].startswith('2B01145600020009876512'), 'otro banco: CCI')
        self.assertEqual((batch.l10n_pe_export_count, batch.l10n_pe_export_total), (3, 1330.5))
        self.assertTrue(batch.export_filename.startswith('BCP_PEN_TBCP_'))

    def test_one_file_per_bank(self):
        bcp = self._batch(self.j_bcp, self._payments(self.j_bcp))
        bbva = self._batch(self.j_bbva, self._payments(self.j_bbva))
        bcp_rows, bbva_rows = self._export(bcp), self._export(bbva)
        self.assertTrue(bbva_rows[0].startswith('700'))
        self.assertEqual(len(bbva_rows), 4)
        self.assertEqual(bbva_rows[0][3:23], '001101230100012345'.ljust(20), 'cuenta de cargo')
        self.assertTrue(bbva_rows[2].startswith('002R20131312955 P'), 'mismo banco BBVA: su cuenta')
        self.assertTrue(bbva_rows[1].startswith('002R20100070970 I'), 'otro banco: CCI')
        self.assertNotEqual(bcp.export_filename, bbva.export_filename)

    def test_supplier_without_cci_is_rejected(self):
        partner, bank = self.s3
        bank.l10n_pe_cci = False
        batch = self._batch(self.j_bcp, self._payments(self.j_bcp, (100.0,), [self.s3]))
        with self.assertRaises(RedirectWarning):
            batch.validate_batch()

    def test_invalid_cci(self):
        with self.assertRaises(ValidationError):
            self.s2[1].l10n_pe_cci = '0114560002000987651'

    def test_currency_mismatch(self):
        partner, bank = self.s1
        bank.currency_id = self.env.ref('base.USD')
        batch = self._batch(self.j_bcp, self._payments(self.j_bcp, (100.0,), [self.s1]))
        errors = batch.check_payments_for_errors()
        self.assertTrue(any('otra moneda' in error['title'] for error in errors))

    def test_journal_without_format(self):
        self.bcp.l10n_pe_batch_format = False
        batch = self._batch(self.j_bcp, self._payments(self.j_bcp, (100.0,), [self.s1]))
        errors = batch.check_payments_for_errors()
        self.assertTrue(any('formato' in error['title'] for error in errors))

    def test_pure_helpers(self):
        self.assertEqual(bank_formats.clean_text('Ñandú & Cía.'), 'Nandu  Cia')
        self.assertEqual(bank_formats.amount(1234.5, 10), '0000123450')
        self.assertEqual(bank_formats.amount(1234.5, 10, point=True), '0001234.50')
        header = {'currency': 'PEN', 'payment_date': date(2026, 10, 12), 'charge_acc': '123',
                  'company_name': 'X', 'company_vat': '20100070970', 'reference': 'L',
                  'options': {}, 'now': None}
        line = {'doc_type': '6', 'doc_number': '20131312955', 'name': 'Y', 'account': '1' * 20,
                'is_cci': True, 'account_kind': 'checking', 'amount': 10.0, 'reference': 'F1'}
        for key, (builder, _label) in bank_formats.FORMATS.items():
            if key == 'interbank':
                continue  # usa la hora local del lote
            text = builder(header, [line])
            self.assertTrue(text.endswith('\r\n'), key)
