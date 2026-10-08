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

    def test_period_follows_payslip_state(self):
        arch = self._arch('hr.payslip', 'hr_payroll.view_hr_payslip_form')
        self.assertIn('paid', self._attr(arch, "//field[@name='periodo_id']", 'readonly'))
        arch = self._arch('hr.payslip.run', 'hr_payroll.hr_payslip_run_form')
        self.assertIn('01_ready', self._attr(arch, "//field[@name='periodo_id']", 'readonly'))
