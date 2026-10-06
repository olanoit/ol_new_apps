# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.tests.http_common import PaymentHttpCommon

from .common import CulqiCommon

API = 'odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request'


@tagged('post_install', '-at_install')
class TestCulqi(CulqiCommon, PaymentHttpCommon):

    def setUp(self):
        super().setUp()
        # Con varias bases en el servidor, la sesión anónima debe fijar la
        # base de la prueba para que la ruta pública la encuentre.
        self.authenticate(None, None)

    # ------------------------------------------------------------ proveedor
    def test_provider_supports_pen_usd_and_refunds(self):
        currencies = self.provider._get_supported_currencies().mapped('name')
        self.assertEqual(sorted(currencies), ['PEN', 'USD'])
        self.assertEqual(self.provider.support_refund, 'partial')
        self.assertEqual(set(self.provider.payment_method_ids.mapped('code')), {'card', 'yape'})

    def test_keys_must_match_mode(self):
        with self.assertRaisesRegex(ValidationError, 'pk_live_'):
            self.provider.write({'state': 'enabled'})
        with self.assertRaisesRegex(ValidationError, 'llaves'):
            self.provider.write({'culqi_secret_key': False})

    def test_request_headers_use_secret_key(self):
        headers = self.provider._build_request_headers('POST', 'charges', {})
        self.assertEqual(headers['Authorization'], 'Bearer sk_test_odoo00000000000')
        self.assertEqual(self.provider._build_request_url('charges'), 'https://api.culqi.com/v2/charges')

    # -------------------------------------------------- valores del navegador
    def test_processing_values(self):
        tx = self._create_transaction('direct')
        values = tx._get_processing_values()
        self.assertEqual(values['culqi_amount'], 12050)
        self.assertEqual(values['culqi_currency'], 'PEN')
        self.assertEqual(values['culqi_payment_method'], 'tarjeta')
        self.assertEqual(values['culqi_public_key'], 'pk_test_odoo00000000000')
        self.assertEqual(values['access_token'], payment_utils.generate_access_token(
            tx.reference, tx.partner_id.id, env=self.env))
        self.assertNotIn('sk_test_odoo00000000000', str(values))

    def test_processing_values_yape(self):
        yape = self.env.ref('al_payment_culqi.payment_method_yape')
        tx = self._create_transaction('direct', payment_method_id=yape.id)
        self.assertEqual(tx._get_processing_values()['culqi_payment_method'], 'yape')

    # ----------------------------------------------------------------- cargo
    def test_charge_payload(self):
        tx = self._create_transaction('direct')
        payload = tx._culqi_prepare_charge_payload(self.token, 'device-123', {
            'eci': '05', 'xid': 'X', 'cavv': 'C', 'protocolVersion': '2.1.0',
            'directoryServerTransactionId': 'D', 'ignored': 'x'})
        self.assertEqual(payload['amount'], 12050)
        self.assertEqual(payload['currency_code'], 'PEN')
        self.assertEqual(payload['email'], 'rosa@example.com')
        self.assertEqual(payload['source_id'], self.token)
        self.assertEqual(payload['antifraud_details']['device_finger_print_id'], 'device-123')
        self.assertEqual(payload['antifraud_details']['country_code'], 'PE')
        self.assertEqual(payload['antifraud_details']['first_name'], 'Rosa María Quispe')
        self.assertEqual(set(payload['authentication_3DS']),
                         {'eci', 'xid', 'cavv', 'protocolVersion', 'directoryServerTransactionId'})

    def test_successful_charge_sets_done(self):
        tx = self._create_transaction('direct')
        with patch(API, return_value=self.charge_data) as api:
            tx._process('culqi', tx._culqi_create_charge(self.token))
        self.assertEqual(api.call_args.args[:2], ('POST', 'charges'))
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, 'chr_test_kEazTaQBDtzNdwFr')

    @mute_logger('odoo.addons.payment.models.payment_transaction')
    def test_declined_charge_sets_error_with_culqi_message(self):
        tx = self._create_transaction('direct')
        error = ValidationError('El proveedor de pago rechazó la solicitud.\nSu tarjeta no tiene fondos suficientes.')
        with patch(API, side_effect=error):
            tx._process('culqi', tx._culqi_create_charge(self.token))
        self.assertEqual(tx.state, 'error')
        self.assertIn('fondos suficientes', tx.state_message)

    @mute_logger('odoo.addons.payment.models.payment_transaction')
    def test_charge_amount_mismatch_is_rejected(self):
        tx = self._create_transaction('direct')
        with patch(API, return_value={**self.charge_data, 'amount': 100}):
            tx._process('culqi', tx._culqi_create_charge(self.token))
        self.assertEqual(tx.state, 'error')

    def test_missing_email_is_rejected_without_calling_culqi(self):
        tx = self._create_transaction('direct')
        tx.partner_email = False
        with patch(API) as api:
            data = tx._culqi_create_charge(self.token)
        api.assert_not_called()
        self.assertEqual(data['object'], 'error')

    # ----------------------------------------------------------- devolución
    def test_partial_refund(self):
        tx = self._create_transaction('direct', state='done', provider_reference='chr_test_kEazTaQBDtzNdwFr')
        with patch(API, return_value=self.refund_data) as api:
            refund = tx._refund(amount_to_refund=30.0)
        self.assertEqual(api.call_args.args[:2], ('POST', 'refunds'))
        self.assertEqual(api.call_args.kwargs['json'], {
            'amount': 3000, 'charge_id': 'chr_test_kEazTaQBDtzNdwFr', 'reason': 'solicitud_comprador'})
        self.assertEqual(refund.state, 'done')
        self.assertEqual(refund.amount, -30.0)
        self.assertEqual(refund.provider_reference, 'ref_test_TTfLAgaA8nz8PWbO')

    # ------------------------------------------------------------- endpoint
    def _charge_route(self, tx, **params):
        values = {
            'reference': tx.reference,
            'partner_id': tx.partner_id.id,
            'access_token': payment_utils.generate_access_token(tx.reference, tx.partner_id.id, env=self.env),
            'source_id': self.token,
        }
        values.update(params)
        return self.make_jsonrpc_request('/payment/culqi/charge', values)

    def test_route_charges_and_processes(self):
        tx = self._create_transaction('direct')
        with patch(API, return_value=self.charge_data):
            result = self._charge_route(tx)
        self.assertEqual(result['state'], 'done')
        self.assertEqual(tx.state, 'done')

    def test_route_returns_review_for_3ds(self):
        tx = self._create_transaction('direct')
        with patch(API, return_value=self.review_data):
            result = self._charge_route(tx)
        self.assertEqual(result['action'], 'review')
        self.assertEqual(tx.state, 'draft')
        # Segundo intento con los parámetros 3DS: Culqi acepta el cargo.
        with patch(API, return_value=self.charge_data) as api:
            result = self._charge_route(tx, authentication_3ds={'eci': '05', 'cavv': 'C', 'xid': 'X'})
        self.assertEqual(api.call_args.kwargs['json']['authentication_3DS']['eci'], '05')
        self.assertEqual(result['state'], 'done')

    @mute_logger('odoo.http')
    def test_route_rejects_tampered_token(self):
        tx = self._create_transaction('direct')
        with patch(API) as api, self.assertRaises(Exception):
            self._charge_route(tx, access_token='falso')
        api.assert_not_called()

    @mute_logger('odoo.http')
    def test_route_does_not_charge_twice(self):
        tx = self._create_transaction('direct', state='done')
        with patch(API) as api, self.assertRaises(Exception):
            self._charge_route(tx)
        api.assert_not_called()
