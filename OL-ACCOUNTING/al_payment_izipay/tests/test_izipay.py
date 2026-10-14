# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.tests.http_common import PaymentHttpCommon

from .common import IzipayCommon

API = 'odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request'


def fake_api(responses):
    """Simula ``_send_api_request`` respondiendo según el servicio web."""
    def _call(method, endpoint, **kwargs):
        response = responses[endpoint]
        if isinstance(response, Exception):
            raise response
        return response
    return Mock(side_effect=_call)


@tagged('post_install', '-at_install')
class TestIzipay(IzipayCommon, PaymentHttpCommon):

    def setUp(self):
        super().setUp()
        # Con varias bases en el servidor, la sesión anónima debe fijar la
        # base de la prueba para que las rutas públicas la encuentren.
        self.authenticate(None, None)

    def _create_izipay_tx(self, **values):
        return self._create_transaction('direct', reference=self.reference, **values)

    # ------------------------------------------------------------ proveedor
    def test_provider_supports_pen_usd_and_refunds(self):
        currencies = self.provider._get_supported_currencies().mapped('name')
        self.assertEqual(sorted(currencies), ['PEN', 'USD'])
        self.assertEqual(self.provider.support_refund, 'partial')
        self.assertEqual(self.provider.payment_method_ids.mapped('code'), ['card'])
        self.assertTrue(self.provider.izipay_webhook_url.endswith('/payment/izipay/webhook'))

    def test_webhook_url_without_double_slash(self):
        self.env['ir.config_parameter'].set_param('web.base.url', 'https://tienda.example.com/')
        self.assertEqual(self.provider._izipay_get_webhook_url(),
                         'https://tienda.example.com/payment/izipay/webhook')

    def test_credentials_must_match_mode(self):
        # assertRaises de Odoo abre un savepoint: la escritura rechazada se deshace.
        cases = [
            ({'state': 'enabled'}, 'prodpassword_'),
            ({'izipay_public_key': '11111111:testpublickey_x'}, '89289758:testpublickey_'),
            ({'izipay_password': False}, 'contraseña'),
        ]
        for values, message in cases:
            with self.assertRaises(ValidationError) as error:
                self.provider.write(values)
            self.assertIn(message, str(error.exception))

    def test_request_uses_basic_auth_with_shop_and_password(self):
        self.assertEqual(self.provider._build_request_auth(), ('89289758', 'testpassword_odoo0000000000'))
        self.assertEqual(self.provider._build_request_url('Charge/CreatePayment'),
                         'https://api.micuentaweb.pe/api-payment/V4/Charge/CreatePayment')

    def test_error_status_with_http_200_raises(self):
        """Izipay responde los errores con HTTP 200 y ``status: ERROR``."""
        response = Mock()
        response.json.return_value = {'status': 'ERROR', 'answer': {
            'errorCode': 'PSP_610', 'errorMessage': 'No merchant acceptance agreement available',
            'detailedErrorMessage': 'No acceptance agreement available', '_type': 'V4/WebService/WebServiceError'}}
        with self.assertRaisesRegex(ValidationError, 'PSP_610'):
            self.provider._parse_response_content(response)
        response.json.return_value = {'status': 'SUCCESS', 'answer': self.form_token_answer}
        self.assertEqual(self.provider._parse_response_content(response), self.form_token_answer)

    # -------------------------------------------------- valores del navegador
    def test_processing_values_create_the_form_token(self):
        tx = self._create_izipay_tx()
        api = fake_api({'Charge/CreatePayment': self.form_token_answer})
        with patch(API, api):
            values = tx._get_processing_values()
        payload = api.call_args.kwargs['json']
        self.assertEqual(payload['amount'], 12050)
        self.assertEqual(payload['currency'], 'PEN')
        self.assertEqual(payload['orderId'], 'INV-2026-00001')
        self.assertEqual(payload['metadata'], {'odoo_reference': 'INV/2026/00001'})
        self.assertTrue(payload['ipnTargetUrl'].endswith('/payment/izipay/webhook'))
        self.assertEqual(payload['customer']['email'], 'rosa@example.com')
        self.assertEqual(payload['customer']['billingDetails']['identityCode'], '20131312955')
        self.assertEqual(payload['customer']['billingDetails']['country'], 'PE')
        self.assertEqual(values['izipay_form_token'], self.form_token_answer['formToken'])
        self.assertEqual(values['izipay_public_key'], '89289758:testpublickey_odoo0000000000')
        self.assertEqual(values['access_token'], payment_utils.generate_access_token(
            tx.reference, tx.partner_id.id, env=self.env))
        self.assertNotIn('testpassword_odoo0000000000', str(values))

    def test_order_id_is_limited_to_allowed_characters(self):
        tx = self._create_transaction('direct', reference='SO0042/ñ 1' + 'x' * 80)
        order_id = tx._izipay_order_id()
        self.assertRegex(order_id, r'^[A-Za-z0-9_-]+$')
        self.assertEqual(len(order_id), 64)

    # ------------------------------------------------------------ retorno
    def _return_route(self, tx, **params):
        values = {
            'reference': tx.reference,
            'partner_id': tx.partner_id.id,
            'access_token': payment_utils.generate_access_token(tx.reference, tx.partner_id.id, env=self.env),
        }
        values.update(params)
        return self.make_jsonrpc_request('/payment/izipay/return', values)

    def test_return_confirms_with_order_get(self):
        tx = self._create_izipay_tx()
        api = fake_api({'Order/Get': self._izipay_order_get([self.refused_transaction, self.paid_transaction])})
        with patch(API, api):
            result = self._return_route(tx)
        self.assertEqual(api.call_args.kwargs['json'], {'orderId': 'INV-2026-00001'})
        self.assertEqual(result['state'], 'done')
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, self.uuid)
        self.assertEqual(tx.payment_method_id.code, 'visa')

    def test_return_with_exhausted_attempts_sets_error(self):
        tx = self._create_izipay_tx()
        with patch(API, fake_api({'Order/Get': self._izipay_order_get([self.refused_transaction])})):
            result = self._return_route(tx)
        self.assertEqual(result['state'], 'error')
        self.assertIn('No funds available', tx.state_message)

    @mute_logger('odoo.addons.payment.models.payment_transaction')
    def test_return_rejects_altered_amount(self):
        tx = self._create_izipay_tx()
        altered = dict(self.paid_transaction, amount=100)
        with patch(API, fake_api({'Order/Get': self._izipay_order_get([altered])})):
            self._return_route(tx)
        self.assertEqual(tx.state, 'error')

    def test_return_ignores_transactions_of_other_references(self):
        tx = self._create_izipay_tx()
        other = dict(self.paid_transaction, metadata={'odoo_reference': 'INV-2026-00001'})
        with patch(API, fake_api({'Order/Get': self._izipay_order_get([other])})):
            result = self._return_route(tx)
        self.assertEqual(result['state'], 'draft')

    @mute_logger('odoo.http')
    def test_return_rejects_tampered_token(self):
        tx = self._create_izipay_tx()
        with patch(API) as api, self.assertRaises(Exception):
            self._return_route(tx, access_token='falso')
        api.assert_not_called()

    def test_return_does_not_query_processed_transactions(self):
        tx = self._create_izipay_tx(state='done')
        with patch(API) as api:
            result = self._return_route(tx)
        api.assert_not_called()
        self.assertEqual(result['state'], 'done')

    # ------------------------------------------------------------------ IPN
    def _ipn(self, answer, password='testpassword_odoo0000000000', **overrides):
        raw = json.dumps(answer)
        data = {
            'kr-hash-key': 'password',
            'kr-hash-algorithm': 'sha256_hmac',
            'kr-answer-type': 'V4/Payment',
            'kr-answer': raw,
            'kr-src': 'EMBEDDED_FORM',
            'kr-hash': hmac.new(password.encode(), raw.encode(), hashlib.sha256).hexdigest(),
        }
        data.update(overrides)
        return self._make_http_post_request(self._build_url('/payment/izipay/webhook'), data=data)

    def test_ipn_confirms_payment(self):
        tx = self._create_izipay_tx()
        response = self._ipn(self._izipay_payment_answer([self.paid_transaction], 'PAID'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, 'OK')
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, self.uuid)

    def test_ipn_of_retryable_refusal_keeps_transaction_open(self):
        tx = self._create_izipay_tx()
        self._ipn(self._izipay_payment_answer([self.refused_transaction], 'UNPAID', order_cycle='OPEN'))
        self.assertEqual(tx.state, 'draft')
        self._ipn(self._izipay_payment_answer([self.refused_transaction], 'UNPAID'))
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.al_payment_izipay.controllers.main', 'odoo.http')
    def test_ipn_with_invalid_signature_is_rejected(self):
        tx = self._create_izipay_tx()
        response = self._ipn(self._izipay_payment_answer([self.paid_transaction], 'PAID'), password='otra')
        self.assertEqual(response.status_code, 403)
        response = self._ipn(self._izipay_payment_answer([self.paid_transaction], 'PAID'),
                             **{'kr-hash-key': 'sha256_hmac'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(tx.state, 'draft')

    def test_ipn_after_done_does_not_change_the_transaction(self):
        """El aviso de una anulación posterior no toca el pago confirmado:
        la devolución tiene su propia transacción."""
        tx = self._create_izipay_tx(state='done', provider_reference=self.uuid)
        cancelled = dict(self.paid_transaction, status='UNPAID', detailedStatus='CANCELLED')
        self._ipn(self._izipay_payment_answer([cancelled], 'UNPAID'))
        self.assertEqual(tx.state, 'done')

    # ----------------------------------------------------------- devolución
    def _refund(self, amount, current, responses):
        tx = self._create_izipay_tx(state='done', provider_reference=self.uuid)
        api = fake_api({'Transaction/Get': current, **responses})
        with patch(API, api):
            refund = tx._refund(amount_to_refund=amount)
        calls = {call.args[1]: call.kwargs['json'] for call in api.call_args_list}
        return refund, calls

    def test_partial_refund_before_capture_reduces_the_amount(self):
        """Antes de la captura, AUTO anularía todo: se reduce el importe."""
        updated = dict(self.paid_transaction, amount=9050)
        refund, calls = self._refund(30.0, self.paid_transaction, {'Transaction/Update': updated})
        self.assertNotIn('Transaction/CancelOrRefund', calls)
        self.assertEqual(calls['Transaction/Update']['cardUpdate'], {'amount': 9050, 'currency': 'PEN'})
        self.assertEqual(refund.state, 'done')
        self.assertEqual(refund.amount, -30.0)

    def test_full_refund_before_capture_cancels(self):
        cancelled = dict(self.paid_transaction, status='UNPAID', detailedStatus='CANCELLED')
        refund, calls = self._refund(120.50, self.paid_transaction, {'Transaction/CancelOrRefund': cancelled})
        self.assertEqual(calls['Transaction/CancelOrRefund']['resolutionMode'], 'CANCELLATION_ONLY')
        self.assertEqual(calls['Transaction/CancelOrRefund']['amount'], 12050)
        self.assertEqual(refund.state, 'done')

    def test_refund_after_capture_creates_a_credit(self):
        captured = dict(self.paid_transaction, detailedStatus='CAPTURED')
        credit = self._izipay_transaction('9f1c0e2a5b7d4c3e8a6b1d2c3e4f5a6b', 'PAID', 'CAPTURED',
                                          amount=3000, operationType='CREDIT')
        refund, calls = self._refund(30.0, captured, {'Transaction/CancelOrRefund': credit})
        self.assertEqual(calls['Transaction/CancelOrRefund']['resolutionMode'], 'REFUND_ONLY')
        self.assertEqual(calls['Transaction/CancelOrRefund']['amount'], 3000)
        self.assertEqual(refund.state, 'done')
        self.assertEqual(refund.provider_reference, '9f1c0e2a5b7d4c3e8a6b1d2c3e4f5a6b')

    def test_refund_of_cancelled_transaction_is_refused(self):
        cancelled = dict(self.paid_transaction, status='UNPAID', detailedStatus='CANCELLED')
        refund, calls = self._refund(30.0, cancelled, {})
        self.assertEqual(list(calls), ['Transaction/Get'])
        self.assertEqual(refund.state, 'error')
        self.assertIn('CANCELLED', refund.state_message)
