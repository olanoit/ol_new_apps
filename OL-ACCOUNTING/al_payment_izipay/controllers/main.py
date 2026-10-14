# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import pprint

from werkzeug.exceptions import Forbidden

from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import SQL

from odoo.addons.al_payment_izipay import const
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)


class IzipayController(http.Controller):
    _return_url = '/payment/izipay/return'
    _webhook_url = '/payment/izipay/webhook'

    @http.route(_return_url, type='jsonrpc', auth='public')
    def izipay_return(self, reference, partner_id, access_token):
        """El formulario de Izipay terminó (pago aceptado o intentos agotados).

        No se confía en la respuesta del navegador: Odoo consulta el pedido a
        Izipay con la contraseña y procesa lo que Izipay devuelve.

        :param str reference: referencia de la transacción de Odoo.
        :param int partner_id: cliente de la transacción.
        :param str access_token: firma de ``reference`` y ``partner_id``
            generada al preparar el pago.
        :return: ``{'state': …, 'message': …}``
        """
        if not payment_utils.check_access_token(access_token, reference, partner_id):
            raise ValidationError(_('Los datos del pago fueron alterados.'))

        # Las transacciones son de clientes públicos (tienda, enlaces de pago):
        # se accede con sudo tras validar la firma de la referencia.
        tx_sudo = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', 'izipay')])
        if not tx_sudo:
            raise ValidationError(_('No se encontró la transacción.'))
        # Bloquea la fila: la IPN puede llegar a la vez.
        self._lock_transaction(tx_sudo)
        if tx_sudo.state in ('draft', 'pending'):
            payment_data = tx_sudo._izipay_fetch_payment_data()
            if payment_data:
                tx_sudo._process('izipay', payment_data)
        return {'state': tx_sudo.state, 'message': tx_sudo.state_message or ''}

    @http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def izipay_webhook(self, **data):
        """IPN de Izipay: ``kr-answer`` (objeto ``V4/Payment``) firmado con la
        contraseña de la API.

        :return: ``OK`` para confirmar la recepción.
        """
        _logger.info('IPN recibida de Izipay:\n%s', pprint.pformat(
            {key: value for key, value in data.items() if key != 'kr-answer'}))
        try:
            answer = json.loads(data.get('kr-answer') or '')
        except ValueError:
            _logger.warning('IPN de Izipay sin kr-answer válido.')
            raise Forbidden()
        payment_data = request.env['payment.transaction'].sudo()._izipay_payment_data_from_answer(answer)
        # La IPN es pública: se busca con sudo y solo se procesa tras verificar
        # la firma con la contraseña del proveedor de la transacción.
        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('izipay', payment_data)
        if tx_sudo:
            self._verify_signature(data, tx_sudo)
            self._lock_transaction(tx_sudo)
            tx_sudo._process('izipay', payment_data)
        return 'OK'

    @staticmethod
    def _lock_transaction(tx_sudo):
        tx_sudo.env.cr.execute(SQL(
            'SELECT 1 FROM payment_transaction WHERE id = %s FOR NO KEY UPDATE', tx_sudo.id))
        tx_sudo.invalidate_recordset(['state'])

    @staticmethod
    def _verify_signature(data, tx_sudo):
        """``kr-hash`` es el HMAC-SHA256 (hexadecimal) de ``kr-answer`` tal
        como llega, con la contraseña de la API como clave.

        :raise Forbidden: si la firma no coincide.
        """
        received = data.get('kr-hash')
        if (not received or data.get('kr-hash-key') != const.IPN_HASH_KEY
                or data.get('kr-hash-algorithm') != const.HASH_ALGORITHM):
            _logger.warning('IPN de Izipay sin firma con la contraseña.')
            raise Forbidden()
        password = tx_sudo.provider_id.izipay_password or ''
        expected = hmac.new(password.encode(), data['kr-answer'].encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received, expected):
            _logger.warning('IPN de Izipay con firma no válida.')
            raise Forbidden()
