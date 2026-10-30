# -*- coding: utf-8 -*-
from odoo.addons.payment.tests.common import PaymentCommon


class PagoEfectivoCommon(PaymentCommon):
    """Datos de prueba con la forma de la API REST v1 de PagoEfectivo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Odoo 20: PaymentCommon reemplaza _process por un mock; aquí se prueba.
        cls.enable_process_patcher = False
        cls.secret_key = 'secreto-de-prueba-odoo'
        cls.provider = cls._prepare_provider('pagoefectivo', update_values={
            'is_published': True,
            'pagoefectivo_service_id': '1035',
            'pagoefectivo_access_key': 'clave-de-acceso-odoo',
            'pagoefectivo_secret_key': cls.secret_key,
        })
        cls.currency = cls._enable_currency('PEN')
        cls.amount = 120.50
        cls.reference = 'INV/2026/00001'
        cls.partner.write({
            'name': 'Rosa María Quispe Huamán', 'email': 'rosa@example.com',
            'phone': '987 654 321', 'street': 'Av. Arequipa 123', 'city': 'Lima',
            'vat': '20131312955', 'country_id': cls.env.ref('base.pe').id,
        })
        cls.payment_method_id = cls.env.ref('al_payment_pagoefectivo.payment_method_pagoefectivo').id
        cls.cip = 2834561
        cls.auth_data = {
            'token': 'eyJhbGciOiJIUzI1NiJ9.prueba',
            'codeService': '1035',
            'tokenStart': '2026-10-22T10:00:00-05:00',
            'tokenExpires': '2026-10-22T11:00:00-05:00',
        }
        cls.cip_data = {
            'cip': cls.cip,
            'currency': 'PEN',
            'amount': 120.5,
            'transactionCode': 'INV-2026-00001',
            'dateExpiry': '2026-10-24T10:00:00-05:00',
            'cipUrl': 'https://pre1a.payment.pagoefectivo.pe/PE/Checkout/Cip?token=abc123&lang=es',
        }

    def _notification(self, event='cip.paid', amount=120.5, currency='PEN', cip=None):
        return {
            'eventType': event,
            'operationNumber': 9123,
            'data': {
                'cip': cip or self.cip,
                'currency': currency,
                'amount': amount,
                'paymentDate': '2026-10-23T15:20:11-05:00',
                'transactionCode': 'INV-2026-00001',
            },
        }
