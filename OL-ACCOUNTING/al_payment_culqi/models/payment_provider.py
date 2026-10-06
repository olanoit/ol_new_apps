# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.al_payment_culqi import const


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('culqi', 'Culqi')], ondelete={'culqi': 'set default'})
    culqi_public_key = fields.Char(
        string='Llave pública',
        help='Llave pública de CulqiPanel (pk_test_… o pk_live_…): la usan el checkout y 3DS '
             'en el navegador.',
        copy=False,
    )
    culqi_secret_key = fields.Char(
        string='Llave secreta',
        help='Llave secreta de CulqiPanel (sk_test_… o sk_live_…): solo la usa el servidor '
             'para crear cargos y devoluciones.',
        copy=False,
        groups='base.group_system',
    )
    culqi_rsa_id = fields.Char(
        string='ID de la llave RSA',
        help='Opcional: ID de la llave RSA de CulqiPanel (xculqirsaid) para cifrar los datos '
             'del checkout.',
        copy=False,
    )
    culqi_rsa_public_key = fields.Text(
        string='Llave pública RSA',
        help='Opcional: llave pública RSA de CulqiPanel (rsapublickey).',
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Funciones admitidas y monedas
    # -------------------------------------------------------------------------

    def _compute_feature_support_fields(self):
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'culqi').update({
            'support_refund': 'partial',
        })

    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'culqi':
            supported_currencies = supported_currencies.filtered(
                lambda currency: currency.name in const.SUPPORTED_CURRENCIES)
        return supported_currencies

    def _get_default_payment_method_codes(self):
        self.ensure_one()
        if self.code != 'culqi':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    @api.constrains('state', 'culqi_public_key', 'culqi_secret_key')
    def _check_culqi_credentials(self):
        """Las llaves son obligatorias para activar el proveedor, y deben
        corresponder al modo: de prueba en «Modo de prueba», de producción en
        «Activado»."""
        for provider in self.filtered(lambda p: p.code == 'culqi' and p.state != 'disabled'):
            # La llave secreta está restringida a administradores.
            provider_sudo = provider.sudo()
            if not provider_sudo.culqi_public_key or not provider_sudo.culqi_secret_key:
                raise ValidationError(_('Indique las llaves pública y secreta de Culqi antes de activar el proveedor.'))
            prefix = 'test' if provider.state == 'test' else 'live'
            for label, key, kind in ((_('pública'), provider_sudo.culqi_public_key, 'pk'),
                                     (_('secreta'), provider_sudo.culqi_secret_key, 'sk')):
                if not key.startswith(f'{kind}_{prefix}_'):
                    raise ValidationError(_(
                        'La llave %(label)s de Culqi debe empezar con «%(prefix)s» en este modo.',
                        label=label, prefix=f'{kind}_{prefix}_'))

    # -------------------------------------------------------------------------
    # Cliente HTTP (API v2)
    # -------------------------------------------------------------------------

    def _build_request_url(self, endpoint, **kwargs):
        if self.code != 'culqi':
            return super()._build_request_url(endpoint, **kwargs)
        return f'{const.API_URL}{endpoint}'

    def _build_request_headers(self, method, endpoint, payload, **kwargs):
        if self.code != 'culqi':
            return super()._build_request_headers(method, endpoint, payload, **kwargs)
        # La llave secreta solo vive en el servidor y está restringida a
        # administradores: se lee con sudo para que el cliente pueda pagar.
        provider_sudo = self.sudo()
        return {
            'Authorization': f'Bearer {provider_sudo.culqi_secret_key}',
            'Content-Type': 'application/json',
        }

    def _parse_response_error(self, response):
        """Mensaje de error de Culqi (objeto ``error``): el mensaje para el
        cliente, y si no hay, el del comercio."""
        if self.code != 'culqi':
            return super()._parse_response_error(response)
        content = response.json()
        return content.get('user_message') or content.get('merchant_message') or response.text
