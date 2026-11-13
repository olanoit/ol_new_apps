# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from .common import AlUserRoleCommon


@tagged('post_install', '-at_install')
class TestAlUserRoleAdditive(AlUserRoleCommon):
    """Roles sin *Reemplazar permisos del usuario*: agregan grupos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_export = cls.env.ref('base.group_allow_export')
        # Configuración propia del usuario: interno + exportar.
        cls.user.group_ids = [Command.set((cls.group_user | cls.group_export).ids)]
        cls.role_add_contacts = cls.Role.create({
            'name': 'Rol aditivo contactos',
            'implied_ids': [Command.set(cls.group_partner_manager.ids)],
        })

    def test_default_is_additive(self):
        self.assertFalse(self.Role.create({'name': 'Rol nuevo'}).exclusive_permissions)

    def test_additive_role_keeps_own_groups(self):
        self.Line.create({'role_id': self.role_add_contacts.id, 'user_id': self.user.id})
        self.assertIn(self.group_export, self.user.group_ids)
        self.assertIn(self.group_partner_manager, self.user.group_ids)
        # all_implied_ids es reflexivo: incluye el grupo del propio rol.
        self.assertEqual(
            self.user.al_role_granted_group_ids,
            self.group_partner_manager | self.role_add_contacts.group_id,
        )
        self.assertTrue(self.user.al_show_role_info)
        self.assertFalse(self.user.al_show_role_alert)

    def test_remove_additive_role_restores_own_groups(self):
        line = self.Line.create({'role_id': self.role_add_contacts.id, 'user_id': self.user.id})
        line.unlink()
        self.assertIn(self.group_export, self.user.group_ids)
        self.assertNotIn(self.group_partner_manager, self.user.group_ids)
        self.assertFalse(self.user.al_role_granted_group_ids)

    def test_own_group_also_given_by_role_is_kept(self):
        # El rol da un grupo que el usuario ya tenía: sigue siendo propio.
        self.user.group_ids = [Command.link(self.group_partner_manager.id)]
        line = self.Line.create({'role_id': self.role_add_contacts.id, 'user_id': self.user.id})
        self.assertEqual(self.user.al_role_granted_group_ids, self.role_add_contacts.group_id)
        line.unlink()
        self.assertIn(self.group_partner_manager, self.user.group_ids)

    def test_manual_changes_to_own_groups_are_kept(self):
        self.Line.create({'role_id': self.role_add_contacts.id, 'user_id': self.user.id})
        self.user.group_ids = [Command.unlink(self.group_export.id)]
        self.assertNotIn(self.group_export, self.user.group_ids)
        self.assertIn(self.group_partner_manager, self.user.group_ids)

    def test_manual_removal_of_role_group_is_restored(self):
        self.Line.create({'role_id': self.role_add_contacts.id, 'user_id': self.user.id})
        self.user.group_ids = [Command.unlink(self.group_partner_manager.id)]
        self.assertIn(self.group_partner_manager, self.user.group_ids)

    def test_expired_additive_role_keeps_own_access(self):
        yesterday = fields.Date.today() - timedelta(days=1)
        line = self.Line.create({'role_id': self.role_add_contacts.id, 'user_id': self.user.id})
        line.write({'date_from': yesterday - timedelta(days=5), 'date_to': yesterday})
        self.assertIn(self.group_user, self.user.group_ids)
        self.assertIn(self.group_export, self.user.group_ids)
        self.assertNotIn(self.group_partner_manager, self.user.group_ids)

    def test_exclusive_role_wins_over_additive(self):
        self.Line.create({'role_id': self.role_add_contacts.id, 'user_id': self.user.id})
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.assertNotIn(self.group_export, self.user.group_ids)
        self.assertIn(self.group_partner_manager, self.user.group_ids)
        self.assertTrue(self.user.al_show_role_alert)
        self.assertFalse(self.user.al_show_role_info)

    def test_toggle_role_to_exclusive_updates_users(self):
        self.Line.create({'role_id': self.role_add_contacts.id, 'user_id': self.user.id})
        self.role_add_contacts.exclusive_permissions = True
        self.assertNotIn(self.group_export, self.user.group_ids)
        self.assertNotIn(self.group_user, self.user.group_ids)
        self.assertIn(self.group_partner_manager, self.user.group_ids)
