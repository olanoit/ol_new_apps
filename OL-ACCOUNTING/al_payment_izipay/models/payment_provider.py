# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.al_payment_izipay import const


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('izipay', 'Izipay')], ondelete={'izipay': 'set default'})
    izipay_shop_id = fields.Char(
        string='Identificador de la tienda',
        help='Usuario de la tabla de claves de la API REST (clave n.° 1): el número de la tienda.',
        copy=False,
    )
    izipay_password = fields.Char(
        string='Contraseña',
        help='Contraseña de la API REST (clave n.° 2: testpassword_… o prodpassword_…). Solo la '
             'usa el servidor: crea los pagos, consulta su estado, anula y reembolsa, y verifica '
             'la firma de la IPN.',
        copy=False,
        groups='base.group_system',
    )
    izipay_public_key = fields.Char(
        string='Clave pública',
        help='Clave pública de la API REST (clave n.° 3: <tienda>:testpublickey_… o '
             '<tienda>:publickey_…): la usa el formulario de pago en el navegador.',
        copy=False,
    )
    izipay_webhook_url = fields.Char(
        string='URL de notificación (IPN)',
        compute='_compute_izipay_webhook_url',
        help='Odoo la envía en cada pago; también puede configurarse en el Back Office Vendedor ▸ '
             'Reglas de notificación.',
    )

    @api.depends('code')
    def _compute_izipay_webhook_url(self):
        for provider in self:
            provider.izipay_webhook_url = (
                provider._izipay_get_webhook_url() if provider.code == 'izipay' else False
            )

    def _izipay_get_webhook_url(self):
        self.ensure_one()
        # web.base.url puede terminar en «/».
        return f"{self.get_base_url().rstrip('/')}/payment/izipay/webhook"

    # -------------------------------------------------------------------------
    # Funciones admitidas y monedas
    # -------------------------------------------------------------------------

    def _compute_feature_support_fields(self):
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'izipay').update({
            'support_refund': 'partial',
        })

    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'izipay':
            supported_currencies = supported_currencies.filtered(
                lambda currency: currency.name in const.SUPPORTED_CURRENCIES)
        return supported_currencies

    def _get_default_payment_method_codes(self):
        self.ensure_one()
        if self.code != 'izipay':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    @api.constrains('state', 'izipay_shop_id', 'izipay_password', 'izipay_public_key')
    def _check_izipay_credentials(self):
        """Las claves son obligatorias para activar el proveedor y deben
        corresponder al modo: de test en «Modo de prueba», de producción en
        «Activado». La clave pública empieza con el identificador de la tienda."""
        for provider in self.filtered(lambda p: p.code == 'izipay' and p.state != 'disabled'):
            # La contraseña está restringida a administradores.
            provider_sudo = provider.sudo()
            shop_id = provider_sudo.izipay_shop_id
            password = provider_sudo.izipay_password
            public_key = provider_sudo.izipay_public_key
            if not shop_id or not password or not public_key:
                raise ValidationError(_(
                    'Indique el identificador de la tienda, la contraseña y la clave pública de '
                    'Izipay antes de activar el proveedor.'))
            test = provider.state == 'test'
            password_prefix = 'testpassword_' if test else 'prodpassword_'
            public_prefix = f"{shop_id}:{'testpublickey_' if test else 'publickey_'}"
            if not password.startswith(password_prefix):
                raise ValidationError(_(
                    'La contraseña de Izipay debe empezar con «%(prefix)s» en este modo.',
                    prefix=password_prefix))
            if not public_key.startswith(public_prefix):
                raise ValidationError(_(
                    'La clave pública de Izipay debe empezar con «%(prefix)s» en este modo.',
                    prefix=public_prefix))

    # -------------------------------------------------------------------------
    # Cliente HTTP (API REST V4)
    # -------------------------------------------------------------------------

    def _build_request_url(self, endpoint, **kwargs):
        if self.code != 'izipay':
            return super()._build_request_url(endpoint, **kwargs)
        return f'{const.API_URL}{endpoint}'

    def _build_request_headers(self, method, endpoint, payload, **kwargs):
        if self.code != 'izipay':
            return super()._build_request_headers(method, endpoint, payload, **kwargs)
        return {'Content-Type': 'application/json'}

    def _build_request_auth(self, **kwargs):
        if self.code != 'izipay':
            return super()._build_request_auth(**kwargs)
        # La contraseña solo vive en el servidor y está restringida a
        # administradores: se lee con sudo para que el cliente pueda pagar.
        provider_sudo = self.sudo()
        return provider_sudo.izipay_shop_id, provider_sudo.izipay_password

    def _parse_response_content(self, response, **kwargs):
        """Izipay responde HTTP 200 también a los errores, con ``status:
        ERROR``: se convierten en ``ValidationError`` como un error HTTP."""
        if self.code != 'izipay':
            return super()._parse_response_content(response, **kwargs)
        content = response.json()
        if content.get('status') != 'SUCCESS':
            raise ValidationError(_(
                'Izipay rechazó la solicitud.\n%s', self._izipay_error_message(content.get('answer'))))
        return content['answer']

    def _parse_response_error(self, response):
        if self.code != 'izipay':
            return super()._parse_response_error(response)
        return self._izipay_error_message(response.json().get('answer')) or response.text

    @api.model
    def _izipay_error_message(self, answer):
        """Mensaje legible de un ``V4/WebService/WebServiceError``."""
        answer = answer or {}
        parts = [answer.get('errorCode'), answer.get('errorMessage'), answer.get('detailedErrorMessage')]
        return ' — '.join(part for part in parts if part)
