import base64
import time

import requests
from requests.exceptions import ConnectionError, Timeout

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.al_payment_niubiz import const
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('niubiz', "Niubiz")],
        ondelete={'niubiz': 'set default'},
    )

    niubiz_merchant_id = fields.Char(
        string="Código de comercio",
        help="Código de 9 dígitos asignado por Niubiz al momento de la afiliación.",
        required_if_provider='niubiz',
        copy=False,
    )
    niubiz_access_key = fields.Char(
        string="Usuario API (access key)",
        help="Correo electrónico o usuario proporcionado por Niubiz para acceso a la API.",
        required_if_provider='niubiz',
        copy=False,
    )
    niubiz_secret_key = fields.Char(
        string="Contraseña API (secret key)",
        help="Contraseña proporcionada por Niubiz para acceso a la API.",
        copy=False,
        groups='base.group_system',
    )
    niubiz_ruc = fields.Char(
        string="RUC del comercio",
        help="RUC de 11 dígitos del comercio. Requerido para procesar devoluciones (API de Devoluciones Niubiz).",
        copy=False,
    )

    # === COMPUTE/CONSTRAINT METHODS === #

    def _compute_feature_support_fields(self):
        super()._compute_feature_support_fields()
        for provider in self.filtered(lambda p: p.code == 'niubiz'):
            provider.support_refund = 'partial'

    @api.constrains('niubiz_merchant_id', 'niubiz_access_key', 'niubiz_secret_key', 'state')
    def _check_niubiz_credentials_before_enabling(self):
        # La contraseña está restringida a administradores: se lee con sudo.
        for provider in self.sudo():
            if provider.code == 'niubiz' and provider.state != 'disabled':
                missing = []
                if not provider.niubiz_merchant_id:
                    missing.append(_("Código de comercio"))
                if not provider.niubiz_access_key:
                    missing.append(_("Usuario API (access key)"))
                if not provider.niubiz_secret_key:
                    missing.append(_("Contraseña API (secret key)"))
                if missing:
                    raise ValidationError(
                        _("Los siguientes campos son obligatorios para activar Niubiz:\n%s",
                          "\n".join(f"  • {f}" for f in missing))
                    )

    # === BUSINESS METHODS === #

    def _get_default_payment_method_codes(self):
        self.ensure_one()
        if self.code != 'niubiz':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'niubiz':
            supported_currencies = supported_currencies.filtered(
                lambda currency: currency.name in const.SUPPORTED_CURRENCIES)
        return supported_currencies

    # === NIUBIZ API METHODS === #

    def _niubiz_request_with_retry(self, method, url, attempts=3, **kwargs):
        """Petición HTTP que se repite si la conexión falla.

        Solo para operaciones que no mueven dinero (token de seguridad,
        sesión de pago): Niubiz corta a veces el saludo TLS (SSLEOFError,
        comprobado contra el sandbox) y la petición ni siquiera llega. La
        autorización del cargo no se reintenta.
        """
        for attempt in range(1, attempts + 1):
            try:
                return requests.request(method, url, **kwargs)
            except (ConnectionError, Timeout) as error:
                _logger.warning("Niubiz: intento %s/%s a %s falló: %s", attempt, attempts, url, error)
                if attempt == attempts:
                    raise
                time.sleep(0.5 * attempt)

    def _niubiz_get_urls(self):
        self.ensure_one()
        return const.SANDBOX_URLS if self.state == 'test' else const.PROD_URLS

    def _niubiz_get_checkout_url(self):
        self.ensure_one()
        return self._niubiz_get_urls()['checkout_js']

    def _niubiz_get_access_token(self):
        """Obtain a JWT access token from the Niubiz Security API (valid 60 min)."""
        self.ensure_one()
        url = self._niubiz_get_urls()['security']
        # La contraseña solo la lee el servidor y está restringida a
        # administradores: se lee con sudo para que el cliente pueda pagar.
        provider_sudo = self.sudo()
        credentials = base64.b64encode(
            f'{provider_sudo.niubiz_access_key}:{provider_sudo.niubiz_secret_key}'.encode()
        ).decode()
        _logger.info("Niubiz: requesting access token for merchant %s", self.niubiz_merchant_id)
        try:
            response = self._niubiz_request_with_retry(
                'GET', url, headers={'Authorization': f'Basic {credentials}', 'Accept': '*/*'}, timeout=15)
            response.raise_for_status()
        except (ConnectionError, Timeout):
            raise ValidationError(
                _("No se pudo establecer conexión con Niubiz. Verifique su conexión a internet.")
            )
        except requests.exceptions.HTTPError as e:
            _logger.error("Niubiz access token error: %s - %s", e, response.text)
            raise ValidationError(
                _("Niubiz rechazó las credenciales. Verifique su Access Key y Secret Key.\n%s",
                  response.text)
            )
        return response.text.strip()

    def _niubiz_get_session_token(self, access_token, tx):
        """Create a session token for a payment transaction."""
        self.ensure_one()
        urls = self._niubiz_get_urls()
        url = urls['session'].format(merchant_id=self.niubiz_merchant_id)

        partner = tx.partner_id
        payload = {
            "channel": "web",
            "amount": round(tx.amount, 2),
            "antifraud": {
                "clientIp": self._niubiz_get_client_ip(),
                "merchantDefineData": {
                    "MDD4": partner.email or f"{partner.id}@noemail.local",
                    "MDD32": str(partner.id),
                    "MDD75": "Registrado",
                    "MDD77": 0,
                }
            },
            "dataMap": {
                "cardholderCity": partner.city or "Lima",
                "cardholderCountry": partner.country_id.code or "PE",
                "cardholderAddress": partner.street or "Sin dirección",
                "cardholderPostalCode": partner.zip or "00000",
                "cardholderState": partner.state_id.code or "LIM",
                "cardholderPhoneNumber": (partner.phone or "000000000")[:12],
            }
        }

        _logger.info(
            "Niubiz: creating session token for transaction %s (amount: %s %s)",
            tx.reference, tx.amount, tx.currency_id.name
        )
        try:
            response = self._niubiz_request_with_retry(
                'POST', url, json=payload,
                headers={'Authorization': access_token, 'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
        except Timeout:
            _logger.error(
                "Niubiz session token timeout for tx %s — endpoint: %s. "
                "Verifique que el servidor Odoo tenga acceso a las APIs de Niubiz desde Perú.",
                tx.reference, url
            )
            raise ValidationError(
                _("Tiempo de espera agotado al conectar con Niubiz. "
                  "Verifique que el servidor tenga acceso a internet y que la IP no esté bloqueada.")
            )
        except ConnectionError as e:
            _logger.error(
                "Niubiz session token connection error for tx %s — %s", tx.reference, e
            )
            raise ValidationError(
                _("No se pudo conectar con Niubiz. Verifique su conexión a internet.")
            )
        except requests.exceptions.HTTPError as e:
            error_text = response.text
            _logger.error(
                "Niubiz session token error for tx %s: %s - %s", tx.reference, e, error_text
            )
            raise ValidationError(
                _("Niubiz rechazó la creación de la sesión de pago.\n%s", error_text)
            )
        return response.json()

    def _niubiz_authorize(self, access_token, transaction_token, tx):
        """Authorize a payment using a transaction token from payform.js."""
        self.ensure_one()
        urls = self._niubiz_get_urls()
        url = urls['authorization'].format(merchant_id=self.niubiz_merchant_id)

        payload = {
            "channel": "web",
            "captureType": "manual",
            "countable": True,
            "order": {
                "tokenId": transaction_token,
                "purchaseNumber": tx.id,
                "amount": round(tx.amount, 2),
                "currency": tx.currency_id.name,
            }
        }

        _logger.info(
            "Niubiz: authorizing transaction %s (purchase #%s)", tx.reference, tx.id
        )
        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Authorization': access_token, 'Content-Type': 'application/json'},
                timeout=60,
            )
        except (ConnectionError, Timeout):
            raise ValidationError(
                _("No se pudo establecer conexión con Niubiz al autorizar el pago.")
            )

        # Niubiz returns HTTP 400 for declined cards but includes a parseable response
        # with data.ACTION_CODE. Treat these as authorization responses, not API errors.
        if response.status_code == 400:
            try:
                body = response.json()
            except Exception:
                raise ValidationError(
                    _("Error inesperado de Niubiz al autorizar el pago: %s", response.text)
                )
            if body.get('data') and body['data'].get('ACTION_CODE'):
                _logger.info(
                    "Niubiz: transaction %s declined by issuer (action code: %s)",
                    tx.reference, body['data'].get('ACTION_CODE'),
                )
                return body
            raise ValidationError(
                _("Niubiz rechazó la solicitud de autorización: %s",
                  body.get('errorMessage', response.text))
            )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            try:
                error_text = response.json().get('errorMessage', response.text)
            except Exception:
                error_text = response.text
            _logger.error(
                "Niubiz authorization error for tx %s: %s - %s", tx.reference, e, error_text
            )
            raise ValidationError(_("Error al autorizar el pago con Niubiz: %s", error_text))

        return response.json()

    def _niubiz_reverse(self, tx):
        """Send a reversa (same-day void) for a completed transaction.

        Reversa cancels a transaction before settlement. Use within the same business day
        as the original authorization. After settlement, use _niubiz_refund() instead.

        :param payment.transaction tx: The source transaction to reverse.
        :raise ValidationError: If the API call fails or the transaction cannot be reversed.
        """
        self.ensure_one()
        if not tx.niubiz_transaction_date:
            raise ValidationError(
                _("No se puede anular: no se encontró la fecha de la transacción original. "
                  "Use la devolución si el pago ya fue liquidado.")
            )

        access_token = self._niubiz_get_access_token()
        url = self._niubiz_get_urls()['reversa'].format(merchant_id=self.niubiz_merchant_id)

        payload = {
            "channel": "pasarela",
            "order": {
                "purchaseNumber": str(tx.source_transaction_id.id or tx.id),
                "transactionDate": tx.niubiz_transaction_date,
            }
        }

        _logger.info(
            "Niubiz: reversing transaction %s (purchase #%s, date: %s)",
            tx.reference, payload['order']['purchaseNumber'], tx.niubiz_transaction_date
        )
        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Authorization': access_token, 'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
        except (ConnectionError, Timeout):
            raise ValidationError(
                _("No se pudo establecer conexión con Niubiz al anular la transacción.")
            )
        except requests.exceptions.HTTPError as e:
            try:
                error_text = str(response.json())
            except Exception:
                error_text = response.text
            _logger.error(
                "Niubiz reversa error for tx %s: %s - %s", tx.reference, e, error_text
            )
            raise ValidationError(_("Niubiz rechazó la anulación.\n%s", error_text))

        result = response.json()
        _logger.info("Niubiz reversa response for tx %s: %s", tx.reference, result)
        return result

    def _niubiz_refund(self, tx, amount, comment=None, external_ref=None):
        """Send a devolución (refund) request to Niubiz.

        Devoluciones are available 48 business hours after authorization and up to 6 months.
        Supports partial refunds. Only VISA and Mastercard.

        :param payment.transaction tx: The source (original) transaction to refund.
        :param float amount: Amount to refund (cannot exceed original transaction amount).
        :param str comment: Reason for refund (max 100 chars). Defaults to generic message.
        :param str external_ref: Unique identifier for this refund (max 20 chars). Defaults to tx reference.
        :raise ValidationError: If RUC is not configured or the API call fails.
        """
        self.ensure_one()
        if not self.niubiz_ruc:
            raise ValidationError(
                _("Configure el RUC del comercio en los ajustes del proveedor de pago "
                  "Niubiz para procesar devoluciones.")
            )
        if not tx.niubiz_trace_number:
            raise ValidationError(
                _("No se puede realizar la devolución: no se encontró el número de traza "
                  "de la transacción original.")
            )

        access_token = self._niubiz_get_access_token()
        url = self._niubiz_get_urls()['refund'].format(
            merchant_id=self.niubiz_merchant_id,
            transaction_id=tx.niubiz_trace_number,
        )

        ref = (external_ref or tx.reference)[:20]
        payload = {
            "ruc": self.niubiz_ruc,
            "comment": (comment or _("Devolución desde Odoo"))[:100],
            "externalReferenceId": ref,
            "amount": round(amount, 2),
        }

        _logger.info(
            "Niubiz: refunding %.2f %s for transaction %s (trace: %s)",
            amount, tx.currency_id.name, tx.reference, tx.niubiz_trace_number
        )
        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Authorization': access_token, 'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
        except (ConnectionError, Timeout):
            raise ValidationError(
                _("No se pudo establecer conexión con Niubiz al procesar la devolución.")
            )
        except requests.exceptions.HTTPError as e:
            try:
                error_text = str(response.json())
            except Exception:
                error_text = response.text
            _logger.error(
                "Niubiz refund error for tx %s: %s - %s", tx.reference, e, error_text
            )
            raise ValidationError(_("Niubiz rechazó la devolución.\n%s", error_text))

        result = response.json()
        _logger.info("Niubiz refund response for tx %s: %s", tx.reference, result)

        # Niubiz returns errorCode 0 / CODERROR '100' for success
        data = result.get('data', {})
        code_error = data.get('CODERROR', '')
        if result.get('errorCode', -1) != 0 or code_error not in ('100', '200', 0, '0'):
            raise ValidationError(
                _("Niubiz rechazó la devolución: %s", data.get('DSCERROR') or result.get('errorMessage', 'Error desconocido'))
            )
        return result

    def _niubiz_create_pagoefectivo_cip(self, access_token, tx):
        """Create a PagoEfectivo CIP (cash payment reference) for the given transaction.

        Called when VisanetCheckout returns channel='pagoefectivo'. The CIP allows
        the customer to pay in cash at any PagoEfectivo network agent.

        :returns: dict with keys: cip (int), cipUrl (str), expiryDate (str)
        :raises ValidationError: if the API call fails.
        """
        self.ensure_one()
        url = self._niubiz_get_urls()['pagoefectivo'].format(merchant_id=self.niubiz_merchant_id)
        partner = tx.partner_id
        name_parts = (partner.name or '').split(' ', 1)
        payload = {
            "channel": "web",
            "email": partner.email or f"{partner.id}@noemail.local",
            "firstName": name_parts[0],
            "amount": round(tx.amount, 2),
            "externalTransactionId": tx.reference[:36],
        }

        _logger.info(
            "Niubiz PagoEfectivo: creating CIP for transaction %s (amount: %s %s)",
            tx.reference, tx.amount, tx.currency_id.name
        )
        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Authorization': access_token, 'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
        except (ConnectionError, Timeout):
            raise ValidationError(
                _("No se pudo establecer conexión con PagoEfectivo al crear el CIP.")
            )
        except requests.exceptions.HTTPError as e:
            try:
                error_text = response.json().get('errorMessage', response.text)
            except Exception:
                error_text = response.text
            _logger.error(
                "Niubiz PagoEfectivo error for tx %s: %s - %s", tx.reference, e, error_text
            )
            raise ValidationError(_("Error al crear el código de pago PagoEfectivo.\n%s", error_text))

        result = response.json()
        _logger.info("Niubiz PagoEfectivo CIP created for tx %s: %s", tx.reference, result)
        return result

    def _niubiz_get_client_ip(self):
        try:
            from odoo.http import request as http_request
            if http_request:
                return http_request.httprequest.environ.get(
                    'HTTP_X_FORWARDED_FOR',
                    http_request.httprequest.remote_addr or '127.0.0.1'
                ).split(',')[0].strip()
        except RuntimeError:
            pass
        return '127.0.0.1'

    @api.model
    def _niubiz_get_error_message(self, action_code):
        return const.ACTION_CODE_MESSAGES.get(
            str(action_code),
            _("Transacción rechazada (código: %s). Por favor intente nuevamente.", action_code)
        )
