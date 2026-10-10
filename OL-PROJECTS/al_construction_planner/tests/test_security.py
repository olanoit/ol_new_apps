# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestSecurity(PlannerCommon):

    def test_planner_generates(self):
        wizard = self.env['construction.plan.generate.wizard'].with_user(self.planner).create({
            'plan_id': self.plan.id, 'space_task_ids': [(6, 0, self.space_501.ids)]})
        wizard.action_generate()
        self.assertEqual(self.plan.line_count, 17)

    def test_reporter_reads_only(self):
        self._generate(space_task_ids=[(6, 0, self.space_501.ids)])
        plan = self.plan.with_user(self.reporter)
        self.assertEqual(plan.line_ids.with_user(self.reporter).mapped('plan_id'), self.plan)
        with self.assertRaises(AccessError):
            plan.write({'exceed_tolerance': 5})
        with self.assertRaises(AccessError):
            self.env['construction.labor.rate'].with_user(self.reporter).create({
                'activity_id': self.act_dowel.id, 'price': 1})
        with self.assertRaises(AccessError):
            self.env['construction.plan.generate.wizard'].with_user(self.reporter).create({
                'plan_id': self.plan.id})

    def test_multicompany(self):
        company_b = self.env['res.company'].create({'name': 'Compañía B (test)'})
        project_b = self.env['project.project'].with_company(company_b).create({
            'name': 'Obra B (test)', 'company_id': company_b.id, 'is_construction_site': True})
        plan_b = self.env['construction.resource.plan'].with_company(company_b).create({
            'project_id': project_b.id})
        self.assertEqual(plan_b.company_id, company_b)
        # Un usuario solo de la compañía A no ve el plan de B.
        self.assertFalse(self.env['construction.resource.plan'].with_user(self.planner).search(
            [('id', '=', plan_b.id)]))
        # Una actividad propia de B no entra en una tipología de A.
        activity_b = self.env['construction.labor.activity'].create({
            'code': 'B-ARM', 'name': 'Armado B', 'stage': 'assembly', 'module_level': True,
            'uom_id': self.unit.id, 'company_id': company_b.id})
        with self.assertRaises(UserError):
            self.typology.module_line_ids[0].assembly_activity_id = activity_b
        # Una actividad compartida (sin compañía, por importación) vale en cualquier obra.
        self.act_dowel.company_id = False
        self.typology.module_line_ids[1].assembly_activity_id = self.act_dowel
        # Un nivel de otra obra no entra al plan.
        task_b = self.env['project.task'].create({
            'name': 'Piso B', 'project_id': project_b.id, 'construction_level': 'floor'})
        with self.assertRaises(ValidationError):
            self.env['construction.resource.plan.line'].create({
                'plan_id': self.plan.id, 'task_id': task_b.id, 'resource_type': 'material',
                'product_id': self.p_cap.id, 'product_uom_id': self.unit.id,
                'qty_planned': 1})
