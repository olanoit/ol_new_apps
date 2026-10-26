"""ITF: redondeo del art. 13 de la Ley 28194 y asiento al confirmar pagos y cobros."""
from datetime import date

from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

from odoo.addons.al_account_base.tests.common import use_pe_company
from odoo.addons.al_l10n_pe_itf.models.res_company import itf_amount

D1 = date(2026, 9, 10)


@tagged('post_install', '-at_install')
class TestItf(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.itf_account = cls.company._l10n_pe_itf_account()
        cls.partner = cls.env['res.partner'].create({'name': 'PROVEEDOR ITF SAC'})
        cls.outstanding = cls.env['account.account'].create({
            'name': 'Pendientes (prueba ITF)', 'code': '104196', 'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.bank = cls._bank('Banco ITF', 'BKIT', itf=True)
        cls.bank_exempt = cls._bank('Banco detracciones', 'BKDT', itf=False)
        cls.bank_plain = cls._bank('Banco sin pendientes', 'BKSP', itf=True, outstanding=False)
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id), ('company_id', 'in', (False, cls.company.id)),
            ('name', '=', D1)]).unlink()
        cls.env['res.currency.rate'].create({
            'name': D1, 'currency_id': cls.usd.id, 'company_id': cls.company.id, 'inverse_company_rate': 3.75})
        cls.bank_usd = cls._bank('Banco dólares ITF', 'BKUS', itf=True, currency=cls.usd)

    @classmethod
    def _bank(cls, name, code, itf, outstanding=True, currency=None):
        journal = cls.env['account.journal'].create({
            'name': name, 'code': code, 'type': 'bank', 'company_id': cls.company.id,
            'l10n_pe_itf_applies': itf, 'currency_id': currency and currency.id,
        })
        (journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids) \
            .payment_account_id = cls.outstanding if outstanding else False
        return journal

    def _payment(self, amount, journal=None, payment_type='outbound', **vals):
        payment = self.env['account.payment'].create({
            'payment_type': payment_type,
            'partner_type': 'supplier' if payment_type == 'outbound' else 'customer',
            'partner_id': self.partner.id, 'amount': amount, 'date': D1,
            'journal_id': (journal or self.bank).id, **vals,
        })
        payment.action_post()
        return payment

    # ------------------------------------------------------------------ redondeo
    def test_rounding_of_article_13(self):
        """Se suprime el tercer decimal y el segundo se ajusta a 0 o a 5."""
        for amount, expected in ((1000, 0.05), (1999.99, 0.05), (2000, 0.10), (999.99, 0.0),
                                 (500, 0.0), (30000, 1.50), (12345.67, 0.60), (7000, 0.35)):
            with self.subTest(amount=amount):
                self.assertEqual(itf_amount(amount), expected)

    # ------------------------------------------------------------------ asiento
    def test_outbound_payment_books_itf(self):
        payment = self._payment(2000)
        self.assertAlmostEqual(payment.l10n_pe_itf_amount, 0.10)
        move = payment.l10n_pe_itf_move_id
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.journal_id, self.bank)
        self.assertEqual(move.l10n_pe_itf_payment_id, payment)
        expense = move.line_ids.filtered(lambda l: l.account_id == self.itf_account)
        self.assertAlmostEqual(expense.balance, 0.10)
        self.assertAlmostEqual(move.line_ids.filtered(lambda l: l.account_id == self.outstanding).balance, -0.10)

    def test_inbound_payment_also_books_itf(self):
        payment = self._payment(5000, payment_type='inbound')
        self.assertAlmostEqual(payment.l10n_pe_itf_move_id.amount_total, 0.25)

    def test_usd_payment_books_itf_in_dollars(self):
        payment = self._payment(1000, journal=self.bank_usd)
        expense = payment.l10n_pe_itf_move_id.line_ids.filtered(lambda l: l.account_id == self.itf_account)
        self.assertEqual(expense.currency_id, self.usd)
        self.assertAlmostEqual(expense.amount_currency, 0.05)
        self.assertAlmostEqual(expense.balance, 0.19, msg='0,05 USD × 3,75 = 0,1875')

    # ------------------------------------------------------------------ sin ITF
    def test_no_itf_cases(self):
        cases = {
            'diario exonerado': self._payment(5000, journal=self.bank_exempt),
            'menos de S/ 1 000': self._payment(999),
            'pago marcado exonerado': self._payment(5000, l10n_pe_itf_exempt=True),
            'cuentas propias': self._payment(5000, destination_account_id=self.company.transfer_account_id.id),
        }
        for case, payment in cases.items():
            with self.subTest(case):
                self.assertFalse(payment.l10n_pe_itf_move_id)

    def test_journal_without_outstanding_uses_reconcile_model(self):
        # Sin la app Contabilidad (accountant), Odoo pone una cuenta de pendientes a
        # todos los pagos y siempre crea su asiento: el caso no existe.
        if self.env['account.move']._get_invoice_in_payment_state() != 'in_payment':
            self.skipTest('Solo con la app Contabilidad (accountant) hay pagos sin asiento.')
        payment = self._payment(5000, journal=self.bank_plain)
        self.assertFalse(payment.move_id)
        self.assertFalse(payment.l10n_pe_itf_move_id, 'su ITF se registra al conciliar el extracto')
        self.assertAlmostEqual(payment.l10n_pe_itf_amount, 0.25)
        model = self.company._l10n_pe_itf_reconcile_model()
        self.assertEqual(model, self.company._l10n_pe_itf_reconcile_model(), 'no se duplica')
        self.assertEqual(model.line_ids.account_id, self.itf_account)
        self.assertEqual(model.match_label, 'match_regex')

    def test_draft_cancels_itf_and_repost_books_again(self):
        payment = self._payment(3000)
        first = payment.l10n_pe_itf_move_id
        payment.action_draft()
        self.assertEqual(first.state, 'cancel')
        self.assertFalse(payment.l10n_pe_itf_move_id)
        payment.action_post()
        self.assertTrue(payment.l10n_pe_itf_move_id)
        self.assertNotEqual(payment.l10n_pe_itf_move_id, first)

    def test_cancel_payment_cancels_itf(self):
        payment = self._payment(3000)
        itf = payment.l10n_pe_itf_move_id
        payment.action_cancel()
        self.assertEqual(itf.state, 'cancel')

    def test_analysis_action_lists_itf(self):
        payment = self._payment(4000)
        action = self.env.ref('al_l10n_pe_itf.action_itf_analysis')
        lines = self.env['account.move.line'].search(safe_eval(action.domain))
        self.assertIn(payment.l10n_pe_itf_move_id.line_ids.filtered(lambda l: l.account_id == self.itf_account),
                      lines)
