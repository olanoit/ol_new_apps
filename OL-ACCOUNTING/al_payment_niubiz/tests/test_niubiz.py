# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.tests.http_common import PaymentHttpCommon

REQUESTS = 'odoo.addons.al_payment_niubiz.models.payment_provider.requests'
JWT = 'eyJhbGciOiJIUzI1NiJ9.niubiz-jwt'


def response(status=200, json_data=None, text=''):
    resp = MagicMock(status_code=status, text=text or str(json_data))
    resp.json.return_value = json_data or {}
    resp.raise_for_status.side_effect = None if status < 400 else __import__('requests').exceptions.HTTPError(str(status))
    return resp


@tagged('post_install', '-at_install')
class TestNiubiz(PaymentHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls._prepare_provider('niubiz', update_values={
            'niubiz_merchant_id': '456879852',
            'niubiz_access_key': 'integraciones@niubiz.com.pe',
            'niubiz_secret_key': 'secreto-de-prueba',
            'niubiz_ruc': '20512528458',
        })
        cls.currency = cls._enable_currency('PEN')
        cls.amount = 150.0
        cls.partner.write({'email': 'cliente@example.com', 'phone': False, 'city': 'Lima',
                           'country_id': cls.env.ref('base.pe').id})
        cls.payment_method_id = cls.env.ref('payment.payment_method_card').id
        cls.approved = {
            'header': {'ecoreTransactionUUID': 'a1b2c3', 'ecoreTransactionDate': 1791232000000},
            'order': {'actionCode': '000', 'authorizationCode': '173424', 'traceNumber': '75', 'purchaseNumber': '1'},
            'dataMap': {'STATUS': 'Authorized', 'BRAND': 'visa'},
        }
        cls.declined = {
            'errorCode': 400, 'errorMessage': 'NOT AUTHORIZED',
            'data': {'ACTION_CODE': '116', 'STATUS': 'Not Authorized', 'BRAND': 'visa', 'TRACE_NUMBER': '76'},
        }

    def setUp(self):
        super().setUp()
        # Servidor con varias bases: la sesión anónima fija la base de la prueba.
        self.authenticate(None, None)

    # ------------------------------------------------------------ proveedor
    def test_currencies_and_secret_restricted(self):
        self.assertEqual(sorted(self.provider._get_supported_currencies().mapped('name')), ['PEN', 'USD'])
        self.assertEqual(self.provider._fields['niubiz_secret_key'].groups, 'base.group_system')

    def test_session_without_phone(self):
        """Odoo 19 ya no tiene ``res.partner.mobile``: sin teléfono no debe fallar."""
        tx = self._create_transaction('redirect')
        with patch(f'{REQUESTS}.request', return_value=response(200, {'sessionKey': 'S1'})) as post:
            self.provider._niubiz_get_session_token(JWT, tx)
        self.assertEqual(post.call_args.kwargs['json']['dataMap']['cardholderPhoneNumber'], '000000000')

    @mute_logger('odoo.addons.al_payment_niubiz.models.payment_provider')
    def test_access_token_retries_on_tls_failure(self):
        import requests as real_requests
        with patch(f'{REQUESTS}.request', side_effect=[real_requests.exceptions.SSLError('EOF'),
                                                        response(201, text=JWT)]) as request, \
                patch('odoo.addons.al_payment_niubiz.models.payment_provider.time.sleep'):
            self.assertEqual(self.provider._niubiz_get_access_token(), JWT)
        self.assertEqual(request.call_count, 2)

    # ----------------------------------------------------------- autorización
    def test_approved_authorization(self):
        tx = self._create_transaction('redirect')
        with patch(f'{REQUESTS}.post', return_value=response(200, self.approved)):
            data = self.provider._niubiz_authorize(JWT, 'TKN', tx)
        tx._process('niubiz', {**data, 'reference': tx.reference})
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, '173424')
        self.assertEqual(tx.niubiz_trace_number, '75')
        self.assertTrue(tx.niubiz_transaction_date)

    @mute_logger('odoo.addons.payment.models.payment_transaction')
    def test_declined_authorization(self):
        tx = self._create_transaction('redirect')
        with patch(f'{REQUESTS}.post', return_value=response(400, self.declined)):
            data = self.provider._niubiz_authorize(JWT, 'TKN', tx)
        tx._process('niubiz', {**data, 'reference': tx.reference})
        self.assertEqual(tx.state, 'error')
        self.assertIn('Fondos insuficientes', tx.state_message)

    # ------------------------------------------------------------ devolución
    def test_refund(self):
        tx = self._create_transaction('redirect', state='done', niubiz_trace_number='75')
        refund_ok = {'errorCode': 0, 'data': {'CODERROR': '100', 'CODIGODEVOLUCION': 'DEV-1'}}
        with patch(f'{REQUESTS}.request', return_value=response(200, text=JWT)), \
                patch(f'{REQUESTS}.post', return_value=response(200, refund_ok)) as post:
            refund = tx._refund(amount_to_refund=50.0)
        self.assertEqual(post.call_args.kwargs['json']['amount'], 50.0)
        self.assertEqual(post.call_args.kwargs['json']['ruc'], '20512528458')
        self.assertEqual(refund.state, 'done')
        self.assertEqual(refund.provider_reference, 'DEV-1')

    @mute_logger('odoo.addons.payment.models.payment_transaction')
    def test_refund_requires_ruc(self):
        self.provider.niubiz_ruc = False
        tx = self._create_transaction('redirect', state='done', niubiz_trace_number='75')
        refund = tx._refund(amount_to_refund=50.0)
        self.assertEqual(refund.state, 'error')
        self.assertIn('RUC', refund.state_message)

    # ------------------------------------------------------------- anulación
    def test_reverse_voided_is_success(self):
        """Respuesta real del sandbox: actionCode 400 + STATUS Voided = anulada."""
        tx = self._create_transaction('redirect', state='done', niubiz_transaction_date='261006120945')
        voided = {'order': {'actionCode': '400', 'authorizationCode': '', 'traceNumber': '2134'},
                  'dataMap': {'ACTION_CODE': '400', 'STATUS': 'Voided', 'AMOUNT': '0.00'}}
        with patch(f'{REQUESTS}.request', return_value=response(200, text=JWT)), \
                patch(f'{REQUESTS}.post', return_value=response(200, voided)):
            result = tx.action_niubiz_reverse()
        self.assertEqual(tx.state, 'cancel')
        self.assertEqual(result['params']['type'], 'success')

    @mute_logger('odoo.addons.payment.models.payment_transaction')
    def test_reverse_rejected(self):
        tx = self._create_transaction('redirect', state='done', niubiz_transaction_date='261006120945')
        rejected = {'order': {'actionCode': '180'}, 'dataMap': {'STATUS': 'Not Voided'}}
        with patch(f'{REQUESTS}.request', return_value=response(200, text=JWT)), \
                patch(f'{REQUESTS}.post', return_value=response(200, rejected)):
            result = tx.action_niubiz_reverse()
        self.assertEqual(result['params']['type'], 'danger')

    # ----------------------------------------------------------------- rutas
    def _token(self, tx):
        return payment_utils.generate_access_token(tx.reference, env=self.env)

    def test_rendering_values_are_signed(self):
        tx = self._create_transaction('redirect')
        values = tx._get_specific_rendering_values({})
        self.assertEqual(values['access_token'], self._token(tx))

    def test_landing_rejects_bad_signature(self):
        tx = self._create_transaction('redirect', state='error')
        with patch(f'{REQUESTS}.request') as get:
            resp = self.url_open(f'/payment/niubiz/landing?reference={tx.reference}&access_token=falso',
                                 allow_redirects=False)
        get.assert_not_called()
        self.assertIn('/payment/status', resp.headers.get('Location', ''))
        self.assertEqual(tx.state, 'error')

    def test_landing_return_url_carries_signature_not_niubiz_token(self):
        tx = self._create_transaction('redirect')
        with patch(f'{REQUESTS}.request', side_effect=[response(200, text=JWT),
                                                        response(200, {'sessionKey': 'S1'})]):
            resp = self.url_open(f'/payment/niubiz/landing?reference={tx.reference}&access_token={self._token(tx)}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self._token(tx), resp.text)
        self.assertNotIn(JWT, resp.text)

    def test_return_rejects_bad_signature(self):
        tx = self._create_transaction('redirect')
        with patch(f'{REQUESTS}.request') as get:
            self.url_open(f'/payment/niubiz/return?reference={tx.reference}&access_token=falso',
                          data={'transactionToken': 'TKN'}, allow_redirects=False)
        get.assert_not_called()
        self.assertEqual(tx.state, 'draft')

    def test_return_authorizes_payment(self):
        tx = self._create_transaction('redirect')
        with patch(f'{REQUESTS}.request', return_value=response(200, text=JWT)), \
                patch(f'{REQUESTS}.post', return_value=response(200, self.approved)):
            self.url_open(f'/payment/niubiz/return?reference={tx.reference}&access_token={self._token(tx)}',
                          data={'transactionToken': 'TKN'}, allow_redirects=False)
        self.assertEqual(tx.state, 'done')
