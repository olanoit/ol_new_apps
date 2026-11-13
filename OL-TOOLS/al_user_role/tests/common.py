# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import TransactionCase


class AlUserRoleCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Role = cls.env['al.user.role']
        cls.Line = cls.env['al.user.role.line']
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_erp_manager = cls.env.ref('base.group_erp_manager')
        cls.group_partner_manager = cls.env.ref('base.group_partner_manager')
        cls.company = cls.env.company
        cls.user = cls.env['res.users'].create({
            'name': 'Usuario roles',
            'login': 'al_usuario_roles',
            'group_ids': [Command.set(cls.group_user.ids)],
        })
        cls.role_internal = cls.Role.create({
            'name': 'Rol interno',
            'exclusive_permissions': True,
            'implied_ids': [Command.set(cls.group_user.ids)],
        })
        cls.role_contacts = cls.Role.create({
            'name': 'Rol contactos',
            'exclusive_permissions': True,
            'implied_ids': [Command.set((cls.group_user | cls.group_partner_manager).ids)],
        })
