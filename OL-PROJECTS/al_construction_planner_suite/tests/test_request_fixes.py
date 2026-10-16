# -*- coding: utf-8 -*-
"""Correcciones del requerimiento de obra tras la prueba del 16-oct-2026
(caso de prueba del planificador, sección «Requerimiento de obra 19.0.19»):

- H-21: el mismo producto de dos niveles se despacha en un movimiento por
  línea y cada línea recibe lo suyo; «Por despachar» hasta que el almacén
  valida.
- H-25: la línea agregada a mano toma el nivel y la etapa únicos del recuadro.
- H-24: las etapas son las del perfil de la obra.
- H-28: una necesidad del plan ya pasada propone hoy.
- La regla de aprobación por exceso mira la política de materiales."""
from datetime import timedelta

from odoo import fields
from odoo.tests import Form, tagged

from .test_request_scope import TestRequestScope


@tagged('post_install', '-at_install')
class TestRequestFixes(TestRequestScope):

    def _approved_two_kitchens(self):
        source = self.company.construction_src_location_id
        self.p_hinge.is_storable = True
        self.env['stock.quant']._update_available_quantity(self.p_hinge, source, 500)
        request = self._new_request()
        self._scope(request, spaces=self.space_501 | self.space_502,
                    stages=self.stage_assembly)
        request.action_construction_fetch_plan()
        request.line_ids.filtered(lambda l: l.product_id != self.p_hinge).unlink()
        request.with_user(self.requester).action_request_approval()
        self.assertEqual(request.state, 'approved')
        return request.with_user(self.env.user)

    def test_dispatch_one_move_per_line(self):
        request = self._approved_two_kitchens()
        hinges = request.line_ids
        self.assertEqual(len(hinges), 2)
        request.action_process()
        moves = request.picking_ids.move_ids.filtered(lambda m: m.state != 'cancel')
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves.construction_request_line_id, hinges)
        # Antes de validar: por despachar, sin cantidad despachada.
        self.assertEqual(set(hinges.mapped('line_state')), {'dispatched'})
        self.assertEqual(dict(hinges._fields['line_state']._description_selection(self.env))
                         ['dispatched'], 'Por despachar')
        self.assertFalse(any(hinges.mapped('qty_dispatched')))
        picking = request.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        picking.move_ids.picked = True
        picking.button_validate()
        for line in hinges:
            self.assertEqual(line.qty_dispatched, line.product_qty, line.task_id.display_name)
            self.assertEqual(line.line_state, 'done')
        self.assertEqual(request.state, 'done')

    def test_manual_line_takes_single_level_and_stage(self):
        request = self._new_request()
        self._scope(request, spaces=self.space_501, stages=self.stage_assembly)
        with Form(request.with_user(self.requester)) as form:
            with form.line_ids.new() as line:
                line.product_id = self.p_screw
                line.product_qty = 3
        manual = request.line_ids
        self.assertEqual(manual.task_id, self.space_501)
        self.assertEqual(manual.construction_stage, 'assembly')
        # Con dos ambientes no hay uno solo que heredar.
        other = self._new_request()
        self._scope(other, spaces=self.space_501 | self.space_502, stages=self.stage_assembly)
        with Form(other.with_user(self.requester)) as form:
            with form.line_ids.new() as line:
                line.product_id = self.p_screw
                line.product_qty = 3
        self.assertFalse(other.line_ids.task_id)
        self.assertEqual(other.line_ids.construction_stage, 'assembly')

    def test_stages_follow_the_project_profile(self):
        furniture = self.env.ref('al_construction_planner.profile_furniture')
        self.project.construction_profile_id = furniture
        request = self._new_request()
        allowed = request.construction_allowed_stage_ids
        self.assertIn(self.stage_assembly, allowed)
        works = self.env.ref('al_construction_planner.stage_works_execution')
        self.assertNotIn(works, allowed)
        # Sin perfil, todas las etapas con recursos.
        project = self.env['project.project'].create({
            'name': 'Obra sin perfil (test)', 'is_construction_site': True})
        project.construction_profile_id = False
        project.message_subscribe(partner_ids=self.requester.partner_id.ids)
        request = self.env['construction.material.request'].with_user(self.requester).create(
            {'project_id': project.id})
        self.assertIn(works, request.construction_allowed_stage_ids)

    def test_past_need_date_proposes_today(self):
        today = fields.Date.context_today(self.plan)
        self.plan.line_ids.date_needed = today - timedelta(days=4)
        request = self._new_request()
        self._scope(request, spaces=self.space_501, stages=self.stage_assembly)
        request.action_construction_fetch_plan()
        self.assertEqual(request.date_required, today)
        self.plan.line_ids.date_needed = today + timedelta(days=10)
        later = self._new_request()
        self._scope(later, spaces=self.space_502, stages=self.stage_assembly)
        later.action_construction_fetch_plan()
        self.assertEqual(later.date_required, today + timedelta(days=10))

    def test_exceed_rule_follows_material_policy(self):
        """Con la general en aprobación y materiales en «Solo alerta», el
        exceso se avisa pero no pasa por la jefatura."""
        self.plan.write({'exceed_policy': 'approval', 'exceed_policy_material': 'warn'})
        request = self._new_request()
        self._scope(request, spaces=self.space_501, stages=self.stage_assembly)
        request.action_construction_fetch_plan()
        hinge = request.line_ids.filtered(lambda l: l.product_id == self.p_hinge)
        hinge.product_qty += 2
        request.with_user(self.requester).with_context(
            construction_exceed_checked=True).action_request_approval()
        self.assertEqual(request.construction_exceed_policy, 'warn')
        self.assertEqual(request.construction_exceed_state, 'exceeded')
        self.assertFalse(request.review_ids)
        self.assertEqual(request.state, 'approved')
        # Con materiales en aprobación, sí pasa por la jefatura.
        self.plan.exceed_policy_material = 'approval'
        other = self._new_request()
        self._scope(other, spaces=self.space_502, stages=self.stage_assembly)
        other.action_construction_fetch_plan()
        hinge = other.line_ids.filtered(lambda l: l.product_id == self.p_hinge)
        hinge.product_qty += 2
        other.construction_exceed_reason = 'Cambio de bisagras (test)'
        other.with_user(self.requester).with_context(
            construction_exceed_checked=True).action_request_approval()
        self.assertEqual(other.construction_exceed_policy, 'approval')
        self.assertEqual(other.state, 'to_approve')
        self.assertTrue(other.review_ids)


# Las pruebas heredadas ya corren en TestRequestScope.
for _name in dir(TestRequestScope):
    if _name.startswith('test_') and callable(getattr(TestRequestScope, _name)) \
            and _name not in TestRequestFixes.__dict__:
        setattr(TestRequestFixes, _name, None)
