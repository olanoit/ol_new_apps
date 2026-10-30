# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta

import pytz
from werkzeug.urls import url_decode, url_parse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

from odoo.addons.al_payment_pagoefectivo import const
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)

# Código del tipo de documento de identidad (catálogo 6 de SUNAT) → userDocumentType.
SUNAT_DOCUMENT_TYPES = {'1': 'DNI', '7': 'PAS'}


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    pagoefectivo_cip_url = fields.Char(string='Página del CIP', readonly=True, copy=False)
    pagoefectivo_date_expiry = fields.Datetime(string='Vencimiento del CIP', readonly=True, copy=False)

    # -------------------------------------------------------------------------
    # Generación del CIP
    # -------------------------------------------------------------------------

    def _get_specific_rendering_values(self, processing_values):
        """Genera el CIP y redirige al cliente a su página en PagoEfectivo,
        donde ve el código y dónde pagarlo. La transacción queda pendiente
        hasta la notificación de pago."""
        if self.provider_code != 'pagoefectivo':
            return super()._get_specific_rendering_values(processing_values)
        # El CIP se genera aquí mismo (llamada síncrona): su respuesta, o el
        # error, se registra en el acto.
        self = self.with_context(payment_safe_write=True)
        try:
            provider = self.provider_id
            token = provider._pagoefectivo_authorize(reference=self.reference)
            data = provider._send_api_request(
                'POST', 'cips', json=self._pagoefectivo_prepare_cip_payload(),
                reference=self.reference, pagoefectivo_token=token)
        except ValidationError as error:
            self._set_error(str(error))
            return {}
        if not data.get('cip') or not data.get('cipUrl'):
            self._set_error(_('PagoEfectivo no devolvió el código de pago.'))
            return {}
        self._pagoefectivo_apply_cip(data)

        # La página del CIP lleva parámetros: van como campos para conservarlos.
        cip_url = data['cipUrl']
        return {
            'api_url': cip_url,
            'url_params': url_decode(url_parse(cip_url).query),
        }

    def _pagoefectivo_transaction_code(self):
        """``transactionCode``: la referencia sin los caracteres que no admite
        (las de facturas llevan «/»). La referencia exacta va en
        ``additionalData``."""
        self.ensure_one()
        return re.sub(r'[^A-Za-z0-9-]', '-', self.reference)[:const.TRANSACTION_CODE_MAX_LENGTH]

    def _pagoefectivo_prepare_cip_payload(self):
        self.ensure_one()
        if not self.partner_email:
            # PagoEfectivo envía el código al correo del cliente: es obligatorio.
            raise ValidationError(_('Para pagar con PagoEfectivo, el cliente debe tener un correo electrónico.'))
        provider = self.provider_id
        expiry = provider._pagoefectivo_now() + timedelta(hours=provider.pagoefectivo_expiry_hours)
        first_name, last_name = payment_utils.split_partner_name(self.partner_name or '')
        concept = _('%(company)s — %(reference)s', company=self.company_id.name, reference=self.reference)
        payload = {
            'currency': self.currency_id.name,
            'amount': self.currency_id.round(self.amount),
            'transactionCode': self._pagoefectivo_transaction_code(),
            'dateExpiry': expiry.isoformat(),
            'paymentConcept': concept[:const.PAYMENT_CONCEPT_MAX_LENGTH],
            'additionalData': self.reference,
            'userEmail': self.partner_email,
            'userId': str(self.partner_id.id),
            'userName': first_name or self.partner_name or '',
            'userLastName': last_name or '',
            'serviceId': int(provider.pagoefectivo_service_id.strip()),
        }
        if self.company_id.email:
            payload['adminEmail'] = self.company_id.email
        document_type = self._pagoefectivo_document_type()
        number = 'l10n_pe_sunat_id_value' in self.partner_id._fields and self.partner_id.l10n_pe_sunat_id_value
        if document_type and number:
            payload.update(userDocumentType=document_type, userDocumentNumber=number)
        phone = re.sub(r'\D', '', self.partner_phone or '')
        if self.partner_country_id.code == 'PE' and len(phone) == 9:
            payload.update(userPhone=phone, userCodeCountry='+51')
        return payload

    def _pagoefectivo_document_type(self):
        """DNI o pasaporte según el tipo de identificación del cliente; el RUC
        no tiene equivalente y se omite."""
        partner = self.partner_id
        code = 'l10n_pe_sunat_id_code' in partner._fields and partner.l10n_pe_sunat_id_code
        return SUNAT_DOCUMENT_TYPES.get(code)

    def _pagoefectivo_apply_cip(self, data):
        """Guarda el CIP y deja la transacción pendiente con el código a la vista."""
        self.ensure_one()
        self.provider_reference = str(data['cip'])
        self.pagoefectivo_cip_url = data['cipUrl']
        self.pagoefectivo_date_expiry = self._pagoefectivo_parse_date(data.get('dateExpiry'))
        self._set_pending(state_message=_(
            'Código de pago (CIP) %(cip)s: páguelo en agentes, bodegas o en la banca por '
            'internet antes de que venza.', cip=data['cip']))

    @api.model
    def _pagoefectivo_parse_date(self, value):
        """Fecha de PagoEfectivo (ISO 8601, con o sin desfase) → UTC sin zona."""
        if not value:
            return False
        try:
            date = datetime.fromisoformat(value)
        except ValueError:
            return False
        if not date.tzinfo:
            date = pytz.timezone(const.TIMEZONE).localize(date)
        return date.astimezone(pytz.utc).replace(tzinfo=None)

    # -------------------------------------------------------------------------
    # Notificación
    # -------------------------------------------------------------------------

    @api.model
    def _search_by_reference(self, provider_code, payment_data):
        """La notificación identifica el pago por el CIP, que es la
        referencia del proveedor."""
        if provider_code != 'pagoefectivo':
            return super()._search_by_reference(provider_code, payment_data)
        cip = str((payment_data.get('data') or {}).get('cip') or '')
        if not cip:
            _logger.warning('Notificación de PagoEfectivo sin CIP.')
            return self
        tx = self.search(
            Domain('provider_reference', '=', cip) & Domain('provider_code', '=', 'pagoefectivo'))
        if not tx:
            _logger.warning('No hay transacción de PagoEfectivo con el CIP %s.', cip)
        return tx

    def _extract_amount_data(self, payment_data):
        if self.provider_code != 'pagoefectivo':
            return super()._extract_amount_data(payment_data)
        if payment_data.get('eventType') != const.EVENT_PAID:
            return None
        data = payment_data.get('data') or {}
        return {'amount': float(data.get('amount') or 0), 'currency_code': data.get('currency')}

    def _apply_updates(self, payment_data):
        if self.provider_code != 'pagoefectivo':
            return super()._apply_updates(payment_data)
        event = payment_data.get('eventType')
        if event == const.EVENT_PAID:
            # Un pago hecho al límite puede notificarse después de cancelar por vencimiento.
            self._set_done(extra_allowed_states=('cancel',))
        elif event == const.EVENT_EXPIRED:
            self._set_canceled(state_message=_('El código de pago (CIP) venció sin pagarse.'))
        else:
            _logger.info('Evento de PagoEfectivo no procesado para %s: %s', self.reference, event)

    # -------------------------------------------------------------------------
    # Vencimiento
    # -------------------------------------------------------------------------

    @api.model
    def _cron_pagoefectivo_cancel_expired(self):
        """Cancela las transacciones pendientes cuyo CIP venció (con un margen
        para la notificación de un pago hecho al límite)."""
        limit = fields.Datetime.now() - timedelta(hours=const.EXPIRY_GRACE_HOURS)
        expired = self.search([
            ('provider_code', '=', 'pagoefectivo'),
            ('state', '=', 'pending'),
            ('pagoefectivo_date_expiry', '!=', False),
            ('pagoefectivo_date_expiry', '<', limit),
        ])
        # Sin llamada externa: la cancelación se puede repetir sin riesgo.
        for tx in expired.with_context(payment_safe_write=True):
            tx._set_canceled(state_message=_('El código de pago (CIP) venció sin pagarse.'))
