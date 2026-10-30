# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import pprint

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request
from odoo.tools import SQL

from odoo.addons.al_payment_pagoefectivo import const
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)


class PagoEfectivoController(http.Controller):
    _webhook_url = '/payment/pagoefectivo/webhook'

    @http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def pagoefectivo_webhook(self):
        """Notificación de PagoEfectivo: JSON ``{eventType, operationNumber,
        data: {cip, currency, amount, paymentDate, transactionCode}}`` firmado
        en la cabecera ``PE-Signature``.

        :return: respuesta vacía con HTTP 200 para confirmar la recepción.
        """
        body = request.httprequest.get_data()
        try:
            payment_data = json.loads(body)
        except ValueError:
            _logger.warning('Notificación de PagoEfectivo sin JSON válido.')
            raise Forbidden()
        if not isinstance(payment_data, dict):
            raise Forbidden()
        _logger.info('Notificación recibida de PagoEfectivo:\n%s', pprint.pformat(payment_data))
        # La notificación es pública: se busca con sudo y solo se procesa tras
        # verificar la firma con la clave secreta del proveedor de la transacción.
        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('pagoefectivo', payment_data)
        if tx_sudo:
            self._verify_signature(body, request.httprequest.headers.get(const.SIGNATURE_HEADER), tx_sudo)
            self._lock_transaction(tx_sudo)
            tx_sudo._record(payment_data)
        return request.make_response('', status=200)

    @staticmethod
    def _lock_transaction(tx_sudo):
        tx_sudo.env.cr.execute(SQL(
            'SELECT 1 FROM payment_transaction WHERE id = %s FOR NO KEY UPDATE', tx_sudo.id))
        tx_sudo.invalidate_recordset(['state'])

    @staticmethod
    def _verify_signature(body, received, tx_sudo):
        """``PE-Signature`` es el HMAC-SHA256 (hexadecimal) del cuerpo con la
        clave secreta. Se acepta también sobre el cuerpo sin espacios ni saltos
        de línea, como lo compacta PagoEfectivo al firmar.

        :raise Forbidden: si falta la firma o no coincide.
        """
        if not received:
            _logger.warning('Notificación de PagoEfectivo sin firma.')
            raise Forbidden()
        key = (tx_sudo.provider_id.pagoefectivo_secret_key or '').encode()
        compact = body.replace(b' ', b'').replace(b'\r', b'').replace(b'\n', b'').replace(b'\t', b'')
        received = received.strip().lower()
        for candidate in (body, compact):
            expected = hmac.new(key, candidate, hashlib.sha256).hexdigest()
            if hmac.compare_digest(received, expected):
                return
        _logger.warning('Notificación de PagoEfectivo con firma no válida.')
        raise Forbidden()
