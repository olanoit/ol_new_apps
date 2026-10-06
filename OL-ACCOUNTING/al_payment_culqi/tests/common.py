# -*- coding: utf-8 -*-
from odoo.addons.payment.tests.common import PaymentCommon


class CulqiCommon(PaymentCommon):
    """Datos de prueba con la forma exacta de la API v2 de Culqi
    (ejemplos de https://apidocs.culqi.com/apiculqi.yaml)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls._prepare_provider('culqi', update_values={
            'culqi_public_key': 'pk_test_odoo00000000000',
            'culqi_secret_key': 'sk_test_odoo00000000000',
        })
        cls.currency = cls._enable_currency('PEN')
        cls.amount = 120.50
        cls.partner.write({
            'name': 'Rosa María Quispe Huamán', 'email': 'rosa@example.com',
            'phone': '987654321', 'street': 'Av. Arequipa 123', 'city': 'Lima',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.payment_method_id = cls.env.ref('payment.payment_method_card').id
        cls.token = 'tkn_test_RvtfMbLatXRJrJQo'
        cls.charge_data = {
            'object': 'charge',
            'id': 'chr_test_kEazTaQBDtzNdwFr',
            'amount': 12050,
            'currency_code': 'PEN',
            'email': 'rosa@example.com',
            'capture': True,
            'reference_code': '1jKsutQy4s',
            'outcome': {
                'type': 'venta_exitosa', 'code': 'AUT0000',
                'merchant_message': 'La operación de venta ha sido autorizada exitosamente',
                'user_message': 'Su compra ha sido exitosa.',
            },
            'source': {'object': 'token', 'id': cls.token, 'type': 'card', 'last_four': '1111'},
        }
        cls.review_data = {'user_message': 'El usuario necesita autenticarse', 'action_code': 'REVIEW'}
        cls.refund_data = {
            'object': 'refund', 'id': 'ref_test_TTfLAgaA8nz8PWbO', 'charge_id': 'chr_test_kEazTaQBDtzNdwFr',
            'amount': 3000, 'reason': 'solicitud_comprador', 'status': 'completa',
        }
