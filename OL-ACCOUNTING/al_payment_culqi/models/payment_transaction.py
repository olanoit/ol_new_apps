# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import ValidationError

from odoo.addons.al_payment_culqi import const
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # -------------------------------------------------------------------------
    # Valores para el navegador
    # -------------------------------------------------------------------------

    def _get_specific_processing_values(self, processing_values):
        """Lo que necesita el checkout en el navegador. La llave secreta
        nunca sale del servidor."""
        if self.provider_code != 'culqi':
            return super()._get_specific_processing_values(processing_values)
        provider = self.provider_id
        amount = payment_utils.to_minor_currency_units(self.amount, self.currency_id)
        return {
            # Firma la referencia y el cliente: /payment/culqi/charge la exige.
            'access_token': payment_utils.generate_access_token(
                processing_values['reference'], processing_values['partner_id'], env=self.env),
            'culqi_public_key': provider.culqi_public_key,
            'culqi_rsa_id': provider.culqi_rsa_id or '',
            'culqi_rsa_public_key': provider.culqi_rsa_public_key or '',
            'culqi_title': self.company_id.name,
            'culqi_amount': amount,
            'culqi_currency': self.currency_id.name,
            'culqi_email': self.partner_email or '',
            'culqi_payment_method': const.PAYMENT_METHODS_MAPPING.get(self.payment_method_code, 'tarjeta'),
            'culqi_3ds_allowed': const.THREEDS_MIN_AMOUNT <= amount <= const.THREEDS_MAX_AMOUNT,
        }

    # -------------------------------------------------------------------------
    # Cargo
    # -------------------------------------------------------------------------

    def _culqi_prepare_charge_payload(self, source_id, device_id=None, authentication_3ds=None):
        self.ensure_one()
        first_name, last_name = payment_utils.split_partner_name(self.partner_name or '')
        antifraud = {
            'first_name': first_name or self.partner_name or '',
            'last_name': last_name or first_name or '',
            'address': self.partner_address or '',
            'address_city': self.partner_city or '',
            'country_code': self.partner_country_id.code or '',
            'phone_number': self.partner_phone or '',
        }
        if device_id:
            antifraud['device_finger_print_id'] = device_id
        payload = {
            'amount': payment_utils.to_minor_currency_units(self.amount, self.currency_id),
            'currency_code': self.currency_id.name,
            'email': self.partner_email,
            'source_id': source_id,
            'capture': True,
            'description': self.reference[:80],
            'metadata': {'odoo_reference': self.reference},
            'antifraud_details': {key: value for key, value in antifraud.items() if value},
        }
        if authentication_3ds:
            payload['authentication_3DS'] = {
                key: authentication_3ds[key]
                for key in ('eci', 'xid', 'cavv', 'protocolVersion', 'directoryServerTransactionId')
                if authentication_3ds.get(key)
            }
        return payload

    def _culqi_create_charge(self, source_id, device_id=None, authentication_3ds=None):
        """Crea el cargo en Culqi y devuelve los datos para ``_process``.

        - Cargo creado (201): el objeto ``charge``.
        - 3DS requerido (200): ``{'action_code': 'REVIEW', ...}``. No es un
          estado final: el navegador autentica y vuelve a llamar con los
          parámetros 3DS.
        - Rechazo (4xx/5xx): ``{'object': 'error', 'user_message': ...}``.
        """
        self.ensure_one()
        if not self.partner_email:
            return self._culqi_error_data(_('Culqi exige el correo electrónico del cliente para cobrar.'))
        payload = self._culqi_prepare_charge_payload(source_id, device_id, authentication_3ds)
        try:
            response = self.provider_id._send_api_request(
                'POST', 'charges', json=payload, reference=self.reference)
        except ValidationError as error:
            return self._culqi_error_data(str(error))
        return {**response, 'reference': self.reference}

    def _culqi_error_data(self, message):
        return {'object': 'error', 'user_message': message, 'reference': self.reference}

    # -------------------------------------------------------------------------
    # Devolución
    # -------------------------------------------------------------------------

    def _send_refund_request(self):
        if self.provider_code != 'culqi':
            return super()._send_refund_request()
        source = self.source_transaction_id
        payload = {
            'amount': payment_utils.to_minor_currency_units(-self.amount, self.currency_id),
            'charge_id': source.provider_reference,
            'reason': const.REFUND_REASON,
        }
        response = self.provider_id._send_api_request(
            'POST', 'refunds', json=payload, reference=self.reference)
        self._process('culqi', {**response, 'reference': self.reference})

    # -------------------------------------------------------------------------
    # Procesamiento
    # -------------------------------------------------------------------------

    def _extract_amount_data(self, payment_data):
        if self.provider_code != 'culqi':
            return super()._extract_amount_data(payment_data)
        if payment_data.get('object') not in ('charge', 'refund'):
            return None  # Rechazos y REVIEW no traen importe.
        return {
            'amount': payment_utils.to_major_currency_units(int(payment_data['amount']), self.currency_id),
            # La devolución no informa la moneda: es la del cargo.
            'currency_code': payment_data.get('currency_code') or self.currency_id.name,
        }

    def _apply_updates(self, payment_data):
        if self.provider_code != 'culqi':
            return super()._apply_updates(payment_data)

        kind = payment_data.get('object')
        if payment_data.get('id'):
            self.provider_reference = payment_data['id']
        if kind == 'charge':
            # Solo se recibe el objeto cargo cuando Culqi lo aceptó (HTTP 201).
            self._set_done()
        elif kind == 'refund':
            if payment_data.get('status', 'completa') == 'completa':
                self._set_done()
            else:
                self._set_pending()
        elif kind == 'error':
            self._set_error(payment_data.get('user_message') or _('Culqi rechazó el pago.'))
        else:
            _logger.warning('Respuesta de Culqi no reconocida para %s: %s', self.reference, payment_data)
            self._set_error(_('Respuesta de Culqi no reconocida.'))
