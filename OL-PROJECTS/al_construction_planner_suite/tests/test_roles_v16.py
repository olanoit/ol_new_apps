# -*- coding: utf-8 -*-
"""Aprobadores, permisos y portal de armado (v1.6, M16-09 a M16-11).

- Las reglas de validación del planificador las aprueba el grupo de jefatura
  de proyectos: cualquiera de sus miembros (un reemplazo también). Desde los
  dos ejes (CREVAL v1.0, capítulo 5) la regla cita Ejecución: aprueba, que la
  jefatura y el administrador incluyen.
- El asistente de proyectos crea el requerimiento a obra y lo envía, pero no
  lo aprueba ni valida su despacho.
- La contrata de armado reporta por el portal los módulos armados, como la de
  instalación.
"""
import re

from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import PlannerCommon
from .test_portal_v15 import PNG

GRP = 'al_construction_planner.group_planner_'


@tagged('post_install', '-at_install')
class TestRoles(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company._al_construction_ensure_setup()
        cls.head = new_test_user(cls.env, 'rol_jefa', name='Jefa de proyectos (test)',
                                 groups=f'{GRP}project_head')
        cls.replacement = new_test_user(cls.env, 'rol_reemplazo', name='Reemplazo (test)',
                                        groups=f'{GRP}project_head')
        cls.admin_only = new_test_user(cls.env, 'rol_admin', name='Administrador (test)',
                                       groups=f'{GRP}manager')
        cls.assistant = new_test_user(cls.env, 'rol_asistente', name='Asistente (test)',
                                      groups=f'{GRP}assistant')
        cls.project.message_subscribe(
            partner_ids=(cls.head | cls.replacement | cls.assistant).partner_id.ids)
        # Solo las reglas del módulo sobre el requerimiento.
        cls.tier_extra = cls.env.ref('al_construction_planner_purchase.tier_material_request_extra')
        cls.env['tier.definition'].search([
            ('model', '=', 'construction.material.request'),
            ('id', 'not in', (cls.tier_extra | cls.env.ref(
                'al_construction_planner_purchase.tier_material_request_exceed')).ids)]).active = False

    def test_module_rules_point_to_project_head(self):
        head = self.env.ref(f'{GRP}project_head')
        approver = self.env.ref(f'{GRP}exec_approver')
        for xmlid in ('al_construction_planner_purchase.tier_material_request_exceed',
                      'al_construction_planner_subcontract.tier_contract_settlement_manager',
                      'al_construction_planner.tier_measurement_difference',
                      'al_construction_planner_purchase.tier_material_request_extra'):
            self.assertEqual(self.env.ref(xmlid).reviewer_group_id, approver, xmlid)
        self.assertIn(approver, head.all_implied_ids)
        self.assertNotIn(self.env.ref(f'{GRP}manager'), head.all_implied_ids)
        self.assertNotIn(head, self.env.ref(f'{GRP}manager').all_implied_ids)

    def _extra(self):
        return self.env['construction.material.request'].with_user(self.assistant).create({
            'project_id': self.project.id,
            'task_id': self.space_501.id,
            'is_extra': True,
            'extra_reason': 'waste',
            'line_ids': [(0, 0, {'product_id': self.p_white.id, 'product_qty': 2})],
        })

    def test_any_project_head_approves(self):
        extra = self._extra()
        extra.action_request_approval()
        review = extra.review_ids
        self.assertIn(self.head, review.reviewer_ids)
        self.assertIn(self.replacement, review.reviewer_ids)
        # El administrador incluye Ejecución: aprueba (CREVAL v1.0, 5.2).
        self.assertIn(self.admin_only, review.reviewer_ids)
        self.assertNotIn(self.assistant, review.reviewer_ids)
        extra.with_user(self.replacement).validate_tier()
        self.assertEqual(extra.state, 'approved')

    def test_assistant_creates_but_does_not_approve(self):
        extra = self._extra()
        self.assertEqual(extra.state, 'draft')
        extra.action_request_approval()
        self.assertEqual(extra.state, 'to_approve')
        self.assertFalse(extra.with_user(self.assistant).can_review)
        with self.assertRaises(UserError):
            extra.with_user(self.assistant).write({
                'construction_discount': True,
                'construction_discount_partner_id': self.contractor.id})
        self.assertFalse(self.assistant.has_group(
            'al_construction_material_request.group_construction_logistics'))
        self.assertFalse(self.assistant.has_group(
            'al_construction_material_request.group_construction_approver'))

    def test_head_decides_discount_and_change(self):
        """Los controles de código que eran del administrador aceptan también
        a la jefatura."""
        extra = self._extra()
        extra.with_user(self.head).write({
            'construction_discount': True,
            'construction_discount_partner_id': self.contractor.id,
            'construction_discount_amount': 10.0})
        self.assertTrue(extra.construction_discount)


@tagged('post_install', '-at_install')
class TestPortalAssembly(HttpCase, PlannerCommon):
    """M16-11: la contrata de armado reporta módulos armados por el portal."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        wizard = cls.env['construction.plan.generate.wizard'].create({'plan_id': cls.plan.id})
        wizard.action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.assembly_lines = cls.plan.line_ids.filtered(
            lambda l: l.resource_type == 'contract' and l.activity_id == cls.act_dowel)
        cls.assembly_lines.partner_id = cls.contractor
        cls.plan.action_request_approval()
        new_test_user(
            cls.env, 'capataz_armado', groups='base.group_portal', name='Capataz armado (test)',
            partner_id=cls.env['res.partner'].create({
                'name': 'Capataz armado (test)', 'parent_id': cls.contractor.id}).id)

    def _csrf(self, url):
        page = self.url_open(url)
        return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)

    def test_assembly_progress_by_module(self):
        self.assertEqual(self.plan.state, 'approved')
        # Tarugo 1, 2 y 3 en cada una de las dos cocinas: una línea por módulo.
        self.assertEqual(len(self.assembly_lines), 6)
        self.assertEqual(set(self.assembly_lines.task_id.mapped('construction_level')), {'module'})
        self.authenticate('capataz_armado', 'capataz_armado')
        self.assertIn('Armado módulo tarugo', self.url_open('/my/obra').text)
        url = '/my/obra/avance?project_id=%s&activity_id=%s' % (self.project.id, self.act_dowel.id)
        page = self.url_open(url)
        line = self.assembly_lines.filtered(lambda l: l.space_task_id == self.space_501)[:1]
        self.assertIn('qty_%s' % line.id, page.text)
        self.assertIn(line.task_id.name, page.text)
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url), 'qty_%s' % line.id: '1', 'date': '2026-11-03',
        }, files={'photos': ('armado.png', PNG, 'image/png')})
        self.assertEqual(response.status_code, 200)
        progress = self.env['construction.task.progress'].search([('plan_line_id', '=', line.id)])
        self.assertEqual((progress.source, progress.state, progress.qty), ('portal', 'draft', 1.0))
        self.assertEqual(progress.task_id, line.task_id)
        progress.action_validate()
        self.assertEqual(line.qty_executed, 1.0)
