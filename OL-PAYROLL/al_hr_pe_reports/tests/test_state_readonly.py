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

    def test_multipayment_done_is_readonly(self):
        arch = self._arch('hr.automate.multipayment', 'al_hr_pe_reports.hr_automate_multipayment_view_form')
        for fname in ('name', 'charge_account_id', 'journal_id', 'process_type', 'subtype_banbif'):
            self.assertIn("state == 'done'", self._attr(arch, "//field[@name='%s']" % fname, 'readonly'), fname)
