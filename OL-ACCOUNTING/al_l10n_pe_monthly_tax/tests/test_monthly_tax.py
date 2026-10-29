# -*- coding: utf-8 -*-
"""Resumen del 621: IGV, saldo a favor, percepciones y retenciones con su
arrastre, y pago a cuenta del impuesto a la renta según el régimen."""
from datetime import date
from unittest.mock import patch

from psycopg2 import IntegrityError
from stdnum.pe import ruc as stdnum_ruc

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from ..models.l10n_pe_monthly_tax import L10nPeMonthlyTax

YEAR = 2031  # periodo sin movimientos de la base de pruebas


def _ruc(body):
    return body + stdnum_ruc.calc_check_digit(body)


@tagged('post_install', '-at_install')
class TestMonthlyTax(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if cls.company.account_fiscal_country_id.code != 'PE':
            cls.skipTest(cls, 'La compañía de prueba no es peruana')
        Tax = cls.env['account.tax']
        domain = [('company_id', '=', cls.company.id), ('l10n_pe_edi_tax_code', '=', '1000'),
                  ('amount', '=', 18.0), ('amount_type', '=', 'percent')]
        cls.igv_sale = Tax.search(domain + [('type_tax_use', '=', 'sale')], limit=1)
        cls.igv_purchase = Tax.search(domain + [('type_tax_use', '=', 'purchase')], limit=1)
        pe = cls.env.ref('base.pe')
        cls.customer = cls.env['res.partner'].create({
            'name': 'CLIENTE 621 SAC (test)', 'country_id': pe.id, 'is_company': True, 'vat': _ruc('2060123456')})
        cls.vendor = cls.env['res.partner'].create({
            'name': 'PROVEEDOR 621 SAC (test)', 'country_id': pe.id, 'is_company': True, 'vat': _ruc('2060765432')})
        cls.sale_journal = cls.env['account.journal'].search([
            ('type', '=', 'sale'), ('company_id', '=', cls.company.id)], limit=1)
        cls.purchase_journal = cls.env['account.journal'].search([
            ('type', '=', 'purchase'), ('company_id', '=', cls.company.id)], limit=1)
        cls.invoice_type = cls.env.ref('l10n_pe.document_type01')
        cls.env['l10n_pe.tax.regime'].search([('company_id', '=', cls.company.root_id.id)]).unlink()
        cls.regime = cls.env['l10n_pe.tax.regime'].create({
            'company_id': cls.company.root_id.id, 'regime': 'general', 'date_from': date(YEAR, 1, 1)})
        cls.company.root_id.write({'l10n_pe_income_coefficient': 0.02,
                                   'l10n_pe_income_coefficient_jan_feb': 0.01,
                                   'l10n_pe_income_suspended': False})
        cls.counter = 0

    def _invoice(self, move_type, amount, day, refund=False):
        type(self).counter += 1
        sale = move_type.startswith('out')
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': (self.customer if sale else self.vendor).id,
            'journal_id': (self.sale_journal if sale else self.purchase_journal).id,
            'invoice_date': day, 'date': day,
            'l10n_latam_document_type_id': (
                self.env.ref('l10n_pe.document_type07') if refund else self.invoice_type).id,
            'l10n_latam_document_number': 'F%03d-%06d' % (900 + self.counter % 99, self.counter),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio (test 621)', 'quantity': 1, 'price_unit': amount,
                'tax_ids': [(6, 0, (self.igv_sale if sale else self.igv_purchase).ids)]})],
        })
        move.action_post()
        return move

    def _period(self, month, received=None):
        record = self.env['l10n_pe.monthly.tax'].create({'year': YEAR, 'month': str(month)})
        amounts = received or {}

        def fake(model_self, model, date_from, date_to):
            return amounts.get(model, 0.0)
        with patch.object(L10nPeMonthlyTax, '_received_amount', fake):
            record.action_compute()
        return record

    def test_igv_perception_retention_and_carry(self):
        self._invoice('out_invoice', 10000.0, date(YEAR, 5, 10))
        self._invoice('in_invoice', 4000.0, date(YEAR, 5, 12))
        may = self._period(5, {'l10n_pe.perception.received': 1500.0,
                               'l10n_pe.retention.received': 200.0})
        self.assertAlmostEqual(may.sale_igv, 1800.0)
        self.assertAlmostEqual(may.sale_base, 10000.0)
        self.assertAlmostEqual(may.purchase_igv, 720.0)
        self.assertAlmostEqual(may.igv_result, 1080.0)
        self.assertAlmostEqual(may.applied_perception, 1080.0)
        self.assertAlmostEqual(may.next_perception, 420.0)
        self.assertAlmostEqual(may.applied_retention, 0.0)
        self.assertAlmostEqual(may.next_retention, 200.0)
        self.assertEqual(may.igv_to_pay, 0.0)
        self.assertEqual(may.state, 'calculated')
        # El saldo no aplicado pasa al mes siguiente.
        self._invoice('out_invoice', 5000.0, date(YEAR, 6, 5))
        june = self._period(6, {'l10n_pe.retention.received': 100.0})
        self.assertEqual(june.previous_id, may)
        self.assertAlmostEqual(june.previous_perception, 420.0)
        self.assertAlmostEqual(june.previous_retention, 200.0)
        self.assertAlmostEqual(june.igv_result, 900.0)
        self.assertAlmostEqual(june.applied_perception, 420.0)
        self.assertAlmostEqual(june.applied_retention, 300.0)
        self.assertEqual(june.igv_to_pay, 180.0)
        self.assertAlmostEqual(june.next_perception, 0.0)

    def test_credit_balance_and_refund(self):
        self._invoice('out_invoice', 1000.0, date(YEAR, 7, 3))
        self._invoice('out_refund', 200.0, date(YEAR, 7, 4), refund=True)
        self._invoice('in_invoice', 3000.0, date(YEAR, 7, 8))
        july = self._period(7)
        self.assertAlmostEqual(july.sale_base, 800.0, msg='la nota de crédito resta')
        self.assertAlmostEqual(july.sale_igv, 144.0)
        self.assertAlmostEqual(july.igv_result, -396.0)
        self.assertAlmostEqual(july.next_credit, 396.0)
        self.assertEqual(july.igv_to_pay, 0.0)
        self._invoice('out_invoice', 3000.0, date(YEAR, 8, 3))
        august = self._period(8)
        self.assertAlmostEqual(august.previous_credit, 396.0)
        self.assertEqual(august.igv_to_pay, 144.0)

    def test_income_tax_by_regime(self):
        self._invoice('out_invoice', 10000.0, date(YEAR, 3, 10))
        march = self._period(3)
        self.assertAlmostEqual(march.net_income, 10000.0)
        self.assertEqual(march.income_tax_to_pay, 200.0, 'coeficiente 0,02 mayor que 1,5 %')
        self.company.root_id.l10n_pe_income_coefficient = 0.01
        march.action_compute()
        self.assertEqual(march.income_tax_to_pay, 150.0, '1,5 % mayor que el coeficiente')
        self.company.root_id.l10n_pe_income_suspended = True
        march.action_compute()
        self.assertEqual(march.income_tax_to_pay, 0.0)
        self.company.root_id.l10n_pe_income_suspended = False
        self.regime.regime = 'mype'
        march.action_compute()
        self.assertEqual(march.income_tax_to_pay, 100.0, 'MYPE hasta 300 UIT: 1 %')
        self.regime.regime = 'special'
        march.action_compute()
        self.assertEqual(march.income_tax_to_pay, 150.0, 'RER: 1,5 %')

    def test_january_uses_previous_coefficient(self):
        self._invoice('out_invoice', 10000.0, date(YEAR, 1, 10))
        january = self._period(1)
        self.assertAlmostEqual(january.coefficient, 0.01)
        self.assertEqual(january.income_tax_to_pay, 150.0)

    def test_mype_over_300_uit_uses_general_rules(self):
        self.regime.regime = 'mype'
        self.company.root_id.l10n_pe_tax_uit_amount = 10.0
        self.env.invalidate_all()
        if 'l10n_pe.hr.uit' in self.env:
            self.env['l10n_pe.hr.uit'].sudo().search([('year', '=', YEAR)]).unlink()
        self._invoice('out_invoice', 10000.0, date(YEAR, 4, 10))
        april = self._period(4)
        self.assertEqual(april.income_tax_to_pay, 200.0, 'más de 300 UIT: coeficiente')

    def test_declare_and_income_move(self):
        self._invoice('out_invoice', 10000.0, date(YEAR, 9, 10))
        september = self._period(9)
        with self.assertRaises(UserError):
            september.action_post_income_move()
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'), ('company_id', '=', self.company.id)], limit=1)
        accounts = self.env['account.account'].search([
            ('company_ids', 'in', self.company.id), ('account_type', '=', 'liability_current')], limit=2)
        self.company.root_id.write({
            'l10n_pe_monthly_tax_journal_id': journal.id,
            'l10n_pe_income_advance_account_id': accounts[0].id,
            'l10n_pe_income_payable_account_id': accounts[1].id})
        september.action_post_income_move()
        self.assertEqual(september.income_move_id.state, 'posted')
        self.assertAlmostEqual(september.income_move_id.amount_total, 200.0)
        september.action_declare()
        self.assertEqual(september.state, 'declared')
        with self.assertRaises(UserError):
            september.action_compute()
        with self.assertRaises(UserError):
            september.action_reset()

    def test_one_period_per_company(self):
        self.env['l10n_pe.monthly.tax'].create({'year': YEAR, 'month': '11'})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.env['l10n_pe.monthly.tax'].create({'year': YEAR, 'month': '11'})
            self.env.flush_all()
