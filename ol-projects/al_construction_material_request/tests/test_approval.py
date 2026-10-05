# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import convert_file

from .common import ConstructionRequestCommon


@tagged('post_install', '-at_install')
class TestApproval(ConstructionRequestCommon):

    def _submitted(self, lines=None):
        request = self._new_request(lines=lines, user=self.requester)
        request.action_request_approval()
        return request

    def test_one_level_project_manager(self):
        request = self._submitted()
        self.assertEqual(request.state, 'to_approve')
        self.assertEqual(len(request.review_ids), 1)
        self.assertEqual(request.review_ids.reviewer_ids, self.approver)
        # el solicitante no puede aprobar su propio requerimiento
        self.assertFalse(request.can_review)
        self.assertTrue(request.with_user(self.approver).can_review)
        request.with_user(self.approver).validate_tier()
        self.assertEqual(request.validation_status, 'validated')
        self.assertEqual(request.state, 'approved')

    def test_two_levels_above_threshold_in_sequence(self):
        # 400 bolsas × 30 = 12 000 > 10 000
        request = self._submitted(lines=[(self.cement, 400)])
        self.assertEqual(len(request.review_ids), 2)
        self.assertFalse(request.with_user(self.operations).can_review)
        request.with_user(self.approver).validate_tier()
        self.assertEqual(request.state, 'to_approve')
        as_operations = request.with_user(self.operations)
        self.assertTrue(as_operations.can_review)
        as_operations.validate_tier()
        self.assertEqual(request.state, 'approved')

    def test_reviewer_sees_request_of_foreign_site(self):
        request = self._submitted(lines=[(self.cement, 400)])
        request.with_user(self.approver).validate_tier()
        Request = self.env['construction.material.request'].with_user(self.operations)
        # (acotado a las obras del test: la base puede tener datos demo)
        sites = self.site_a | self.site_b
        self.assertEqual(
            Request.search([('can_review', '=', True), ('project_id', 'in', sites.ids)]),
            request)

    def test_reject_then_resubmit(self):
        request = self._submitted()
        request.with_user(self.approver).reject_tier()
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.validation_status, 'rejected')
        request.action_draft()
        self.assertFalse(request.review_ids)
        request.action_request_approval()
        self.assertEqual(request.review_ids.status, 'pending')

    def test_withdraw_under_approval(self):
        request = self._submitted()
        request.action_draft()
        self.assertEqual(request.state, 'draft')
        self.assertFalse(request.review_ids)

    def test_without_applicable_rules_approves_directly(self):
        (self.tier_manager | self.tier_operations).active = False
        request = self._submitted()
        self.assertFalse(request.review_ids)
        self.assertEqual(request.state, 'approved')

    def test_site_without_manager_skips_level_one(self):
        # Odoo pone al usuario actual como jefe al crear el proyecto
        self.site_b.user_id = False
        request = self._new_request(project=self.site_b, user=self.other_requester)
        request.action_request_approval()
        self.assertEqual(request.state, 'approved')

    def test_edits_under_approval(self):
        request = self._submitted()
        with self.assertRaises(ValidationError):
            request.write({'note': 'cambio en revisión'})
        # logística ajusta la fecha requerida durante la aprobación
        request.with_user(self.logistics).date_required = '2026-10-15'
        self.assertEqual(str(request.date_required), '2026-10-15')

    def test_demo_data_100_bags_with_60_available(self):
        """Carga el XML demo en la transacción y recorre el caso de aceptación
        (plan §9.3): 100 bolsas pedidas, 60 en almacén."""
        convert_file(self.env, 'al_construction_material_request',
                     'demo/construction_demo.xml', {}, mode='init')
        request = self.env.ref('al_construction_material_request.demo_request_school')
        site = self.env.ref('al_construction_material_request.demo_site_school')
        self.assertTrue(site.construction_location_id)
        self.assertEqual(request.location_dest_id, site.construction_location_id)
        (self.tier_manager | self.tier_operations).active = False
        demo_tiers = self.env.ref('al_construction_material_request.demo_tier_project_manager') \
            | self.env.ref('al_construction_material_request.demo_tier_operations')
        self.assertTrue(all(demo_tiers.mapped('active')))

        request.action_request_approval()
        self.assertEqual(request.review_ids.reviewer_ids, self.env.ref('base.user_admin'))
        # la regla demo pide comentario: se valida sin pasar por el asistente
        request.with_user(self.env.ref('base.user_admin'))._validate_tier()
        self.assertEqual(request.state, 'approved')

        request.with_user(self.logistics).action_process()
        dispatch = request.picking_ids.move_ids.filtered(
            lambda m: m.procure_method == 'make_to_stock')
        self.assertEqual((dispatch.product_uom_qty, dispatch.quantity), (60, 60))
        self.assertEqual(request.purchase_request_ids.line_ids.product_qty, 40)
        self.assertEqual(dispatch.construction_analytic_distribution,
                         request.line_ids.analytic_distribution)
