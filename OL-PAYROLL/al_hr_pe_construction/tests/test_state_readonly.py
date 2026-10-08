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

    def test_conafovicer_and_site(self):
        arch = self._arch('l10n_pe.hr.conafovicer', 'al_hr_pe_construction.view_conafovicer_form')
        self.assertIn('paid', self._attr(arch, "//field[@name='payment_reference']", 'readonly'))
        arch = self._arch('l10n_pe.hr.construction.site', 'al_hr_pe_construction.view_construction_site_form')
        self.assertIn('employee_count', self._attr(arch, "//button[@name='action_view_employees']", 'invisible'))
