# -*- coding: utf-8 -*-
"""Campos editables según el estado y botones solo con datos que abrir,
comprobado sobre la vista compuesta (lo que ve el usuario)."""
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStateReadonly(TransactionCase):

    def _arch(self, model, xmlid, view_type='form'):
        view = self.env[model].get_view(self.env.ref(xmlid).id, view_type)
        return etree.fromstring(view['arch'])

    def _attr(self, arch, xpath, attr):
        nodes = arch.xpath(xpath)
        self.assertTrue(nodes, xpath)
        return ' '.join(node.get(attr) or '' for node in nodes)

    def test_liquidation_move_button_only_without_move(self):
        arch = self._arch('hr.liquidation', 'al_hr_pe_benefits.hr_liquidation_view_form')
        self.assertIn('account_move_id', self._attr(
            arch, "//field[@name='liq_move_ids']//button[@name='action_open_move_wizard']", 'invisible'))
