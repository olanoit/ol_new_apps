# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import Form, new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestRequestScope(PlannerCommon):
    """Requerimiento de obra con selección de nivel y etapa (RQ-01 a RQ-07):
    niveles en cascada, «Traer materiales del plan», control de exceso, obra
    sin plan y material de producción a la preproducción de la planta."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.requester = new_test_user(
            cls.env, 'rq_supervisor', name='Supervisor de proyectos (test)',
            groups='al_construction_material_request.group_construction_requester,'
                   'project.group_project_user')
        # Solo la regla de exceso del puente: las demás (p. ej. las demo) se
        # apagan para que el requerimiento sin exceso se apruebe solo.
        tier_exceed = cls.env.ref('al_construction_planner_purchase.tier_material_request_exceed')
        cls.env['tier.definition'].search([
            ('model', '=', 'construction.material.request'),
            ('id', '!=', tier_exceed.id)]).active = False
        cls.company._al_construction_ensure_setup()
        cls.company.construction_request_production_stage = True
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        cls.project.message_subscribe(partner_ids=cls.requester.partner_id.ids)
        wizard = cls.env['construction.plan.generate.wizard'].create({'plan_id': cls.plan.id})
        wizard.action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state
        cls.stage_assembly = cls.env['construction.stage'].search([('code', '=', 'assembly')])
        cls.stage_production = cls.env['construction.stage'].search(
            [('code', '=', 'production')])
        warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.plant = cls.env['stock.location'].create({
            'name': 'Preproducción (test)', 'usage': 'internal',
            'location_id': warehouse.view_location_id.id,
            'construction_preproduction': True})

    def _new_request(self, user=None):
        return self.env['construction.material.request'].with_user(
            user or self.requester).create({'project_id': self.project.id})

    def _scope(self, request, floors=(), apartments=(), spaces=(), stages=()):
        request.write({
            'construction_scope_1_ids': [(6, 0, [t.id for t in floors])],
            'construction_scope_2_ids': [(6, 0, [t.id for t in apartments])],
            'construction_scope_3_ids': [(6, 0, [t.id for t in spaces])],
            'construction_stage_ids': [(6, 0, [s.id for s in stages])],
        })

    def _hinge_qty(self, task):
        return sum(line._qty_to_product_uom(line.qty_planned) for line in self.plan.line_ids
                   if line.product_id == self.p_hinge and line.stage == 'assembly'
                   and line.task_id and task.id in [
                       int(i) for i in line.task_path.split('/') if i])

    # ------------------------------------------------------------------
    # RQ-01 selectores en cascada
    # ------------------------------------------------------------------
    def test_scope_slots_follow_levels(self):
        request = self._new_request()
        self.assertEqual(
            [request['construction_scope_%s_label' % depth] for depth in range(1, 5)],
            ['Piso', 'Departamento', 'Ambiente', False])
        self.assertEqual(request.construction_scope_2_allowed_ids, self.apt_501 | self.apt_502)
        # Cascada: el ambiente solo ofrece los del departamento elegido.
        with Form(request.with_user(self.requester)) as form:
            form.construction_scope_2_ids.add(self.apt_501)
            form.construction_scope_3_ids.add(self.space_501)
        self.assertEqual(request.construction_scope_2_ids, self.apt_501)
        self.assertEqual(request.construction_scope_3_ids, self.space_501)
        self.assertEqual(request.construction_scope_3_allowed_ids, self.space_501)
        # Cambiar el departamento quita el ambiente que ya no cuelga de él.
        with Form(request.with_user(self.requester)) as form:
            form.construction_scope_2_ids.clear()
            form.construction_scope_2_ids.add(self.apt_502)
        self.assertFalse(request.construction_scope_3_ids)
        self.assertEqual(request.construction_scope_3_allowed_ids, self.space_502)

    # ------------------------------------------------------------------
    # RQ-04 traer materiales del plan
    # ------------------------------------------------------------------
    def test_fetch_lowest_level_and_stage(self):
        request = self._new_request()
        self._scope(request, floors=self.floor, apartments=self.apt_501 | self.apt_502,
                    spaces=self.space_501 | self.space_502, stages=self.stage_assembly)
        request.action_construction_fetch_plan()
        lines = request.line_ids
        self.assertTrue(lines)
        self.assertEqual(set(lines.mapped('construction_stage')), {'assembly'})
        self.assertEqual(set(lines.task_id.ids), {self.space_501.id, self.space_502.id})
        hinges = lines.filtered(lambda l: l.product_id == self.p_hinge).sorted(
            lambda l: l.task_id.parent_id.name)
        self.assertEqual(hinges.mapped('construction_level_label'),
                         ['Dpto 501 / Cocina', 'Dpto 502 / Cocina'])
        self.assertEqual(hinges.mapped('product_qty'),
                         [self._hinge_qty(self.space_501), self._hinge_qty(self.space_502)])
        # Cada línea queda enlazada a sus líneas del plan y dentro del saldo.
        for line in lines:
            self.assertTrue(line.construction_allocation_ids)
            self.assertEqual(line.construction_plan_control, 'En plan')
            self.assertEqual(line.construction_allocation_ids.plan_line_id.mapped('stage'),
                             ['assembly'] * len(line.construction_allocation_ids))
        # Pulsar otra vez no duplica: ya no queda saldo.
        count = len(lines)
        with self.assertRaises(UserError):
            request.action_construction_fetch_plan()
        self.assertEqual(len(request.line_ids), count)
        # Una línea borrada vuelve en la siguiente pulsación (solo esa).
        hinges[:1].unlink()
        request.action_construction_fetch_plan()
        self.assertEqual(len(request.line_ids), count)

    def test_fetch_floor_only(self):
        request = self._new_request()
        self._scope(request, floors=self.floor, stages=self.stage_assembly)
        request.action_construction_fetch_plan()
        hinge = request.line_ids.filtered(lambda l: l.product_id == self.p_hinge)
        self.assertEqual(hinge.task_id, self.floor)
        self.assertEqual(hinge.product_qty, self._hinge_qty(self.floor))
        self.assertEqual(set(hinge.construction_allocation_ids.plan_line_id.space_task_id.ids),
                         {self.space_501.id, self.space_502.id})
        self.assertNotIn(self.p_white, request.line_ids.product_id)

    def test_fetch_excess_marks_line(self):
        request = self._new_request()
        self._scope(request, spaces=self.space_501, stages=self.stage_assembly)
        request.action_construction_fetch_plan()
        hinge = request.line_ids.filtered(lambda l: l.product_id == self.p_hinge)
        hinge.product_qty = hinge.product_qty + 5
        self.assertTrue(hinge.construction_plan_exceeded)
        self.assertIn('Excede', hinge.construction_plan_control)

    # ------------------------------------------------------------------
    # RQ-03 y RQ-06 tareas del Gantt y obra sin plan
    # ------------------------------------------------------------------
    def test_gantt_task_and_project_without_plan(self):
        project = self.env['project.project'].create({
            'name': 'Obra sin plan (test)', 'is_construction_site': True})
        project.message_subscribe(partner_ids=self.requester.partner_id.ids)
        gantt_task = self.env['project.task'].create({
            'name': 'Movilización', 'project_id': project.id})
        request = self.env['construction.material.request'].with_user(self.requester).create({
            'project_id': project.id})
        self.assertFalse(request.construction_plan_id)
        self.assertFalse(request.construction_has_levels)
        with self.assertRaises(UserError):
            request.action_construction_fetch_plan()
        with Form(request.with_user(self.requester)) as form:
            form.construction_gantt_task_ids.add(gantt_task)
            with form.line_ids.new() as line:
                line.product_id = self.p_screw
                line.product_qty = 50
        self.assertEqual(request.line_ids.task_id, gantt_task)
        self.assertEqual(request.line_ids.product_qty, 50)

    # ------------------------------------------------------------------
    # RQ-07 material de producción
    # ------------------------------------------------------------------
    def test_production_goes_to_plant(self):
        source = self.company.construction_src_location_id
        (self.p_white | self.p_hinge).is_storable = True
        Quant = self.env['stock.quant']
        Quant._update_available_quantity(self.p_white, source, 100)
        Quant._update_available_quantity(self.p_hinge, source, 100)
        request = self._new_request()
        self._scope(request, spaces=self.space_501,
                    stages=self.stage_production | self.stage_assembly)
        self.assertTrue(request.construction_needs_plant)
        request.action_construction_fetch_plan()
        with self.assertRaises(UserError):
            request.with_user(self.requester).action_request_approval()
        request.construction_production_location_id = self.plant
        production = request.line_ids.filtered(lambda l: l.construction_stage == 'production')
        assembly = request.line_ids - production
        self.assertTrue(production and assembly)
        self.assertEqual(production.location_dest_id, self.plant)
        self.assertEqual(set(assembly.location_dest_id.ids),
                         {self.project.construction_location_id.id})
        request.with_user(self.requester).action_request_approval()
        self.assertEqual(request.state, 'approved')
        request = request.with_user(self.env.user)
        request.action_process()
        pickings = request.picking_ids.filtered(lambda p: p.state != 'cancel')
        by_dest = {p.location_dest_id: p for p in pickings}
        self.assertIn(self.plant, by_dest)
        self.assertIn(self.project.construction_location_id, by_dest)
        plant_moves = by_dest[self.plant].move_ids
        self.assertTrue(plant_moves.construction_request_line_id <= production)
        self.assertIn(self.p_white, plant_moves.product_id)
        self.assertFalse(by_dest[self.project.construction_location_id].move_ids
                         .construction_request_line_id & production)
        self.assertTrue(all(move.construction_analytic_distribution for move in plant_moves))
        self.assertEqual(plant_moves.construction_analytic_distribution,
                         production[:1].analytic_distribution)

    def test_production_stage_setting(self):
        request = self._new_request()
        self.assertIn(self.stage_production, request.construction_allowed_stage_ids)
        self.company.construction_request_production_stage = False
        request.invalidate_recordset(['construction_allowed_stage_ids'])
        self.assertNotIn(self.stage_production, request.construction_allowed_stage_ids)
        self.assertIn(self.stage_assembly, request.construction_allowed_stage_ids)
        request.write({'line_ids': [(0, 0, {
            'product_id': self.p_white.id, 'product_qty': 1,
            'construction_stage': 'production'})],
            'construction_production_location_id': self.plant.id})
        with self.assertRaises(UserError):
            request.with_user(self.requester).action_request_approval()
