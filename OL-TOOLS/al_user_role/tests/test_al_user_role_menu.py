# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from .common import AlUserRoleCommon


@tagged('post_install', '-at_install')
class TestAlUserRoleMenu(AlUserRoleCommon):
    """Menús ocultos por rol: se ocultan solo si todos los roles del usuario
    los ocultan, con sus submenús; el Administrador del sistema ve todos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Menu = cls.env['ir.ui.menu']
        action = cls.env['ir.actions.act_window'].create({
            'name': 'Contactos', 'res_model': 'res.partner',
        })
        cls.menu_root = Menu.create({'name': 'Raíz'})
        cls.menu_parent = Menu.create({'name': 'Padre', 'parent_id': cls.menu_root.id})
        cls.menu_child = Menu.create({
            'name': 'Hijo', 'parent_id': cls.menu_parent.id,
            'action': f'ir.actions.act_window,{action.id}',
        })
        cls.menu_other = Menu.create({
            'name': 'Otro', 'parent_id': cls.menu_root.id,
            'action': f'ir.actions.act_window,{action.id}',
        })
        cls.menus = cls.menu_root | cls.menu_parent | cls.menu_child | cls.menu_other

    def _visible(self, user=None):
        return self.menus.with_user(user or self.user)._filter_visible_menus()

    def test_without_roles_nothing_hidden(self):
        self.role_internal.hidden_menu_ids = [Command.set(self.menu_child.ids)]
        self.assertEqual(self._visible(), self.menus)

    def test_role_hides_menu(self):
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.assertIn(self.menu_child, self._visible())
        # Cambiar los menús del rol limpia la caché de menús visibles.
        self.role_internal.hidden_menu_ids = [Command.set(self.menu_child.ids)]
        visible = self._visible()
        self.assertNotIn(self.menu_child, visible)
        self.assertIn(self.menu_other, visible)

    def test_hidden_parent_hides_children(self):
        self.role_internal.hidden_menu_ids = [Command.set(self.menu_parent.ids)]
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        visible = self._visible()
        self.assertNotIn(self.menu_parent, visible)
        self.assertNotIn(self.menu_child, visible)

    def test_hidden_only_if_all_roles_hide(self):
        self.role_internal.hidden_menu_ids = [Command.set(self.menu_parent.ids)]
        for role in (self.role_internal, self.role_contacts):
            self.Line.create({'role_id': role.id, 'user_id': self.user.id})
        self.assertIn(self.menu_child, self._visible())
        # El otro rol oculta solo el hijo: queda oculto el hijo, no el padre.
        self.role_contacts.hidden_menu_ids = [Command.set(self.menu_child.ids)]
        visible = self._visible()
        self.assertNotIn(self.menu_child, visible)
        self.assertIn(self.menu_parent, visible)

    def test_role_not_enabled_does_not_count(self):
        # El rol vigente oculta el hijo; el rol futuro no oculta nada. Si el
        # futuro contara, la intersección dejaría el hijo visible.
        self.role_internal.hidden_menu_ids = [Command.set(self.menu_child.ids)]
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.Line.create({
            'role_id': self.role_contacts.id, 'user_id': self.user.id,
            'date_from': fields.Date.today() + timedelta(days=1),
        })
        self.assertNotIn(self.menu_child, self._visible())

    def test_admin_sees_everything(self):
        role_admin = self.Role.create({
            'name': 'Rol admin',
            'implied_ids': [Command.set(self.env.ref('base.group_system').ids)],
            'hidden_menu_ids': [Command.set(self.menu_child.ids)],
        })
        self.Line.create({'role_id': role_admin.id, 'user_id': self.user.id})
        self.assertIn(self.menu_child, self._visible())

    def test_hide_from_menu_side(self):
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.assertIn(self.menu_child, self._visible())
        self.menu_child.al_hiding_role_ids = [Command.link(self.role_internal.id)]
        self.assertNotIn(self.menu_child, self._visible())
