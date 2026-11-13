# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import AlUserRoleCommon


@tagged('post_install', '-at_install')
class TestAlUserRoleCompany(AlUserRoleCommon):
    """Un rol con compañía solo aplica cuando esa compañía está activa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_b = cls.env['res.company'].create({'name': 'Compañía B'})
        cls.user.write({'company_ids': [Command.link(cls.company_b.id)]})

    def _apply(self, companies):
        self.user.with_context(al_active_company_ids=companies.ids)._al_apply_roles()

    def test_role_only_in_its_company(self):
        self.Line.create({'role_id': self.role_internal.id, 'user_id': self.user.id})
        self.Line.create({
            'role_id': self.role_contacts.id, 'user_id': self.user.id,
            'company_id': self.company_b.id,
        })
        self._apply(self.company)
        self.assertFalse(self.user.has_group('base.group_partner_manager'))
        self._apply(self.company_b)
        self.assertTrue(self.user.has_group('base.group_partner_manager'))
        # Con las dos compañías activas, el rol debe estar en ambas.
        self._apply(self.company | self.company_b)
        self.assertFalse(self.user.has_group('base.group_partner_manager'))
        self.Line.create({
            'role_id': self.role_contacts.id, 'user_id': self.user.id,
            'company_id': self.company.id,
        })
        self._apply(self.company | self.company_b)
        self.assertTrue(self.user.has_group('base.group_partner_manager'))

    def test_same_role_in_two_companies(self):
        for company in (self.company, self.company_b):
            self.Line.create({
                'role_id': self.role_contacts.id, 'user_id': self.user.id,
                'company_id': company.id,
            })
        self.assertEqual(len(self.user.al_role_line_ids), 2)

    def test_company_must_be_allowed(self):
        company_c = self.env['res.company'].create({'name': 'Compañía C'})
        with self.assertRaises(ValidationError):
            self.Line.create({
                'role_id': self.role_contacts.id, 'user_id': self.user.id,
                'company_id': company_c.id,
            })
