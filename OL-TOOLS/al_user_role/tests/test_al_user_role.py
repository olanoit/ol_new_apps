# -*- coding: utf-8 -*-
from datetime import timedelta

from lxml import etree
from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import SQL, mute_logger

from .common import AlUserRoleCommon


@tagged('post_install', '-at_install')
class TestAlUserRole(AlUserRoleCommon):
    """Los grupos del usuario se calculan desde sus roles habilitados."""

    def test_role_is_a_group(self):
        self.assertTrue(self.role_contacts.group_id)
        self.assertEqual(self.role_contacts.group_id.name, 'Rol contactos')
        self.assertIn(self.group_partner_manager, self.role_contacts.effective_group_ids)

    def test_assign_role_gives_groups(self):
        self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})
        self.assertTrue(self.user.has_group('base.group_partner_manager'))
        self.assertIn(self.role_contacts.group_id, self.user.group_ids)
        self.assertEqual(self.user.al_role_ids, self.role_contacts)
        self.assertEqual(self.role_contacts.role_user_ids, self.user)

    def test_groups_outside_roles_are_removed(self):
        # group_partner_manager no lo da el rol interno (group_no_one sí:
        # en Odoo 19 lo implica group_user).
        self.user.group_ids = [Command.link(self.group_partner_manager.id)]
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.assertNotIn(self.group_partner_manager, self.user.group_ids)
        # Un cambio manual de grupos se revierte a lo que dicen los roles.
        self.user.write({'group_ids': [Command.link(self.group_partner_manager.id)]})
        self.assertNotIn(self.group_partner_manager, self.user.group_ids)

    def test_no_enabled_role_removes_all_groups(self):
        # Rol exclusivo vencido = sin acceso (mismo criterio que OCA).
        line = self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        yesterday = fields.Date.today() - timedelta(days=1)
        line.write({'date_from': yesterday - timedelta(days=5), 'date_to': yesterday})
        self.assertFalse(self.user.group_ids)

    def test_future_exclusive_role_keeps_own_groups_until_start(self):
        # Un rol exclusivo que aún no empieza no reemplaza nada todavía.
        self.Line.create({
            'role_id': self.role_internal.id, 'user_id': self.user.id,
            'date_from': fields.Date.today() + timedelta(days=1),
        })
        self.assertEqual(self.user.group_ids, self.group_user)

    def test_remove_last_role_removes_groups(self):
        line = self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})
        line.unlink()
        self.assertFalse(self.user.has_group('base.group_partner_manager'))

    def test_role_change_propagates(self):
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.assertFalse(self.user.has_group('base.group_partner_manager'))
        self.role_internal.implied_ids = [Command.link(self.group_partner_manager.id)]
        self.assertTrue(self.user.has_group('base.group_partner_manager'))

    def test_validity_dates(self):
        today = fields.Date.today()
        line = self.Line.create({
            'role_id': self.role_contacts.id, 'user_id': self.user.id,
            'date_from': today + timedelta(days=1),
        })
        self.assertFalse(line.is_enabled)
        self.assertFalse(self.user.has_group('base.group_partner_manager'))
        line.date_from = today - timedelta(days=10)
        self.assertTrue(line.is_enabled)
        self.assertTrue(self.user.has_group('base.group_partner_manager'))
        line.date_to = today - timedelta(days=1)
        self.assertFalse(self.user.has_group('base.group_partner_manager'))

    def test_dates_order(self):
        today = fields.Date.today()
        with self.assertRaises(ValidationError):
            self.Line.create({
                'role_id': self.role_contacts.id, 'user_id': self.user.id,
                'date_from': today, 'date_to': today - timedelta(days=1),
            })

    def test_cron_applies_validity(self):
        line = self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})
        # "Hoy" en la zona del cron (compañía o Lima), no en UTC: entre las
        # 19:00 y las 24:00 de Lima la fecha UTC ya es la del día siguiente.
        today = fields.Date.context_today(self.Role.with_context(tz=self.Role._al_role_tz()))
        # Vencimiento sin pasar por el ORM: lo detecta el cron.
        self.env.cr.execute(SQL(
            'UPDATE al_user_role_line SET date_to = %s WHERE id = %s',
            today - timedelta(days=1), line.id,
        ))
        self.env.invalidate_all()
        self.assertTrue(self.user.has_group('base.group_partner_manager'))
        self.Role._cron_update_users()
        self.env.invalidate_all()
        self.assertFalse(self.user.has_group('base.group_partner_manager'))

    def test_unique_role_per_user(self):
        self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})

    def test_default_role_on_new_user(self):
        self.role_contacts.is_default = True
        new_user = self.env['res.users'].create({'name': 'Nuevo', 'login': 'al_nuevo'})
        self.assertEqual(new_user.al_role_ids, self.role_contacts)
        self.assertTrue(new_user.has_group('base.group_partner_manager'))

    def test_unlink_role(self):
        self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})
        group = self.role_contacts.group_id
        self.role_contacts.unlink()
        self.assertFalse(group.exists())
        self.assertFalse(self.user.has_group('base.group_partner_manager'))

    def test_copy_role(self):
        copy = self.role_contacts.copy()
        self.assertEqual(copy.name, 'Rol contactos (copia)')
        self.assertNotEqual(copy.group_id, self.role_contacts.group_id)
        self.assertEqual(copy.implied_ids, self.role_contacts.implied_ids)

    def test_group_lists_its_roles(self):
        self.assertIn(self.role_contacts, self.group_partner_manager.al_role_ids)
        self.assertNotIn(self.role_internal, self.group_partner_manager.al_role_ids)
        action = self.role_contacts.group_id.action_al_view_roles()
        self.assertEqual(action['res_id'], self.role_contacts.id)

    def test_last_admin_keeps_admin(self):
        admin = self.env.ref('base.user_admin')
        group_system = self.env.ref('base.group_system')
        others = self.env['res.users'].search_count([
            ('id', '!=', admin.id), ('group_ids', 'in', group_system.id),
        ])
        if others:
            self.skipTest('Hay otros administradores en la base')
        self.Line.create({'role_id': self.role_internal.id, 'user_id': admin.id})
        self.assertTrue(admin.has_group('base.group_system'))

    def test_action_view_roles_from_user(self):
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.assertEqual(self.user.al_role_count, 1)
        action = self.user.action_al_view_roles()
        self.assertEqual((action['view_mode'], action['res_id']), ('form', self.role_internal.id))
        self.Line.create({'role_id': self.role_contacts.id, 'user_id': self.user.id})
        self.user.invalidate_recordset(['al_role_ids', 'al_role_count'])
        self.assertEqual(self.user.al_role_count, 2)
        action = self.user.action_al_view_roles()
        field, operator, ids = action['domain'][0]
        self.assertEqual((field, operator), ('id', 'in'))
        self.assertEqual(set(ids), set((self.role_internal | self.role_contacts).ids))

    def test_group_field_hidden_while_creating_in_debug_mode(self):
        # En modo desarrollador "Grupo asociado" es visible, y el cliente web
        # exige los campos requeridos visibles aunque sean de solo lectura. Lo
        # crea _inherits al guardar: debe estar oculto mientras no hay id.
        # Se revisa la definición de la vista: group_no_one depende del modo
        # desarrollador de la sesión web, que un test sin navegador no tiene.
        view = self.env.ref('al_user_role.view_al_user_role_form')
        node = etree.fromstring(view.arch).xpath("//field[@name='group_id']")
        self.assertEqual(len(node), 1)
        self.assertEqual(node[0].get('invisible'), 'not id')

    def test_default_role_in_new_user_form(self):
        # El formulario pide los valores por defecto con onchange: la
        # asignación del rol por defecto debe llegar (no filtrarse por active).
        self.role_internal.is_default = True
        spec = {'al_role_line_ids': {'fields': {'role_id': {'fields': {'display_name': {}}}}}}
        lines = self.env['res.users'].onchange({}, [], spec)['value'].get('al_role_line_ids')
        self.assertTrue(lines, 'El formulario de usuario nuevo no recibe el rol por defecto')
        role_ids = [vals['role_id']['id'] for _cmd, _id, vals in lines]
        self.assertIn(self.role_internal.id, role_ids)
