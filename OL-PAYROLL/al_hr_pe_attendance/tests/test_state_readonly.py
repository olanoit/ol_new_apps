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

    def test_tareaje_detail(self):
        arch = self._arch('hr.tareaje.manager', 'al_hr_pe_attendance.hr_tareaje_manager_view_form')
        self.assertIn('attendance_line_ids', self._attr(
            arch, "//button[@name='action_show_details']", 'invisible'))
        arch = self._arch('hr.tareaje.manager.line.attendance',
                          'al_hr_pe_attendance.hr_tareaje_manager_line_attendance_view_list', 'list')
        for fname in ('dlab', 'he25', 'hours_compensate'):
            self.assertIn("tareaje_state == 'done'", self._attr(arch, "//field[@name='%s']" % fname, 'readonly'))
