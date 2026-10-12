# -*- coding: utf-8 -*-
"""v1.5, fase 16: portal de obra (P-23 a P-25)."""
import re

from odoo.tests import HttpCase, new_test_user, tagged

from .common import PlannerCommon

PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00'
       b'\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00'
       b'\x00\x00\x00IEND\xaeB`\x82')


@tagged('post_install', '-at_install')
class TestPortalV15(HttpCase, PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        wizard = cls.env['construction.plan.generate.wizard'].create({'plan_id': cls.plan.id})
        wizard.action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.contract_lines = cls.plan.line_ids.filtered(
            lambda l: l.resource_type == 'contract' and l.activity_id == cls.act_doors)
        cls.contract_lines.partner_id = cls.contractor
        cls.plan.action_request_approval()
        cls.portal_user = new_test_user(
            cls.env, 'contrata_portal', groups='base.group_portal', name='Capataz Gonza (test)',
            partner_id=cls.env['res.partner'].create({
                'name': 'Capataz Gonza (test)', 'parent_id': cls.contractor.id}).id)
        cls.other = new_test_user(cls.env, 'otra_contrata', groups='base.group_portal',
                                  name='Otra contrata (test)')

    def _csrf(self, url):
        page = self.url_open(url)
        return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)

    def test_portal_lists_only_own_work(self):
        self.assertEqual(self.plan.state, 'approved')
        self.authenticate('contrata_portal', 'contrata_portal')
        page = self.url_open('/my/obra')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Colocación de puertas', page.text)
        self.assertNotIn('Armado módulo tarugo', page.text, 'solo lo asignado a su empresa')
        self.authenticate('otra_contrata', 'otra_contrata')
        page = self.url_open('/my/obra')
        self.assertNotIn('Colocación de puertas', page.text)
        form = self.url_open('/my/obra/avance?project_id=%s&activity_id=%s'
                             % (self.project.id, self.act_doors.id))
        self.assertIn('/my/obra', form.url, 'otra contrata no ve el formulario')

    def test_portal_registers_progress_with_photo_and_location(self):
        self.authenticate('contrata_portal', 'contrata_portal')
        url = '/my/obra/avance?project_id=%s&activity_id=%s' % (self.project.id, self.act_doors.id)
        line = self.contract_lines[0]
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url),
            'qty_%s' % line.id: '1',
            'latitude': '-12.0464', 'longitude': '-77.0428', 'date': '2026-11-03',
        }, files={'photos': ('avance.png', PNG, 'image/png')})
        self.assertEqual(response.status_code, 200)
        progress = self.env['construction.task.progress'].search([('plan_line_id', '=', line.id)])
        self.assertEqual(len(progress), 1)
        self.assertEqual((progress.source, progress.state, progress.qty), ('portal', 'draft', 1.0))
        self.assertEqual(progress.reported_by_id, self.portal_user)
        self.assertEqual(progress.photo_count, 1)
        self.assertAlmostEqual(progress.latitude, -12.0464, 4)
        history = self.url_open('/my/obra/avances')
        self.assertIn('Por validar', history.text)

    def test_portal_rejects_without_photo(self):
        self.authenticate('contrata_portal', 'contrata_portal')
        url = '/my/obra/avance?project_id=%s&activity_id=%s' % (self.project.id, self.act_doors.id)
        line = self.contract_lines[0]
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url),
            'qty_%s' % line.id: '1'})
        self.assertIn('al menos una foto', response.text)
        self.assertFalse(self.env['construction.task.progress'].search([('plan_line_id', '=', line.id)]))
