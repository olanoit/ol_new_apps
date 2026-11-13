# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests import tagged

from .common import AlUserRoleCommon


@tagged('post_install', '-at_install')
class TestAlUserRoleHistory(AlUserRoleCommon):
    """Cada alta, cambio y baja de un rol queda en el historial."""

    def _history(self):
        return self.env['al.user.role.history'].search(
            [('user_id', '=', self.user.id)], order='id',
        )

    def test_add_edit_unlink(self):
        line = self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        line.write({'role_id': self.role_contacts.id, 'date_to': date(2099, 12, 31)})
        line.write({'date_to': date(2099, 12, 31)})  # sin cambios: no registra
        line.unlink()
        add, edit, unlink = self._history()
        self.assertEqual(add.action, 'add')
        self.assertEqual(add.new_role_id, self.role_internal)
        self.assertEqual(edit.action, 'edit')
        self.assertEqual(edit.old_role_id, self.role_internal)
        self.assertEqual(edit.new_role_id, self.role_contacts)
        self.assertEqual(edit.new_date_to, date(2099, 12, 31))
        self.assertEqual(unlink.action, 'unlink')
        self.assertEqual(unlink.old_role_name, 'Rol contactos')
        self.assertTrue(self.user.al_role_last_change)

    def test_history_survives_role_deletion(self):
        self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})
        self.role_contacts.unlink()
        history = self._history()
        self.assertEqual(history.mapped('action'), ['add', 'unlink'])
        self.assertEqual(history[-1].old_role_name, 'Rol contactos')
        self.assertFalse(history[-1].old_role_id)

    def test_user_action(self):
        action = self.user.action_al_role_history()
        self.assertEqual(action['domain'], [('user_id', '=', self.user.id)])
