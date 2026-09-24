# -*- coding: utf-8 -*-
"""El cajero puede guardar su preferencia desde Mis preferencias.

Un usuario interno solo lee y escribe en su propio registro los campos que
``res.users`` declara como propios (``SELF_READABLE_FIELDS`` /
``SELF_WRITEABLE_FIELDS``); con los demás se aplican los permisos normales
de ``res.users``, que un cajero no tiene. Sin declarar el campo, guardar
las preferencias fallaba con «No tienes permiso para modificar registros
Usuario».
"""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

FIELD = 'pos_product_view_mode'


@tagged('post_install', '-at_install')
class TestUserPreference(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cashier = cls.env['res.users'].create({
            'name': 'Cajero preferencias',
            'login': 'al_pos_product_view_cajero',
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('point_of_sale.group_pos_user').id])],
        })

    def _own_record(self):
        return self.env['res.users'].with_user(self.cashier).browse(self.cashier.id)

    def test_field_is_declared_as_own(self):
        own = self._own_record()
        self.assertIn(FIELD, own.SELF_READABLE_FIELDS)
        self.assertIn(FIELD, own.SELF_WRITEABLE_FIELDS)

    def test_cashier_saves_the_preference(self):
        own = self._own_record()
        own.write({FIELD: 'list'})
        self.assertEqual(self.cashier[FIELD], 'list')
        self.assertEqual(own.read([FIELD])[0][FIELD], 'list')

    def test_cashier_cannot_touch_another_user(self):
        other = self.env['res.users'].create({
            'name': 'Otro usuario', 'login': 'al_pos_product_view_otro',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            other.with_user(self.cashier).write({FIELD: 'grid'})
