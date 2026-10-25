# -*- coding: utf-8 -*-
"""Paquete 1.11, M111-21: el requerimiento interno con el motor «Aplicación
Aprobaciones» pasa por el jefe del departamento de quien pide o, sin jefe,
por el grupo de la opción M111-19 C; el resultado es el mismo que con los
niveles. Quien pide solo es «Solicitante interno»."""
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_material_request.tests.common import ConstructionRequestCommon

GRP = 'al_construction_material_request.group_construction_'
TIER_INTERNAL = 'al_construction_material_request.tier_definition_internal_department_manager'


@tagged('post_install', '-at_install')
class TestPackage111InternalApprovals(ConstructionRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env['account.analytic.plan'].create({'name': 'Área (test M111-21)'})
        cls.company.construction_area_plan_id = plan
        cls.area = cls.env['account.analytic.account'].create({
            'name': 'Administración (test M111-21)', 'plan_id': plan.id,
            'company_id': cls.company.id})
        cls.env.ref(TIER_INTERNAL).active = True
        cls.company.construction_internal_fallback_group_id = cls.env.ref(f'{GRP}logistics')
        cls.clerk = new_test_user(cls.env, 'm11121_asistente', groups=f'{GRP}internal_requester',
                                  name='Asistente administrativa (test)')
        cls.loner = new_test_user(cls.env, 'm11121_sin_jefe', groups=f'{GRP}internal_requester',
                                  name='Sin jefe (test)')
        cls.head = new_test_user(cls.env, 'm11121_jefe', groups=f'{GRP}approver',
                                 name='Jefa de administración (test)')
        Employee = cls.env['hr.employee']
        head = Employee.create({'name': 'Jefa de administración (test)', 'user_id': cls.head.id})
        department = cls.env['hr.department'].create({
            'name': 'Administración (test M111-21)', 'manager_id': head.id})
        Employee.create({'name': 'Asistente administrativa (test)', 'user_id': cls.clerk.id,
                         'department_id': department.id})
        cls.paper = cls.env['product.product'].create({
            'name': 'Papel A4 (test M111-21)', 'type': 'consu', 'is_storable': True,
            'standard_price': 12.0})

    def _internal(self, user, engine):
        self.company.construction_approval_engine = engine
        request = self.env['construction.material.request'].with_user(user).create({
            'request_type': 'internal', 'area_id': self.area.id,
            'line_ids': [(0, 0, {'product_id': self.paper.id, 'product_qty': 2})]})
        request.action_request_approval()
        return request

    def test_department_head_in_approvals(self):
        request = self._internal(self.clerk, 'approvals')
        self.assertEqual(request.construction_approval_engine, 'approvals')
        self.assertEqual(request.state, 'to_approve')
        self.assertFalse(request.review_ids)
        approval = request.construction_approval_id
        self.assertEqual(approval.approver_ids.user_id, self.head)
        self.assertIn(self.head, approval.activity_ids.user_id)
        # La jefa aprueba desde el requerimiento, sin administrar Aprobaciones.
        request.with_user(self.head).action_construction_approve()
        self.assertEqual(request.state, 'approved')

    def test_without_head_goes_to_fallback_group(self):
        request = self._internal(self.loner, 'approvals')
        self.assertFalse(request.construction_department_manager_id)
        self.assertEqual(request.state, 'to_approve')
        approvers = request.construction_approval_id.approver_ids.user_id
        self.assertIn(self.logistics, approvers)
        self.assertNotIn(self.loner, approvers)
        request.with_user(self.logistics).action_construction_approve()
        self.assertEqual(request.state, 'approved')

    def test_without_group_is_approved_on_request(self):
        self.company.construction_internal_fallback_group_id = False
        request = self._internal(self.loner, 'approvals')
        self.assertEqual(request.state, 'approved')
        self.assertFalse(request.construction_approval_ids)

    def test_same_result_with_both_engines(self):
        """Mismo aprobador y mismo resultado con los niveles y con Aprobaciones."""
        tiers = self._internal(self.clerk, 'tier')
        self.assertEqual(tiers.state, 'to_approve')
        self.assertEqual(tiers.review_ids.reviewer_ids, self.head)
        tiers.with_user(self.head).validate_tier()
        approvals = self._internal(self.clerk, 'approvals')
        self.assertEqual(approvals.construction_approval_id.approver_ids.user_id, self.head)
        approvals.with_user(self.head).action_construction_approve()
        self.assertEqual((tiers.state, approvals.state), ('approved', 'approved'))
