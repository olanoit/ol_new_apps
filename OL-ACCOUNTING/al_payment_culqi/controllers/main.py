# -*- coding: utf-8 -*-
from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import SQL

from odoo.addons.al_payment_culqi import const
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)


class CulqiController(http.Controller):

    @http.route('/payment/culqi/charge', type='jsonrpc', auth='public')
    def culqi_charge(self, reference, partner_id, access_token, source_id,
                     device_id=None, authentication_3ds=None):
        """Crea el cargo con el token del checkout (o repite el cargo con los
        parámetros 3DS) y procesa la transacción.

        :param str reference: referencia de la transacción de Odoo.
        :param int partner_id: cliente de la transacción.
        :param str access_token: firma de ``reference`` y ``partner_id``
            generada al preparar el pago (impide alterar la transacción).
        :param str source_id: token de Culqi (``tkn_…`` o ``ype_…``).
        :param str device_id: huella del dispositivo de Culqi3DS (antifraude).
        :param dict authentication_3ds: parámetros devueltos por Culqi3DS.
        :return: ``{'state': …, 'message': …}`` o ``{'action': 'review'}``
            cuando Culqi pide autenticación 3DS.
        """
        if not payment_utils.check_access_token(access_token, reference, partner_id):
            raise ValidationError(_('Los datos del pago fueron alterados.'))

        # Las transacciones son de clientes públicos (tienda, enlaces de pago):
        # se accede con sudo tras validar la firma de la referencia.
        tx_sudo = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', 'culqi')])
        if not tx_sudo:
            raise ValidationError(_('No se encontró la transacción.'))
        # Bloquea la fila: un token de Culqi es de un solo uso y una segunda
        # petición simultánea no debe volver a cobrar.
        tx_sudo.env.cr.execute(SQL(
            'SELECT 1 FROM payment_transaction WHERE id = %s FOR NO KEY UPDATE', tx_sudo.id))
        tx_sudo.invalidate_recordset(['state'])
        if tx_sudo.state not in ('draft', 'pending'):
            raise ValidationError(_('La transacción ya fue procesada.'))

        payment_data = tx_sudo._culqi_create_charge(source_id, device_id, authentication_3ds)
        if payment_data.get('action_code') == const.ACTION_CODE_REVIEW:
            _logger.info('Culqi pide autenticación 3DS para %s.', reference)
            return {'action': 'review', 'message': payment_data.get('user_message')}

        tx_sudo._process('culqi', payment_data)
        return {'state': tx_sudo.state, 'message': tx_sudo.state_message or ''}
