# -*- coding: utf-8 -*-
from datetime import date

from odoo import Command
from odoo.tests import tagged

from .common import AlUserRoleCommon


@tagged('post_install', '-at_install')
class TestAlUserRoleWizards(AlUserRoleCommon):

    def test_role_from_user(self):
        self.user.group_ids = [Command.link(self.group_partner_manager.id)]
        wizard = self.env['al.user.role.from.user.wizard'].with_context(
            active_model='res.users', active_id=self.user.id,
        ).create({'name': 'Rol desde usuario'})
        action = wizard.action_create_role()
        role = self.Role.browse(action['res_id'])
        self.assertIn(self.group_partner_manager, role.implied_ids)
        self.assertEqual(self.user.al_role_ids, role)
        self.assertTrue(self.user.has_group('base.group_partner_manager'))

    def test_role_from_groups(self):
        groups = self.group_user | self.group_partner_manager
        wizard = self.env['al.user.role.from.groups.wizard'].with_context(
            active_model='res.groups', active_ids=groups.ids,
        ).create({'name': 'Rol desde grupos'})
        role = self.Role.browse(wizard.action_create_role()['res_id'])
        self.assertEqual(role.implied_ids, groups)

    def test_add_users(self):
        other = self.env['res.users'].create({'name': 'Otro', 'login': 'al_otro'})
        self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})
        wizard = self.env['al.user.role.add.users.wizard'].create({
            'role_id': self.role_contacts.id,
            'user_ids': [Command.set((self.user | other).ids)],
            'date_to': date(2099, 12, 31),
        })
        wizard.action_add_users()
        self.assertEqual(len(self.role_contacts.line_ids), 2)
        self.assertEqual(self.role_contacts.role_user_ids, self.user | other)
        self.assertTrue(other.has_group('base.group_partner_manager'))
