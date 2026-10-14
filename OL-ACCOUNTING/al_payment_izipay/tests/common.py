# -*- coding: utf-8 -*-
from odoo.addons.payment.tests.common import PaymentCommon


class IzipayCommon(PaymentCommon):
    """Datos de prueba con la forma exacta de la API REST V4 de Izipay,
    tomados de respuestas reales de su tienda de prueba (reducidas)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls._prepare_provider('izipay', update_values={
            'izipay_shop_id': '89289758',
            'izipay_password': 'testpassword_odoo0000000000',
            'izipay_public_key': '89289758:testpublickey_odoo0000000000',
        })
        cls.currency = cls._enable_currency('PEN')
        cls.amount = 120.50
        cls.reference = 'INV/2026/00001'
        cls.partner.write({
            'name': 'Rosa María Quispe Huamán', 'email': 'rosa@example.com',
            'phone': '987654321', 'street': 'Av. Arequipa 123', 'city': 'Lima',
            'vat': '20131312955', 'country_id': cls.env.ref('base.pe').id,
        })
        cls.payment_method_id = cls.env.ref('payment.payment_method_card').id
        cls.form_token_answer = {'formToken': '26XrYMTBDzS9yZR4K3afl8Uw26AeyJhbW91bnQiOjEyMDUw', '_type': 'V4/Charge/PaymentForm'}
        cls.uuid = '34030cb72c1c4e43b98644b3a758411c'
        cls.paid_transaction = cls._izipay_transaction(cls.uuid, 'PAID', 'AUTHORISED')
        cls.refused_transaction = dict(
            cls._izipay_transaction('3ecf55b12d8b498bb668ad2667571df2', 'UNPAID', 'REFUSED'),
            errorCode='ACQ_001', errorMessage='payment refused', detailedErrorCode='51',
            detailedErrorMessage='No funds available', creationDate='2026-10-13T23:45:09+00:00')

    @classmethod
    def _izipay_transaction(cls, uuid, status, detailed_status, amount=12050, **values):
        return {
            'shopId': '89289758', 'uuid': uuid, 'amount': amount, 'currency': 'PEN',
            'paymentMethodType': 'CARD', 'status': status, 'detailedStatus': detailed_status,
            'operationType': 'DEBIT', 'creationDate': '2026-10-13T23:43:58+00:00',
            'errorCode': None, 'errorMessage': None, 'detailedErrorCode': None, 'detailedErrorMessage': None,
            'metadata': {'odoo_reference': cls.reference},
            'transactionDetails': {'cardDetails': {'effectiveBrand': 'VISA', 'pan': '497010XXXXXX0055'}},
            '_type': 'V4/PaymentTransaction',
            **values,
        }

    def _izipay_payment_answer(self, transactions, order_status, order_cycle='CLOSED'):
        """``kr-answer`` (V4/Payment) como lo envían la IPN y el formulario."""
        return {
            'shopId': '89289758', 'orderCycle': order_cycle, 'orderStatus': order_status,
            'serverDate': '2026-10-13T23:44:00+00:00',
            'orderDetails': {'orderTotalAmount': 12050, 'orderCurrency': 'PEN', 'mode': 'TEST',
                             'orderId': 'INV-2026-00001', 'metadata': None, '_type': 'V4/OrderDetails'},
            'transactions': transactions,
            '_type': 'V4/Payment',
        }

    def _izipay_order_get(self, transactions):
        """Respuesta de Order/Get (V4/OrderTransactions)."""
        return {'orderId': 'INV-2026-00001', 'shopId': '89289758', 'transactions': transactions,
                '_type': 'V4/OrderTransactions'}
