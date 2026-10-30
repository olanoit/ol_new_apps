# -*- coding: utf-8 -*-
import base64
import io

from PIL import Image

from odoo.tools import BinaryBytes
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_account_base.tests.common import use_pe_company


def _png():
    buffer = io.BytesIO()
    Image.new('RGB', (40, 40), (114, 46, 209)).save(buffer, format='PNG')
    return BinaryBytes(buffer.getvalue())


@tagged('post_install', '-at_install')
class TestWalletQr(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.pen = cls.env.ref('base.PEN')
        cls.bank_account = cls.env['res.partner.bank'].create({
            'account_number': '19112345678090',
            'partner_id': cls.company.partner_id.id,
            'l10n_pe_wallet_qr_image': _png(),
        })
        cls.journal = cls.env['account.journal'].create({
            'name': 'Yape (prueba)', 'code': 'YAPT', 'type': 'bank',
            'company_id': cls.company.id, 'bank_account_id': cls.bank_account.id,
        })

    def _payment_method(self, **values):
        return self.env['pos.payment.method'].create({
            'name': 'Yape', 'type': 'bank', 'journal_id': self.journal.id, 'company_id': self.company.id,
            'payment_method_type': 'bank_qr_code', 'qr_code_method': 'l10n_pe_wallet', **values,
        })

    def test_method_is_offered(self):
        methods = dict(self.env['res.partner.bank'].get_available_qr_methods_in_sequence())
        self.assertIn('l10n_pe_wallet', methods)

    def test_pos_shows_the_wallet_image(self):
        method = self._payment_method()
        qr = method.get_qr_code_value(25.5, 'Orden 0001', '', self.pen.id, False)
        self.assertTrue(qr.startswith('data:image/png;base64,'))
        # Odoo 20: el campo Image es un BinaryValue (bytes crudos).
        self.assertEqual(qr.split(',', 1)[1], self.bank_account.l10n_pe_wallet_qr_image.to_base64())
        # Sin conexión, el TPV usa el mismo QR.
        self.assertEqual(method.default_qr, qr)

    def test_account_without_image_is_rejected(self):
        self.bank_account.l10n_pe_wallet_qr_image = False
        with self.assertRaisesRegex(ValidationError, 'QR de billetera'):
            self._payment_method()

    def test_only_soles(self):
        method = self._payment_method()
        usd = self.env.ref('base.USD')
        with self.assertRaisesRegex(UserError, 'soles'):
            method.get_qr_code_value(10.0, 'Orden 0002', '', usd.id, False)

    def test_other_qr_methods_untouched(self):
        self.assertIsNone(self.bank_account._get_error_messages_for_qr('unknown_method', False, self.pen))
