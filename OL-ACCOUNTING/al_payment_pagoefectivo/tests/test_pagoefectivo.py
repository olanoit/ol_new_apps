# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon

from .common import PagoEfectivoCommon

API = 'odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request'
WEBHOOK = '/payment/pagoefectivo/webhook'


def fake_api(responses, calls=None):
    """Simula ``_send_api_request`` según el servicio y guarda las llamadas."""
    def _call(method, endpoint, **kwargs):
        if calls is not None:
            calls.append((endpoint, kwargs))
        response = responses[endpoint]
        if isinstance(response, Exception):
            raise response
        return response
    return Mock(side_effect=_call)


@tagged('post_install', '-at_install')
class TestPagoEfectivo(PagoEfectivoCommon, PaymentHttpCommon):

    def setUp(self):
        super().setUp()
        # Con varias bases en el servidor, la sesión anónima debe fijar la
        # base de la prueba para que las rutas públicas la encuentren.
        self.authenticate(None, None)

    def _create_cip_tx(self, **values):
        tx = self._create_transaction('redirect', reference=self.reference, **values)
        with patch(API, fake_api({'authorizations': self.auth_data, 'cips': self.cip_data})):
            rendering_values = tx._get_specific_rendering_values({})
        return tx, rendering_values

    # ------------------------------------------------------------ proveedor
    def test_provider_defaults(self):
        currencies = self.provider._get_supported_currencies().mapped('name')
        self.assertEqual(sorted(currencies), ['PEN', 'USD'])
        self.assertEqual(self.provider.support_refund, 'none')
        self.assertEqual(self.provider.payment_method_ids.mapped('code'), ['pagoefectivo'])
        self.assertTrue(self.provider.pagoefectivo_webhook_url.endswith(WEBHOOK))
        self.assertEqual(self.provider._build_request_url('cips'),
                         'https://pre1a.services.pagoefectivo.pe/v1/cips')

    def test_credentials_are_required_to_activate(self):
        cases = [
            ({'pagoefectivo_secret_key': False}, 'clave secreta'),
            ({'pagoefectivo_service_id': 'ABC'}, 'numérico'),
            ({'pagoefectivo_expiry_hours': 0}, 'vigencia'),
        ]
        for values, message in cases:
            with self.assertRaises(ValidationError) as error:
                self.provider.write(values)
            self.assertIn(message, str(error.exception))

    def test_authorization_signs_service_keys_and_lima_date(self):
        calls = []
        with patch(API, fake_api({'authorizations': self.auth_data}, calls)):
            token = self.provider._pagoefectivo_authorize()
        self.assertEqual(token, self.auth_data['token'])
        payload = calls[0][1]['json']
        self.assertEqual(payload['idService'], 1035)
        self.assertEqual(payload['accessKey'], 'clave-de-acceso-odoo')
        self.assertRegex(payload['dateRequest'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d-05:00$')
        expected = hashlib.sha256(
            f"1035.clave-de-acceso-odoo.{self.secret_key}.{payload['dateRequest']}".encode()).hexdigest()
        self.assertEqual(payload['hashString'], expected)
        self.assertNotIn(self.secret_key, json.dumps(payload))

    def test_bearer_header_only_with_token(self):
        self.assertNotIn('Authorization', self.provider._build_request_headers('POST', 'authorizations', {}))
        headers = self.provider._build_request_headers('POST', 'cips', {}, pagoefectivo_token='tk')
        self.assertEqual(headers['Authorization'], 'Bearer tk')

    def test_rejection_with_http_200_lists_field_errors(self):
        """Respuesta real del entorno de prueba ante una fecha no válida."""
        response = Mock()
        response.json.return_value = {'code': 111, 'message': 'Solicitud con datos inválidos.', 'data': [
            {'code': 113, 'message': 'Valor invalido.', 'field': 'DateRequest'}]}
        with self.assertRaisesRegex(ValidationError, r'113 Valor invalido\. \(DateRequest\)'):
            self.provider._parse_response_content(response)
        response.json.return_value = {'code': '100', 'message': 'Solicitud exitosa.', 'data': self.cip_data}
        self.assertEqual(self.provider._parse_response_content(response), self.cip_data)

    # ------------------------------------------------------------ CIP
    def test_cip_is_generated_and_customer_redirected(self):
        calls = []
        tx = self._create_transaction('redirect', reference=self.reference)
        with patch(API, fake_api({'authorizations': self.auth_data, 'cips': self.cip_data}, calls)):
            rendering_values = tx._get_specific_rendering_values({})
        self.assertEqual([call[0] for call in calls], ['authorizations', 'cips'])
        self.assertEqual(calls[1][1]['pagoefectivo_token'], self.auth_data['token'])
        payload = calls[1][1]['json']
        self.assertEqual(payload['amount'], 120.5)
        self.assertEqual(payload['currency'], 'PEN')
        self.assertEqual(payload['transactionCode'], 'INV-2026-00001')
        self.assertEqual(payload['additionalData'], self.reference)
        self.assertEqual(payload['userEmail'], 'rosa@example.com')
        self.assertEqual((payload['userPhone'], payload['userCodeCountry']), ('987654321', '+51'))
        self.assertEqual(payload['serviceId'], 1035)
        self.assertNotIn('userDocumentType', payload, 'El RUC no es un tipo de documento de PagoEfectivo.')
        expiry = datetime.fromisoformat(payload['dateExpiry'])
        self.assertAlmostEqual(expiry - datetime.now(expiry.tzinfo), timedelta(hours=48), delta=timedelta(minutes=5))

        self.assertEqual(tx.state, 'pending')
        self.assertEqual(tx.provider_reference, str(self.cip))
        self.assertIn(str(self.cip), tx.state_message)
        self.assertEqual(tx.pagoefectivo_date_expiry, datetime(2026, 10, 24, 15, 0, 0))
        self.assertEqual(rendering_values['api_url'], self.cip_data['cipUrl'])
        self.assertEqual(dict(rendering_values['url_params']), {'token': 'abc123', 'lang': 'es'})

    def test_customer_without_email_cannot_generate_cip(self):
        self.partner.email = False
        tx = self._create_transaction('redirect', reference=self.reference)
        with patch(API, fake_api({'authorizations': self.auth_data, 'cips': self.cip_data})):
            self.assertEqual(tx._get_specific_rendering_values({}), {})
        self.assertEqual(tx.state, 'error')
        self.assertIn('correo', tx.state_message)

    def test_rejected_cip_sets_error(self):
        tx = self._create_transaction('redirect', reference=self.reference)
        with patch(API, fake_api({'authorizations': ValidationError('508 Servicio asociado a token es inválido.')})):
            self.assertEqual(tx._get_specific_rendering_values({}), {})
        self.assertEqual(tx.state, 'error')
        self.assertIn('508', tx.state_message)

    def test_dni_is_sent_as_document(self):
        # Odoo 20: un contacto con DNI no tiene RUC (vat).
        self.partner.write({'vat': False, 'additional_identifiers': {'PE_DNI': '45678912'}})
        tx = self._create_transaction('redirect', reference=self.reference)
        payload = tx._pagoefectivo_prepare_cip_payload()
        self.assertEqual((payload['userDocumentType'], payload['userDocumentNumber']), ('DNI', '45678912'))

    # ------------------------------------------------------------ notificación
    def _post_notification(self, payload, key=None, body=None):
        body = body if body is not None else json.dumps(payload, indent=2).encode()
        signature = hmac.new((key or self.secret_key).encode(), body, hashlib.sha256).hexdigest()
        return self.url_open(WEBHOOK, data=body, headers={
            'Content-Type': 'application/json', 'PE-Signature': signature})

    @mute_logger('odoo.addons.al_payment_pagoefectivo.controllers.main')
    def test_paid_notification_confirms_payment(self):
        tx, _values = self._create_cip_tx()
        response = self._post_notification(self._notification())
        self.assertEqual(response.status_code, 200)
        self._run_processing()  # Odoo 20: la notificación se encola con _record()
        self.assertEqual(tx.state, 'done')

    @mute_logger('odoo.addons.al_payment_pagoefectivo.controllers.main')
    def test_signature_over_compact_body_is_accepted(self):
        """PagoEfectivo firma el JSON compacto aunque lo envíe con espacios."""
        tx, _values = self._create_cip_tx()
        payload = self._notification()
        pretty = json.dumps(payload, indent=2).encode()
        compact = json.dumps(payload, separators=(',', ':')).encode()
        signature = hmac.new(self.secret_key.encode(), compact, hashlib.sha256).hexdigest().upper()
        response = self.url_open(WEBHOOK, data=pretty, headers={
            'Content-Type': 'application/json', 'PE-Signature': signature})
        self.assertEqual(response.status_code, 200)
        self._run_processing()  # Odoo 20: la notificación se encola con _record()
        self.assertEqual(tx.state, 'done')

    @mute_logger('odoo.addons.al_payment_pagoefectivo.controllers.main', 'odoo.http')
    def test_notification_with_invalid_signature_is_rejected(self):
        tx, _values = self._create_cip_tx()
        response = self._post_notification(self._notification(), key='otra-clave')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(tx.state, 'pending')
        response = self.url_open(WEBHOOK, data=json.dumps(self._notification()).encode(),
                                 headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(tx.state, 'pending')

    @mute_logger('odoo.addons.al_payment_pagoefectivo.controllers.main',
                 'odoo.addons.al_payment_pagoefectivo.models.payment_transaction')
    def test_notification_of_unknown_cip_is_acknowledged(self):
        response = self._post_notification(self._notification(cip=999))
        self.assertEqual(response.status_code, 200)

    @mute_logger('odoo.addons.al_payment_pagoefectivo.controllers.main')
    def test_notification_with_altered_amount_sets_error(self):
        tx, _values = self._create_cip_tx()
        self._post_notification(self._notification(amount=12.05))
        self._run_processing()
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.al_payment_pagoefectivo.controllers.main')
    def test_expired_notification_cancels(self):
        tx, _values = self._create_cip_tx()
        self._post_notification(self._notification(event='cip.expired'))
        self._run_processing()
        self.assertEqual(tx.state, 'cancel')

    # ------------------------------------------------------------ vencimiento
    def test_cron_cancels_expired_cip_and_late_payment_still_confirms(self):
        tx, _values = self._create_cip_tx()
        tx = tx.with_context(payment_safe_write=True)
        tx.pagoefectivo_date_expiry = fields.Datetime.now() - timedelta(hours=1)
        self.env['payment.transaction']._cron_pagoefectivo_cancel_expired()
        self.assertEqual(tx.state, 'pending', 'Dentro del margen no se cancela.')
        tx.pagoefectivo_date_expiry = fields.Datetime.now() - timedelta(hours=3)
        self.env['payment.transaction']._cron_pagoefectivo_cancel_expired()
        self.assertEqual(tx.state, 'cancel')
        tx.with_context(payment_safe_write=True)._process(self._notification())
        self.assertEqual(tx.state, 'done')
