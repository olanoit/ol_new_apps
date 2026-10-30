# -*- coding: utf-8 -*-
import re

from odoo import _, api, models
from odoo.exceptions import ValidationError

from odoo.addons.al_payment_izipay import const
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # -------------------------------------------------------------------------
    # Valores para el navegador
    # -------------------------------------------------------------------------

    def _get_specific_processing_values(self, processing_values):
        """Crea el formToken con el importe de la transacción: el navegador
        solo recibe el formToken y la clave pública, nunca la contraseña."""
        if self.provider_code != 'izipay':
            return super()._get_specific_processing_values(processing_values)
        answer = self.provider_id._send_api_request(
            'POST', 'Charge/CreatePayment', json=self._izipay_prepare_payment_payload(),
            reference=self.reference)
        return {
            # Firma la referencia y el cliente: /payment/izipay/return la exige.
            'access_token': payment_utils.generate_access_token(
                processing_values['reference'], processing_values['partner_id'], env=self.env),
            'izipay_form_token': answer['formToken'],
            'izipay_public_key': self.provider_id.izipay_public_key,
            'izipay_static_url': const.STATIC_URL,
        }

    def _izipay_order_id(self):
        """``orderId`` de Izipay: la referencia sin los caracteres que no
        admite (las de facturas llevan «/»). La referencia exacta va en
        ``metadata``."""
        self.ensure_one()
        return re.sub(r'[^A-Za-z0-9_-]', '-', self.reference)[:const.ORDER_ID_MAX_LENGTH]

    def _izipay_prepare_payment_payload(self):
        self.ensure_one()
        first_name, last_name = payment_utils.split_partner_name(self.partner_name or '')
        billing = {
            'firstName': first_name or self.partner_name or '',
            'lastName': last_name,
            'identityCode': self.partner_id.vat or '',
            'phoneNumber': self.partner_phone or '',
            'address': (self.partner_address or '').replace('<', '').replace('>', ''),
            'city': self.partner_city or '',
            'state': self.partner_state_id.name or '',
            'zipCode': self.partner_zip or '',
            'country': self.partner_country_id.code or '',
        }
        customer = {
            'reference': str(self.partner_id.id),
            'billingDetails': {key: value for key, value in billing.items() if value},
        }
        # Sin correo, el formulario de Izipay lo pide al cliente.
        if self.partner_email:
            customer['email'] = self.partner_email
        return {
            'amount': payment_utils.to_minor_currency_units(self.amount, self.currency_id),
            'currency': self.currency_id.name,
            'orderId': self._izipay_order_id(),
            'formAction': 'PAYMENT',
            'contrib': 'Odoo 19 al_payment_izipay',
            'ipnTargetUrl': self.provider_id._izipay_get_webhook_url(),
            'customer': customer,
            'metadata': {'odoo_reference': self.reference},
        }

    # -------------------------------------------------------------------------
    # Consulta del pedido
    # -------------------------------------------------------------------------

    def _izipay_fetch_payment_data(self):
        """Consulta el pedido a Izipay con la contraseña (Order/Get) y lo
        devuelve en el formato de ``_process``. Si Izipay aún no registra
        ninguna transacción, devuelve ``None``."""
        self.ensure_one()
        try:
            answer = self.provider_id._send_api_request(
                'POST', 'Order/Get', json={'orderId': self._izipay_order_id()},
                reference=self.reference)
        except ValidationError as error:
            _logger.info('Izipay no devolvió el pedido de %s: %s', self.reference, error)
            return None
        transactions = [
            transaction for transaction in answer.get('transactions') or []
            if (transaction.get('metadata') or {}).get('odoo_reference') in (None, self.reference)
        ]
        transaction = self._izipay_pick_transaction(transactions)
        if not transaction:
            return None
        # El formulario solo devuelve el control al terminar: el pedido está
        # cerrado, pagado o con los intentos agotados.
        return {
            'reference': self.reference,
            'order_status': transaction['status'],
            'order_cycle': 'CLOSED',
            'transaction': transaction,
        }

    @api.model
    def _izipay_pick_transaction(self, transactions):
        """La transacción que decide el estado del pedido: la pagada, si no la
        que está en curso, y si no la última (los intentos rechazados quedan
        en el mismo pedido)."""
        if not transactions:
            return None
        for status in (const.STATUS_PAID, const.STATUS_RUNNING):
            for transaction in transactions:
                if transaction.get('status') == status and transaction.get('operationType', 'DEBIT') == 'DEBIT':
                    return transaction
        return max(transactions, key=lambda transaction: transaction.get('creationDate') or '')

    @api.model
    def _izipay_payment_data_from_answer(self, answer):
        """Convierte un ``V4/Payment`` (la ``kr-answer`` de la IPN) al formato
        de ``_process``."""
        transaction = self._izipay_pick_transaction(answer.get('transactions') or [])
        metadata = (transaction or {}).get('metadata') or {}
        return {
            'reference': metadata.get('odoo_reference'),
            'order_id': (answer.get('orderDetails') or {}).get('orderId'),
            'order_status': answer.get('orderStatus'),
            'order_cycle': answer.get('orderCycle'),
            'transaction': transaction or {},
        }

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        if provider_code != 'izipay':
            return super()._extract_reference(provider_code, payment_data)
        return payment_data.get('reference')

    # -------------------------------------------------------------------------
    # Devolución
    # -------------------------------------------------------------------------

    def _send_refund_request(self):
        """Devuelve según el estado de la transacción en Izipay:

        - Sin capturar (el lote se cierra por la noche): si se devuelve todo
          lo que queda, se anula (CANCELLATION_ONLY); si es una parte, se
          reduce el importe por capturar (Transaction/Update).
        - Capturada: se reembolsa (REFUND_ONLY).

        ``resolutionMode: AUTO`` no sirve para una parte: antes de la captura
        anula la transacción completa (comprobado en la tienda de prueba).
        """
        if self.provider_code != 'izipay':
            return super()._send_refund_request()
        source = self.source_transaction_id
        provider = self.provider_id
        uuid = source.provider_reference
        amount = payment_utils.to_minor_currency_units(-self.amount, self.currency_id)
        currency = self.currency_id.name

        current = provider._send_api_request(
            'POST', 'Transaction/Get', json={'uuid': uuid}, reference=self.reference)
        detailed_status = current.get('detailedStatus')
        if detailed_status in const.NOT_CAPTURED_STATUSES:
            remaining = int(current['amount']) - amount
            if remaining < 0:
                raise ValidationError(_('El importe a devolver supera el importe pendiente en Izipay.'))
            if remaining == 0:
                response = provider._send_api_request(
                    'POST', 'Transaction/CancelOrRefund', reference=self.reference, json={
                        'uuid': uuid, 'amount': amount, 'currency': currency,
                        'resolutionMode': 'CANCELLATION_ONLY',
                        'comment': self.reference,
                    })
                operation = 'cancel'
            else:
                response = provider._send_api_request(
                    'POST', 'Transaction/Update', reference=self.reference, json={
                        'uuid': uuid,
                        'cardUpdate': {'amount': remaining, 'currency': currency},
                        'comment': self.reference,
                    })
                operation = 'update'
        elif detailed_status == const.CAPTURED_STATUS:
            response = provider._send_api_request(
                'POST', 'Transaction/CancelOrRefund', reference=self.reference, json={
                    'uuid': uuid, 'amount': amount, 'currency': currency,
                    'resolutionMode': 'REFUND_ONLY',
                    'comment': self.reference,
                })
            operation = 'refund'
        else:
            raise ValidationError(_(
                'Izipay no permite devolver una transacción en estado %s.', detailed_status))

        self.with_context(payment_safe_write=True)._process({
            'reference': self.reference,
            'refund_operation': operation,
            'refund_amount': amount,
            'transaction': response,
        })

    # -------------------------------------------------------------------------
    # Procesamiento
    # -------------------------------------------------------------------------

    def _extract_amount_data(self, payment_data):
        if self.provider_code != 'izipay':
            return super()._extract_amount_data(payment_data)
        transaction = payment_data.get('transaction') or {}
        if payment_data.get('refund_operation'):
            # La anulación y la reducción responden con la transacción
            # original: el importe devuelto es el que se pidió.
            return {
                'amount': payment_utils.to_major_currency_units(
                    payment_data['refund_amount'], self.currency_id),
                'currency_code': transaction.get('currency') or self.currency_id.name,
            }
        # Una transacción ya confirmada puede recibir avisos posteriores (IPN
        # de una anulación o con el importe reducido): no se vuelve a validar.
        # En 20 el importe se valida después de _apply_updates, cuando la
        # transacción ya quedó «done»: por eso se marca en payment_data.
        if payment_data.get('izipay_already_done') or transaction.get('status') not in (const.STATUS_PAID, const.STATUS_RUNNING):
            return None
        return {
            'amount': payment_utils.to_major_currency_units(int(transaction['amount']), self.currency_id),
            'currency_code': transaction.get('currency'),
        }

    def _apply_updates(self, payment_data):
        if self.provider_code != 'izipay':
            return super()._apply_updates(payment_data)

        transaction = payment_data.get('transaction') or {}
        if payment_data.get('refund_operation'):
            self._izipay_apply_refund(payment_data['refund_operation'], transaction)
            return
        if self.state == 'done':
            # Avisos posteriores (anulación, devolución): la devolución tiene
            # su propia transacción; tampoco se revalida el importe.
            payment_data['izipay_already_done'] = True
            return

        if transaction.get('uuid'):
            self.provider_reference = transaction['uuid']
        brand = ((transaction.get('transactionDetails') or {}).get('cardDetails') or {}).get('effectiveBrand')
        if brand and self.payment_method_id.code == 'card':
            payment_method = self.provider_id._get_pm_from_code(
                brand, mapping=const.PAYMENT_METHODS_MAPPING)
            self.payment_method_id = payment_method or self.payment_method_id

        status = transaction.get('status') or payment_data.get('order_status')
        if status == const.STATUS_PAID:
            self._set_done()
        elif status == const.STATUS_RUNNING:
            self._set_pending()
        elif status == const.STATUS_ABANDONED:
            self._set_canceled(_('El cliente abandonó el pago en Izipay.'))
        elif status == const.STATUS_UNPAID:
            if payment_data.get('order_cycle') == 'OPEN':
                # Intento rechazado: el formulario deja reintentar al cliente.
                _logger.info('Intento rechazado en Izipay para %s; el pedido sigue abierto.', self.reference)
                return
            self._set_error(self._izipay_transaction_message(transaction) or _('Izipay rechazó el pago.'))
        else:
            _logger.warning('Respuesta de Izipay no reconocida para %s: %s', self.reference, payment_data)
            self._set_error(_('Respuesta de Izipay no reconocida.'))

    def _izipay_apply_refund(self, operation, transaction):
        if operation == 'refund':
            # El reembolso es una transacción nueva (operationType CREDIT).
            self.provider_reference = transaction.get('uuid')
        else:
            self.provider_reference = f"{transaction.get('uuid')}-{operation}"
        if operation == 'cancel' and transaction.get('detailedStatus') != 'CANCELLED':
            self._set_error(_('Izipay no confirmó la anulación.'))
        elif transaction.get('status') == const.STATUS_RUNNING:
            self._set_pending()
        else:
            self._set_done()

    @api.model
    def _izipay_transaction_message(self, transaction):
        parts = [transaction.get('errorMessage'), transaction.get('detailedErrorMessage')]
        return ' — '.join(part for part in parts if part)
