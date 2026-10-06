import json
import urllib.parse

from markupsafe import Markup

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

from odoo.addons.al_payment_niubiz import const
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)


class NiubizPaymentController(http.Controller):

    @http.route(
        const.PAYMENT_LANDING_ROUTE,
        type='http',
        auth='public',
        methods=['GET'],
        website=True,
        sitemap=False,
    )
    def niubiz_landing(self, reference=None, access_token=None, payment_error=None, **kwargs):
        """Render the Niubiz payment landing page with the payform.js decoupled form.

        Also handles retries: if the transaction is in 'error' state (declined card),
        reset it to 'pending' and generate a fresh session token so the user can
        enter a different card without creating a new order.
        """
        if not reference or not payment_utils.check_access_token(access_token, reference):
            _logger.warning("Niubiz: página de pago sin referencia o con firma inválida (%s).", reference)
            return request.redirect('/payment/status')

        tx_sudo = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', 'niubiz')],
            limit=1,
        )
        if not tx_sudo or tx_sudo.state not in ('draft', 'pending', 'error'):
            _logger.warning(
                "Niubiz landing: no valid transaction found for reference %s", reference
            )
            return request.redirect('/payment/status')

        # Reset errored transaction so a new authorization attempt can succeed
        if tx_sudo.state == 'error':
            tx_sudo.write({'state': 'pending', 'state_message': False})

        provider_sudo = tx_sudo.provider_id.sudo()

        try:
            niubiz_token = provider_sudo._niubiz_get_access_token()
            session_data = provider_sudo._niubiz_get_session_token(niubiz_token, tx_sudo)
        except ValidationError as e:
            _logger.error(
                "Niubiz landing: failed to generate session for tx %s: %s",
                reference, e
            )
            return request.render(
                'al_payment_niubiz.landing_error',
                {'error_message': str(e), 'back_url': '/shop/checkout'},
            )

        return_url = (
            f'{request.httprequest.host_url.rstrip("/")}{const.PAYMENT_RETURN_ROUTE}?'
            + urllib.parse.urlencode({'reference': reference, 'access_token': access_token})
        )

        checkout_js_url = provider_sudo._niubiz_get_checkout_url()

        # Split partner name into first/last for VisanetCheckout
        partner = tx_sudo.partner_id
        name_parts = (partner.name or '').split(' ', 1)
        cardholder_name = name_parts[0]
        cardholder_last_name = name_parts[1] if len(name_parts) > 1 else name_parts[0]

        # Serialize config as Markup (trusted server data) so QWeb doesn't HTML-escape the JSON.
        timeout_url = f'{request.httprequest.host_url.rstrip("/")}/payment/status'
        config = {
            'sessionToken': session_data['sessionKey'],
            'merchantId': provider_sudo.niubiz_merchant_id,
            'purchaseNumber': str(tx_sudo.id),
            'amount': round(tx_sudo.amount, 2),
            'currency': tx_sudo.currency_id.name,
            'returnUrl': return_url,
            'timeoutUrl': timeout_url,
            'expirationMinutes': const.SESSION_EXPIRY_MINUTES,
            'checkoutJsUrl': checkout_js_url,
            'cardholderName': cardholder_name,
            'cardholderLastName': cardholder_last_name,
            'cardholderEmail': partner.email or '',
        }

        return request.render('al_payment_niubiz.landing_page', {
            'niubiz_config_json': Markup(json.dumps(config)),
            'reference': reference,
            'payment_error': payment_error or '',
        })

    @http.route(
        const.PAYMENT_RETURN_ROUTE,
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        website=True,
        sitemap=False,
    )
    def niubiz_return(self, reference=None, access_token=None, **post_data):
        """Process the payment result posted by the Niubiz checkout.js.

        Niubiz checkout.js submits a POST to this URL after the user completes
        (or cancels) the payment in the modal. The POST body contains
        ``transactionToken`` and optionally ``channel`` (e.g. 'pagoefectivo').
        """
        if not reference or not payment_utils.check_access_token(access_token, reference):
            _logger.warning("Niubiz: retorno sin referencia o con firma inválida (%s).", reference)
            return request.redirect('/payment/status')

        transaction_token = post_data.get('transactionToken') or post_data.get('LP_RESULT_CODE')
        channel = post_data.get('channel', 'web')

        tx_sudo = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', 'niubiz')],
            limit=1,
        )
        if not tx_sudo:
            _logger.warning(
                "Niubiz return: no transaction found for reference %s", reference
            )
            return request.redirect('/payment/status')

        if not transaction_token:
            _logger.warning(
                "Niubiz return: no transactionToken received for reference %s. "
                "Post data: %s",
                reference, list(post_data.keys())
            )
            tx_sudo._set_error(
                "No se recibió el token de transacción de Niubiz. "
                "El pago puede haber sido cancelado."
            )
            return request.redirect('/payment/status')

        provider_sudo = tx_sudo.provider_id.sudo()

        # PagoEfectivo: the transactionToken IS the CIP code; authorization is not called.
        # Instead, generate the cipUrl via the dedicated PagoEfectivo API and show the CIP.
        if channel == 'pagoefectivo':
            try:
                niubiz_token = provider_sudo._niubiz_get_access_token()
                cip_data = provider_sudo._niubiz_create_pagoefectivo_cip(niubiz_token, tx_sudo)
            except ValidationError as e:
                _logger.error(
                    "Niubiz PagoEfectivo CIP creation failed for tx %s: %s", reference, e
                )
                tx_sudo._set_error(str(e))
                return request.redirect('/payment/status')

            cip = cip_data.get('cip') or transaction_token
            cip_url = cip_data.get('cipUrl', '')
            expiry_date = cip_data.get('expiryDate', '')

            tx_sudo.write({
                'provider_reference': str(cip),
                'niubiz_cip_url': cip_url,
            })
            # Transaction stays 'pending' — customer hasn't paid yet (cash payment)
            _logger.info(
                "Niubiz PagoEfectivo: tx %s assigned CIP %s (expires %s)", reference, cip, expiry_date
            )
            return request.render('al_payment_niubiz.pagoefectivo_result', {
                'cip': cip,
                'cip_url': cip_url,
                'expiry_date': expiry_date,
                'amount': tx_sudo.amount,
                'currency': tx_sudo.currency_id.name,
                'reference': reference,
            })

        # Standard card / Yape / Plin / Cuotéalo flow: authorize using the transactionToken
        try:
            niubiz_token = provider_sudo._niubiz_get_access_token()
            auth_response = provider_sudo._niubiz_authorize(
                niubiz_token, transaction_token, tx_sudo
            )
        except ValidationError as e:
            _logger.error(
                "Niubiz authorization failed for tx %s: %s", reference, e
            )
            tx_sudo._set_error(str(e))
            return request.redirect('/payment/status')

        auth_response['reference'] = reference

        _logger.info(
            "Niubiz: processing authorization response for tx %s: %s",
            reference, auth_response
        )
        tx_sudo._process('niubiz', auth_response)

        # On decline/error let the user retry on the landing page with a fresh session token.
        # On success redirect to the standard Odoo payment status page.
        if tx_sudo.state in ('error', 'cancel'):
            error_msg = urllib.parse.quote(
                tx_sudo.state_message or 'Pago rechazado. Verifique los datos e intente nuevamente.'
            )
            return request.redirect(
                f'{const.PAYMENT_LANDING_ROUTE}?reference={urllib.parse.quote(reference)}'
                f'&access_token={access_token}&payment_error={error_msg}'
            )

        return request.redirect('/payment/status')
