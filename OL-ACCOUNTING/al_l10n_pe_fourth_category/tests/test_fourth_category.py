# -*- coding: utf-8 -*-
"""Retención de renta de 4.ª categoría en recibos por honorarios."""
import base64
from datetime import timedelta

from stdnum.pe import ruc as stdnum_ruc

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def _ruc(body):
    return body + stdnum_ruc.calc_check_digit(body)


@tagged('post_install', '-at_install')
class TestFourthCategory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if cls.company.account_fiscal_country_id.code != 'PE':
            cls.skipTest(cls, 'La compañía de prueba no es peruana')
        cls.company.write({'l10n_pe_fourth_category_agent': True,
                           'l10n_pe_fourth_category_rate': 8.0,
                           'l10n_pe_fourth_category_threshold': 1500.0})
        cls.receipt_type = cls.env.ref('l10n_pe.document_type03')
        cls.provider = cls.env['res.partner'].create({
            'name': 'QUISPE ROJAS ANA (test 4ta)', 'country_id': cls.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
            'vat': _ruc('1047382956'),
        })
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'purchase'), ('company_id', '=', cls.company.id)], limit=1)
        cls.today = fields.Date.context_today(cls.env['account.move'])
        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'), ('company_id', '=', cls.company.id)], limit=1)

    def _receipt(self, amount, currency=None, number='E001-123', date=None, post=True):
        move = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.provider.id,
            'journal_id': self.journal.id,
            'invoice_date': date or self.today,
            'l10n_latam_document_type_id': self.receipt_type.id,
            'l10n_latam_document_number': number,
            'currency_id': (currency or self.company.currency_id).id,
            'invoice_line_ids': [(0, 0, {'name': 'Asesoría contable', 'quantity': 1,
                                         'price_unit': amount, 'tax_ids': [(6, 0, [])]})],
        })
        if post:
            move.action_post()
        return move

    def test_withheld_above_threshold(self):
        move = self._receipt(2000.0)
        self.assertTrue(move.l10n_pe_fourth_category_receipt)
        self.assertEqual(move.l10n_pe_fourth_category_status, 'withheld')
        self.assertAlmostEqual(move.l10n_pe_fourth_category_amount, 160.0)
        self.assertAlmostEqual(move.amount_residual, 1840.0)
        tax_line = move.line_ids.filtered(lambda l: l.tax_line_id.l10n_pe_fourth_category)
        self.assertEqual(tax_line.account_id, self.company._l10n_pe_fourth_category_account())
        self.assertEqual(tax_line.account_id.code[:5], '40172')

    def test_not_withheld_up_to_threshold(self):
        move = self._receipt(1500.0)
        self.assertEqual(move.l10n_pe_fourth_category_status, 'under_threshold')
        self.assertFalse(move.l10n_pe_fourth_category_amount)
        self.assertAlmostEqual(move.amount_residual, 1500.0)

    def test_draft_change_removes_and_adds_tax(self):
        move = self._receipt(2000.0, post=False)
        self.assertTrue(move.invoice_line_ids.tax_ids.filtered('l10n_pe_fourth_category'))
        move.invoice_line_ids.price_unit = 900.0
        move.write({'invoice_date': self.today})
        self.assertFalse(move.invoice_line_ids.tax_ids.filtered('l10n_pe_fourth_category'))
        move.invoice_line_ids.price_unit = 3000.0
        move.action_post()
        self.assertAlmostEqual(move.l10n_pe_fourth_category_amount, 240.0)

    def test_foreign_currency_threshold_in_soles(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        self.env['res.currency.rate'].create({
            'name': self.today, 'currency_id': usd.id, 'company_id': self.company.id,
            'inverse_company_rate': 3.75})
        move = self._receipt(500.0, currency=usd)  # S/ 1 875
        self.assertEqual(move.l10n_pe_fourth_category_status, 'withheld')
        self.assertAlmostEqual(move.l10n_pe_fourth_category_amount, 150.0, places=1)

    def test_suspension(self):
        suspension = self.env['l10n_pe.fourth.category.suspension'].create({
            'partner_id': self.provider.id, 'number': '1609-0001',
            'date_issued': self.today - timedelta(days=1)})
        self.assertEqual(suspension.date_from, self.today)
        self.assertEqual(suspension.date_to.month, 12)
        move = self._receipt(5000.0)
        self.assertEqual(move.l10n_pe_fourth_category_status, 'suspended')
        self.assertEqual(move.l10n_pe_fourth_category_suspension_id, suspension)
        self.assertFalse(move.l10n_pe_fourth_category_amount)
        self.assertTrue(self.provider.l10n_pe_fourth_category_suspended)

    def test_later_suspension_keeps_posted_status(self):
        move = self._receipt(4000.0, number='E001-90')
        self.assertEqual(move.l10n_pe_fourth_category_status, 'withheld')
        self.env['l10n_pe.fourth.category.suspension'].create({
            'partner_id': self.provider.id, 'number': '1609-0010',
            'date_issued': self.today - timedelta(days=5)})
        move.invalidate_recordset()
        self.assertEqual(move.l10n_pe_fourth_category_status, 'withheld')
        self.assertAlmostEqual(move.l10n_pe_fourth_category_amount, 320.0)
        draft = self._receipt(4000.0, number='E001-91', post=False)
        draft.action_post()
        self.assertEqual(draft.l10n_pe_fourth_category_status, 'suspended')
        self.assertFalse(draft.l10n_pe_fourth_category_amount)

    def test_suspension_rules_from_next_day(self):
        self.env['l10n_pe.fourth.category.suspension'].create({
            'partner_id': self.provider.id, 'number': '1609-0002', 'date_issued': self.today})
        move = self._receipt(5000.0)
        self.assertEqual(move.l10n_pe_fourth_category_status, 'withheld')
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.fourth.category.suspension'].create({
                'partner_id': self.provider.id, 'number': '1609-0003',
                'date_issued': self.today + timedelta(days=3)})

    def test_company_not_agent(self):
        self.company.l10n_pe_fourth_category_agent = False
        move = self._receipt(5000.0)
        self.assertEqual(move.l10n_pe_fourth_category_status, 'not_agent')
        self.assertFalse(move.l10n_pe_fourth_category_amount)

    def _pay(self, move):
        # Diario explícito: el que propone el asistente puede ser uno sin
        # cuenta de pagos pendientes (p. ej. el del pago masivo), cuyo pago
        # en Odoo 19 no genera asiento ni concilia el recibo.
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids).create({
                'payment_date': self.today, 'journal_id': self.bank_journal.id})._create_payments()

    def test_monthly_report_and_txt(self):
        move = self._receipt(2000.0, number='E001-45')
        under = self._receipt(800.0, number='E001-46')
        unpaid = self._receipt(3000.0, number='E001-47')
        self._pay(move)
        self._pay(under)
        report = self.env['l10n_pe.fourth.category.report'].create({
            'year': self.today.year, 'month': str(self.today.month)})
        report.action_compute()
        # Solo los recibos de este prestador (la base puede tener otros del mes).
        own = report.line_ids.filtered(lambda l: l.move_id.partner_id == self.provider)
        self.assertEqual(own.move_id, move | under)
        self.assertNotIn(unpaid, report.line_ids.move_id)
        self.assertAlmostEqual(sum(own.mapped('amount_withheld')), 160.0)
        self.assertAlmostEqual(report.amount_withheld, sum(report.line_ids.mapped('amount_withheld')))
        report.action_export_txt()
        self.assertEqual(report.filename, '0601%04d%02d%s.4ta' % (
            self.today.year, self.today.month, self.company.vat))
        lines = base64.b64decode(report.file).decode().splitlines()
        first = [l for l in lines if '|45|' in l][0].split('|')
        self.assertEqual(first[:5], ['06', self.provider.vat, 'R', 'E001', '45'])
        self.assertEqual(first[5], '2000.00')
        self.assertEqual(first[6], self.today.strftime('%d/%m/%Y'))
        self.assertEqual(first[8:11], ['1', '3', ''])
        second = [l for l in lines if '|46|' in l][0].split('|')
        self.assertEqual(second[8], '0')

    def test_certificate(self):
        move = self._receipt(2500.0, number='E001-77')
        self._pay(move)
        wizard = self.env['l10n_pe.fourth.category.certificate'].create({
            'year': self.today.year, 'partner_ids': [(6, 0, self.provider.ids)]})
        data = wizard._certificate_data()
        self.assertEqual(data[self.provider][0][0], move)
        self.assertAlmostEqual(data[self.provider][0][3], 200.0)
        html, _ = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_fourth_category.action_report_fourth_category_certificate',
            self.provider.ids, data={'year': self.today.year, 'company_id': self.company.id})
        self.assertIn(b'E001-77', html)
        self.assertIn(b'Certificado de rentas y retenciones', html)

    def test_suspension_company_rule(self):
        other = self.env['res.company'].create({'name': 'Otra (test 4ta)'})
        suspension = self.env['l10n_pe.fourth.category.suspension'].with_company(other).create({
            'partner_id': self.provider.id, 'number': '1609-9', 'company_id': other.id,
            'date_issued': self.today - timedelta(days=2)})
        move = self._receipt(5000.0)
        self.assertEqual(move.l10n_pe_fourth_category_status, 'withheld',
                         'la constancia registrada en otra compañía no aplica')
        self.assertTrue(suspension)
