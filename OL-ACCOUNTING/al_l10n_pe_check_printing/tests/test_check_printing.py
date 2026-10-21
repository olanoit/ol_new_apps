"""Impresión de cheques propios con el formato de la chequera."""
import re
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_account_base.tests.common import use_pe_company
from odoo.addons.al_l10n_pe_check_printing.models.check_layout import amount_in_words

MM = 72 / 25.4  # puntos por milímetro


@tagged('post_install', '-at_install')
class TestCheckPrinting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.company._l10n_pe_check_setup()
        Journal = cls.env['account.journal']
        cls.bank = Journal.search([*Journal._check_company_domain(cls.company), ('type', '=', 'bank')], limit=1)
        cls.layout = cls.env['l10n_pe.check.layout'].create({
            'name': 'Chequera de prueba', 'paper_width': 170, 'paper_height': 75, 'city': 'Lima'})
        cls.bank.l10n_pe_check_layout_id = cls.layout
        cls.supplier = cls.env['res.partner'].create({'name': 'PROVEEDOR CHEQUES SAC'})
        cls.portfolio = cls.env['account.chart.template'].with_company(cls.company).ref('l10n_pe_third_party_check')

    def _own_check(self, amount=1250.0, payment_date=date(2026, 10, 21), journal=None):
        journal = journal or self.bank
        line = journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.supplier.id,
            'journal_id': journal.id, 'payment_method_line_id': line.id, 'date': date(2026, 10, 21),
            'amount': amount,
            'l10n_latam_new_check_ids': [Command.create({
                'name': '00004521', 'payment_date': payment_date, 'amount': amount})],
        })
        payment.action_post()
        return payment

    def _html(self, checks=None, data=None):
        html, _type = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_check_printing.report_check', checks.ids if checks else [], data=data)
        return html.decode()

    # ------------------------------------------------------------------ textos
    def test_amount_in_words_and_figures(self):
        pen = self.company.currency_id
        self.assertEqual(amount_in_words(1250.0, pen), 'MIL DOSCIENTOS CINCUENTA Y 00/100 SOLES')
        self.assertEqual(amount_in_words(0.5, self.env.ref('base.USD')), 'CERO Y 50/100 DÓLARES AMERICANOS')
        self.assertEqual(self.layout._l10n_pe_format_amount(1250.0, pen), 'S/ ******1,250.00')
        self.layout.amount_fill = False
        self.assertEqual(self.layout._l10n_pe_format_amount(1250.0, pen), 'S/ 1,250.00')

    def test_date_formats(self):
        self.assertEqual(self.layout._l10n_pe_format_date(date(2026, 10, 21)), 'Lima, 21 de octubre de 2026')
        self.layout.write({'date_style': 'numeric', 'city': False})
        self.assertEqual(self.layout._l10n_pe_format_date(date(2026, 10, 21)), '21/10/2026')

    # ------------------------------------------------------------------ papel
    def test_paperformat_follows_the_sheet(self):
        paperformat = self.layout.paperformat_id
        self.assertEqual((paperformat.format, paperformat.page_width, paperformat.page_height), ('custom', 170, 75))
        self.assertEqual((paperformat.margin_top, paperformat.margin_left), (0, 0))
        self.layout.paper_width = 180
        self.assertEqual(paperformat.page_width, 180)

    def test_pdf_page_has_the_sheet_size(self):
        check = self._own_check().l10n_latam_new_check_ids
        pdf, _type = self.env['ir.actions.report'].with_context(force_report_rendering=True)._render_qweb_pdf(
            'al_l10n_pe_check_printing.report_check', check.ids)
        box = re.search(rb'/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', pdf)
        width = float(box.group(3)) - float(box.group(1))
        height = float(box.group(4)) - float(box.group(2))
        self.assertAlmostEqual(width / MM, 170, delta=1)
        self.assertAlmostEqual(height / MM, 75, delta=1)

    # ------------------------------------------------------------------ cheque
    def test_check_prints_payee_amount_and_words(self):
        payment = self._own_check()
        action = payment.action_l10n_pe_print_checks()
        self.assertEqual(action['report_name'], 'al_l10n_pe_check_printing.report_check')
        html = self._html(payment.l10n_latam_new_check_ids)
        for text in ('PROVEEDOR CHEQUES SAC', 'S/ ******1,250.00', 'MIL DOSCIENTOS CINCUENTA Y 00/100 SOLES',
                     'Lima, 21 de octubre de 2026'):
            self.assertIn(text, html)
        self.assertNotIn('Pagar desde', html, 'no es diferido')

    def test_deferred_check_prints_payment_date(self):
        check = self._own_check(payment_date=date(2026, 11, 20)).l10n_latam_new_check_ids
        self.assertIn('Pagar desde: 20 de noviembre de 2026', self._html(check))
        self.layout.print_due_date = False
        self.assertNotIn('Pagar desde', self._html(check))

    def test_print_test_sheet(self):
        action = self.layout.action_print_test()
        self.assertEqual(action['data'], {'l10n_pe_test_layout_id': self.layout.id})
        html = self._html(data=action['data'])
        self.assertIn('BENEFICIARIO DE PRUEBA', html)
        self.assertIn('DOCE MIL TRESCIENTOS CUARENTA Y CINCO Y 67/100 SOLES', html)

    def test_requires_layout_and_own_checks(self):
        other_bank = self.env['account.journal'].create({
            'name': 'Banco sin formato', 'code': 'BKSF', 'type': 'bank', 'company_id': self.company.id})
        self.company._l10n_pe_check_setup()
        if other_bank.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks'):
            check = self._own_check(journal=other_bank).l10n_latam_new_check_ids
            with self.assertRaisesRegex(UserError, 'formato de cheque'):
                check.action_l10n_pe_print_check()
        line = self.portfolio.inbound_payment_method_line_ids.filtered(lambda l: l.code == 'new_third_party_checks')
        received = self.env['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': self.supplier.id,
            'journal_id': self.portfolio.id, 'payment_method_line_id': line.id, 'date': date(2026, 10, 21),
            'l10n_latam_new_check_ids': [Command.create({
                'name': '00000777', 'payment_date': date(2026, 10, 21), 'amount': 50,
                'bank_id': self.env['res.bank'].create({'name': 'Banco tercero'}).id})],
        })
        received.action_post()
        with self.assertRaisesRegex(UserError, 'cheques propios'):
            received.l10n_latam_new_check_ids.action_l10n_pe_print_check()
