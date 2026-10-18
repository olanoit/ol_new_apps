# -*- coding: utf-8 -*-
import uuid
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.models.payment_provider import PaymentProvider
from odoo.addons.payment.models.payment_transaction import PaymentTransaction
from odoo.addons.pos_online_payment.tests.test_frontend import TestUi


_compute_feature_support_fields = PaymentProvider._compute_feature_support_fields


def _support_partial_refund(provider):
    """La pasarela de prueba de Odoo no declara devoluciones."""
    _compute_feature_support_fields(provider)
    provider.support_refund = 'partial'


def _refund_done(tx):
    """La pasarela de prueba confirma la devolución en el acto."""
    tx._set_done()


@tagged('post_install', '-at_install')
class TestPosPaymentGateway(TestUi):
    """Hereda el entorno de las pruebas de pos_online_payment (sus pruebas
    también corren aquí: el pago en línea nativo sigue funcionando)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider_2 = cls.payment_provider.copy({'name': 'Segunda pasarela', 'state': 'test', 'is_published': True})
        cls.online_payment_method_2 = cls.env['pos.payment.method'].create({
            'name': 'Segunda pasarela',
            'is_online_payment': True,
            'online_payment_provider_ids': [Command.set(cls.provider_2.ids)],
        })
        cls.pos_config.payment_method_ids = [Command.link(cls.online_payment_method_2.id)]
        cls.startClassPatcher(patch.object(
            PaymentProvider, '_compute_feature_support_fields', _support_partial_refund))

    def _pay_online(self, order, provider):
        """Como _fake_online_payment de Odoo, con la pasarela que se indique."""
        payment_context = self._fake_open_pos_order_pay_page(order.id, order.access_token)
        route_values = {k: payment_context[k] for k in ('amount', 'access_token', 'landing_route')}
        route_values.update({
            'provider_id': provider.id,
            'payment_method_id': self.payment_method_id,
            'token_id': None,
            'flow': 'direct',
            'tokenization_requested': False,
        })
        with mute_logger('odoo.addons.payment.models.payment_transaction'):
            processing_values = self._fake_request_pos_order_pay_transaction_page(order.id, route_values)
        tx = self._get_tx(processing_values['reference'])
        tx._set_done()
        self._fake_open_pos_order_pay_confirmation_page(order.id, order.access_token, tx.id)
        return tx

    def test_one_method_per_provider(self):
        """La caja admite dos métodos en línea, pero no la misma pasarela en dos."""
        self.assertEqual(len(self.pos_config.payment_method_ids.filtered('is_online_payment')), 2)
        with self.assertRaises(ValidationError):
            self.online_payment_method_2.online_payment_provider_ids = [Command.link(self.payment_provider.id)]

    def test_method_takes_provider_logo(self):
        """El método creado desde la pasarela lleva su logo."""
        logo = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        provider = self.payment_provider.copy({'name': 'Pasarela con logo', 'state': 'test', 'image_128': logo})
        action = provider.action_al_pos_payment_method()
        method = self.env['pos.payment.method'].browse(action['res_id'])
        self.assertEqual(method.online_payment_provider_ids, provider)
        self.assertTrue(method.image)
        # Sin imagen, la toma de la pasarela al cambiarla.
        method.image = False
        method.online_payment_provider_ids = [Command.set(provider.ids)]
        self.assertTrue(method.image)
        # Con la caja abierta también se puede poner el logo (migración).
        self.pos_config.with_user(self.pos_user).open_ui()
        self.online_payment_method_2.image = False
        self.provider_2.image_128 = logo
        self.online_payment_method_2._al_set_provider_logo()
        self.assertTrue(self.online_payment_method_2.image)

    def test_payment_recorded_with_provider_method(self):
        """El cajero pide el QR con el segundo método: la página solo admite su
        pasarela y el pago queda con ese método."""
        order = self._open_session_fake_cashier_unpaid_order()
        order.with_user(self.pos_user).al_set_online_payment_method(self.online_payment_method_2.id)
        order.with_user(self.pos_user).get_and_set_online_payments_data(order.amount_total)
        self.assertEqual(order.online_payment_method_id, self.online_payment_method_2)

        with mute_logger('odoo.http'), self.assertRaises(Exception):
            self._pay_online(order, self.payment_provider)  # pasarela de otro método
        self._pay_online(order, self.provider_2)
        self.assertEqual(order.state, 'paid')
        self.assertEqual(order.payment_ids.payment_method_id, self.online_payment_method_2)

    def test_payment_method_follows_transaction_provider(self):
        """Aunque el cajero haya cambiado de método, el pago va al método de la
        pasarela que cobró."""
        order = self._open_session_fake_cashier_unpaid_order()
        self._pay_online(order, self.payment_provider)
        self.assertEqual(order.payment_ids.payment_method_id, self.online_payment_method)

    def test_refund_to_card(self):
        """Devolución total: la pasarela devuelve el importe, el pago del TPV
        enlaza el pago contable de la devolución y la caja cierra."""
        order = self._open_session_fake_cashier_unpaid_order()
        tx = self._pay_online(order, self.payment_provider)
        amount = order.amount_total
        with patch.object(PaymentTransaction, '_send_refund_request', _refund_done):
            result = self.env['pos.order'].with_user(self.pos_user).al_refund_online_payment(
                order.ids, self.online_payment_method.id, amount)
        self.assertIn('reference', result)
        refund_tx = tx.child_transaction_ids
        self.assertEqual(refund_tx.reference, result['reference'])
        self.assertTrue(refund_tx.payment_id, 'La devolución tiene su pago contable')

        session = self.pos_config.current_session_id
        line = order.lines
        refund_uid = '00055-001-0002'
        self.env['pos.order'].with_user(self.pos_user).sync_from_ui([{
            'uuid': refund_uid,
            'name': 'Order ' + refund_uid,
            'session_id': session.id,
            'user_id': self.pos_user.id,
            'partner_id': False,
            'is_refund': True,
            'access_token': str(uuid.uuid4()),
            'amount_paid': -amount,
            'amount_return': 0,
            'state': 'paid',
            'amount_tax': -order.amount_tax,
            'amount_total': -amount,
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'fiscal_position_id': False,
            'lines': [[0, 0, {
                'product_id': line.product_id.id,
                'qty': -1,
                'discount': 0,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'price_unit': line.price_unit,
                'price_subtotal': -line.price_subtotal,
                'price_subtotal_incl': -line.price_subtotal_incl,
                'refunded_orderline_id': line.id,
                'pack_lot_ids': [],
            }]],
            'payment_ids': [[0, 0, {
                'amount': -amount,
                'payment_date': fields.Datetime.to_string(fields.Datetime.now()),
                'payment_method_id': self.online_payment_method.id,
                'transaction_id': result['reference'],
            }]],
        }])
        refund_order = session.order_ids.filtered('is_refund')
        self.assertEqual(refund_order.state, 'paid')
        self.assertEqual(refund_order.payment_ids.online_account_payment_id, refund_tx.payment_id)

        session.post_closing_cash_details(0)
        self.assertTrue(session.close_session_from_ui()['successful'])

    def test_refund_more_than_paid(self):
        """No se devuelve más de lo cobrado con la pasarela."""
        order = self._open_session_fake_cashier_unpaid_order()
        self._pay_online(order, self.payment_provider)
        result = self.env['pos.order'].with_user(self.pos_user).al_refund_online_payment(
            order.ids, self.online_payment_method.id, order.amount_total + 1)
        self.assertIn('error', result)
        self.assertFalse(order.payment_ids.online_account_payment_id.payment_transaction_id.child_transaction_ids)

    def test_refund_requires_refund_transaction(self):
        """Sin una devolución confirmada, el TPV no puede registrar un pago
        negativo en línea."""
        order = self._open_session_fake_cashier_unpaid_order()
        self._pay_online(order, self.payment_provider)
        with self.assertRaises(Exception):
            self.env['pos.payment'].create({
                'pos_order_id': order.id,
                'amount': -1.0,
                'payment_method_id': self.online_payment_method.id,
                'transaction_id': 'NO-EXISTE',
            })

    def test_refund_tour(self):
        """En el TPV: devolver la venta cobrada en línea con su pasarela."""
        order = self._open_session_fake_cashier_unpaid_order()
        self._pay_online(order, self.payment_provider)
        with patch.object(PaymentTransaction, '_send_refund_request', _refund_done):
            self.start_pos_tour('al_pos_payment_gateway_refund', login='pos_op_user')
        refund_order = self.pos_config.current_session_id.order_ids.filtered('is_refund')
        self.assertEqual(refund_order.state, 'paid')
        self.assertTrue(refund_order.payment_ids.online_account_payment_id)
        self.assertAlmostEqual(refund_order.payment_ids.amount, -order.amount_total)

    def test_choose_method_tour(self):
        """En el TPV: al cobrar con la segunda pasarela, la orden queda con ese
        método antes de mostrar el QR (la página de pago ofrece solo esa)."""
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, None)
        self.start_pos_tour('al_pos_payment_gateway_choose_method', login='pos_op_user')
        order = self.pos_config.current_session_id.order_ids
        self.assertEqual(order.al_online_payment_method_id, self.online_payment_method_2)
        self.assertEqual(order.online_payment_method_id, self.online_payment_method_2)
