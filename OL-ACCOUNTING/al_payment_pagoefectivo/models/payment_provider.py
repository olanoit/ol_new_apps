# -*- coding: utf-8 -*-
import hashlib
from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.al_payment_pagoefectivo import const


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('pagoefectivo', 'PagoEfectivo')], ondelete={'pagoefectivo': 'set default'})
    pagoefectivo_service_id = fields.Char(
        string='Código de servicio',
        help='Identificador del servicio (idService) que PagoEfectivo asigna al comercio.',
        copy=False,
    )
    pagoefectivo_access_key = fields.Char(
        string='Clave de acceso',
        help='Access key del servicio, del panel de PagoEfectivo.',
        copy=False,
        groups='base.group_system',
    )
    pagoefectivo_secret_key = fields.Char(
        string='Clave secreta',
        help='Secret key del servicio. Firma la autorización y verifica la firma de las '
             'notificaciones de pago; nunca sale del servidor.',
        copy=False,
        groups='base.group_system',
    )
    pagoefectivo_expiry_hours = fields.Integer(
        string='Vigencia del CIP (horas)',
        default=const.DEFAULT_EXPIRY_HOURS,
        help='Plazo que tiene el cliente para pagar el código. Vencido, la transacción se cancela.',
    )
    pagoefectivo_webhook_url = fields.Char(
        string='URL de notificación',
        compute='_compute_pagoefectivo_webhook_url',
        help='Regístrela en el panel de PagoEfectivo: allí llega el aviso de cada CIP pagado.',
    )

    @api.depends('code')
    def _compute_pagoefectivo_webhook_url(self):
        for provider in self:
            provider.pagoefectivo_webhook_url = (
                provider._pagoefectivo_get_webhook_url() if provider.code == 'pagoefectivo' else False
            )

    def _pagoefectivo_get_webhook_url(self):
        self.ensure_one()
        # web.base.url puede terminar en «/».
        return f"{self.get_base_url().rstrip('/')}/payment/pagoefectivo/webhook"

    # -------------------------------------------------------------------------
    # Funciones admitidas y monedas
    # -------------------------------------------------------------------------

    def _compute_feature_support_fields(self):
        super()._compute_feature_support_fields()
        # Pago en efectivo o por banca: no hay devolución desde la API.
        self.filtered(lambda p: p.code == 'pagoefectivo').update({
            'support_refund': 'none',
        })

    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'pagoefectivo':
            supported_currencies = supported_currencies.filtered(
                lambda currency: currency.name in const.SUPPORTED_CURRENCIES)
        return supported_currencies

    def _get_default_payment_method_codes(self):
        self.ensure_one()
        if self.code != 'pagoefectivo':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    @api.constrains('state', 'pagoefectivo_service_id', 'pagoefectivo_access_key',
                    'pagoefectivo_secret_key', 'pagoefectivo_expiry_hours')
    def _check_pagoefectivo_credentials(self):
        for provider in self.filtered(lambda p: p.code == 'pagoefectivo' and p.state != 'disabled'):
            # Las claves están restringidas a administradores.
            provider_sudo = provider.sudo()
            if not (provider_sudo.pagoefectivo_service_id and provider_sudo.pagoefectivo_access_key
                    and provider_sudo.pagoefectivo_secret_key):
                raise ValidationError(_(
                    'Indique el código de servicio, la clave de acceso y la clave secreta de '
                    'PagoEfectivo antes de activar el proveedor.'))
            if not provider_sudo.pagoefectivo_service_id.strip().isdigit():
                raise ValidationError(_('El código de servicio de PagoEfectivo es numérico.'))
            if provider.pagoefectivo_expiry_hours <= 0:
                raise ValidationError(_('La vigencia del CIP debe ser de al menos una hora.'))

    # -------------------------------------------------------------------------
    # Cliente HTTP
    # -------------------------------------------------------------------------

    def _pagoefectivo_api_url(self):
        self.ensure_one()
        return const.API_URL_PROD if self.state == 'enabled' else const.API_URL_TEST

    def _build_request_url(self, endpoint, **kwargs):
        if self.code != 'pagoefectivo':
            return super()._build_request_url(endpoint, **kwargs)
        return f'{self._pagoefectivo_api_url()}{endpoint}'

    def _build_request_headers(self, method, endpoint, payload, **kwargs):
        if self.code != 'pagoefectivo':
            return super()._build_request_headers(method, endpoint, payload, **kwargs)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if kwargs.get('pagoefectivo_token'):
            headers.update({
                'Authorization': f"Bearer {kwargs['pagoefectivo_token']}",
                'Accept-Language': 'es-PE',
                'Origin': 'web',
            })
        return headers

    def _parse_response_content(self, response, **kwargs):
        """PagoEfectivo envuelve la respuesta en ``{code, message, data}``: un
        ``code`` distinto de 100 es un rechazo aunque el HTTP sea 200."""
        if self.code != 'pagoefectivo':
            return super()._parse_response_content(response, **kwargs)
        content = response.json()
        if str(content.get('code')) != const.CODE_SUCCESS:
            raise ValidationError(_(
                'PagoEfectivo rechazó la solicitud.\n%s', self._pagoefectivo_error_message(content)))
        return content.get('data') or {}

    def _parse_response_error(self, response):
        if self.code != 'pagoefectivo':
            return super()._parse_response_error(response)
        return self._pagoefectivo_error_message(response.json()) or response.text

    @api.model
    def _pagoefectivo_error_message(self, content):
        """Mensaje legible: el general y el de cada campo observado
        (``data: [{code, message, field}]``)."""
        content = content or {}
        parts = [f"{content.get('code') or ''} {content.get('message') or ''}".strip()]
        details = content.get('data')
        if isinstance(details, list):
            for detail in details:
                if isinstance(detail, dict):
                    field = f" ({detail['field']})" if detail.get('field') else ''
                    parts.append(f"{detail.get('code') or ''} {detail.get('message') or ''}{field}".strip())
        return ' — '.join(part for part in parts if part)

    @api.model
    def _pagoefectivo_now(self):
        return datetime.now(pytz.timezone(const.TIMEZONE)).replace(microsecond=0)

    def _pagoefectivo_authorize(self, reference=None):
        """Pide el token de la API: ``hashString`` es el SHA-256 de
        ``idService.accessKey.secretKey.dateRequest``, con la fecha en hora
        de Lima (``yyyy-mm-ddThh:mm:ss-05:00``).

        :return: el token Bearer.
        """
        self.ensure_one()
        # Las claves solo viven en el servidor y están restringidas a
        # administradores: se leen con sudo para que el cliente pueda pagar.
        provider_sudo = self.sudo()
        service_id = provider_sudo.pagoefectivo_service_id.strip()
        access_key = provider_sudo.pagoefectivo_access_key
        date_request = self._pagoefectivo_now().isoformat()
        hash_string = hashlib.sha256(
            f'{service_id}.{access_key}.{provider_sudo.pagoefectivo_secret_key}.{date_request}'.encode()
        ).hexdigest()
        data = self._send_api_request('POST', 'authorizations', reference=reference, json={
            'accessKey': access_key,
            'idService': int(service_id),
            'dateRequest': date_request,
            'hashString': hash_string,
        })
        if not data.get('token'):
            raise ValidationError(_('PagoEfectivo no devolvió el token de autorización.'))
        return data['token']
