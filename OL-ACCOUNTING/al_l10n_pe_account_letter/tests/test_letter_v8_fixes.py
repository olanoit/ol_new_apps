# -*- coding: utf-8 -*-
"""Defectos corregidos en la versión 8 (auditoría del 07/10/2026).

- 1 000 en 3 letras daba 3 × 333,33 y el céntimo iba a gasto por redondeo.
- Una letra enviada al banco (cobranza libre o descuento) quedaba «Pagado»
  aunque el cliente no hubiera pagado.
- Las facturas se conciliaban emparejando apuntes por orden.
- Las letras nuevas no tenían tipo («En cartera»).
- Las cuentas de letras del PCGE había que configurarlas a mano.
"""
from datetime import date

from odoo.tests import tagged

from .test_letter_bank_flow import TestLetterBankFlow


@tagged('post_install', '-at_install')
class TestLetterV8Fixes(TestLetterBankFlow):

    def _letter_for(self, amounts, letters):
        """Canje en «Canjeado» de varias facturas, con ``letters`` letras."""
        invoices = self.env['account.move']
        for amount in amounts:
            invoices |= self._invoice(amount)
        lines = []
        for invoice in invoices:
            term = invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term')
            lines.append((0, 0, {
                'document_type_id': self.doc_type.id, 'move_line_id': term.id,
                'account_id': term.account_id.id, 'imp_div': abs(term.amount_residual_currency)}))
        letter = self.env['l10n_pe.letter'].create({
            'partner_id': self.partner.id, 'type': 'out_invoice',
            'journal_id': self.letter_journal.id, 'invoice_line_ids': lines})
        letter.invoice_date = date(2026, 8, 10)
        letter.action_checked()
        letter.write({'number_letter': letters, 'letter_end_date': date(2026, 9, 10),
                      'range_date': 30})
        letter.create_letters()
        for index, line in enumerate(letter.letter_line_ids, start=1):
            line.nro_letter = 'V8-%d-%03d' % (letter.id, index)
        letter.action_redeemed()
        return letter, invoices

    def test_ultima_letra_absorbe_el_redondeo(self):
        letter, invoices = self._letter_for([1000.0], 3)
        self.assertEqual(letter.letter_line_ids.mapped('imp_div'), [333.33, 333.33, 333.34])
        self.assertFalse(letter.letter_residual_ids, 'nada a gasto por redondeo')
        self.assertFalse(letter.account_id.line_ids.filtered(lambda l: l.name == 'Redondeo'))
        self.assertEqual(invoices.payment_state, 'paid')

    def test_letras_nuevas_en_cartera(self):
        letter, dummy = self._letter_for([600.0], 2)
        self.assertEqual(set(letter.letter_line_ids.mapped('letter_type')), {'portfolio'})

    def test_letra_en_el_banco_sigue_pendiente(self):
        letter, dummy = self._letter_for([1000.0], 2)
        first, second = letter.letter_line_ids
        self._send_to_bank(letter, date(2026, 8, 15), line=first)
        self.assertEqual(first.adeudado, 500.0)
        self.assertEqual(first.payment_state, 'pending', 'enviada al banco no es cobrada')
        self.assertEqual(second.payment_state, 'pending')
        self.assertNotIn(first, letter._get_letters_to_send())
        # El cliente paga la letra en el banco.
        destination = letter.canje_move_ids.line_ids.filtered(
            lambda l: l.l10n_pe_letter_line_id == first and not l.reconciled)
        self.assertEqual(destination.amount_residual_currency, 500.0)
        payment = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.letter_journal.id, 'date': date(2026, 9, 10),
            'line_ids': [
                (0, 0, {'name': 'Cobro', 'account_id': self.income.id, 'debit': 500.0}),
                (0, 0, {'name': 'Cobro', 'account_id': destination.account_id.id,
                        'partner_id': self.partner.id, 'credit': 500.0}),
            ]})
        payment.action_post()
        (payment.line_ids.filtered(lambda l: l.account_id == destination.account_id) + destination).reconcile()
        self.assertEqual(first.adeudado, 0.0)
        self.assertEqual(first.payment_state, 'paid')

    def test_conciliacion_por_vinculo(self):
        """Dos facturas de importes distintos: cada una se concilia con su apunte."""
        letter, invoices = self._letter_for([1200.0, 300.0], 3)
        self.assertEqual(set(invoices.mapped('payment_state')), {'paid'})
        for invoice_line in letter.invoice_line_ids:
            canje_line = letter.account_id.line_ids.filtered(
                lambda l: l.l10n_pe_letter_invoice_line_id == invoice_line)
            self.assertEqual(abs(canje_line.amount_currency), invoice_line.imp_div)
            self.assertTrue(canje_line.reconciled)

    def test_configuracion_pcge(self):
        company = self.env['res.company'].create({
            'name': 'Letras PCGE SAC', 'country_id': self.env.ref('base.pe').id,
            'currency_id': self.env.ref('base.PEN').id})
        self.env['account.chart.template'].try_loading('pe', company=company, install_demo=False)
        Config = self.env['l10n_pe.letter.account.config']
        created = Config._l10n_pe_create_default_configs(company)
        mapping = {(c.account_type, c.letter_type, c.currency_id.name): c.account_id.with_company(company).code[:4]
                   for c in created}
        self.assertEqual(mapping[('asset_receivable', 'portfolio', 'PEN')], '1232')
        self.assertEqual(mapping[('asset_receivable', 'billing', 'PEN')], '1233')
        self.assertEqual(mapping[('asset_receivable', 'discount', 'PEN')], '1234')
        self.assertEqual(mapping[('liability_payable', 'portfolio', 'PEN')], '4230')
        self.assertFalse(Config._l10n_pe_create_default_configs(company), 'no duplica')


# Los tests heredados ya corren en su propia clase.
for _name in dir(TestLetterBankFlow):
    if _name.startswith('test_') and _name not in TestLetterV8Fixes.__dict__:
        setattr(TestLetterV8Fixes, _name, None)
