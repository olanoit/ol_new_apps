# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ConstructionRequestCommon


@tagged('post_install', '-at_install')
class TestSkeleton(ConstructionRequestCommon):

    def test_site_location_created_under_obras(self):
        location = self.site_a.construction_location_id
        self.assertTrue(location)
        self.assertEqual(location.location_id, self.company.construction_sites_location_id)
        self.assertEqual(location.usage, 'internal')
        # un proyecto que no es obra no recibe ubicación
        project = self.env['project.project'].create({'name': 'Oficina (test)'})
        self.assertFalse(project.construction_location_id)
        project.is_construction_site = True
        self.assertTrue(project.construction_location_id)

    def test_setup_is_idempotent(self):
        dispatch = self.company.construction_dispatch_type_id
        self.assertEqual(dispatch.code, 'internal')
        self.company._al_construction_ensure_setup()
        self.assertEqual(self.company.construction_dispatch_type_id, dispatch)

    def test_defaults_and_sequence(self):
        request = self._new_request(user=self.requester)
        self.assertTrue(request.name.startswith('RQO/'))
        self.assertEqual(request.requested_by, self.requester)
        self.assertEqual(request.location_dest_id, self.site_a.construction_location_id)
        self.assertEqual(request.location_src_id, self.stock)
        self.assertEqual(request.project_manager_id, self.approver)
        self.assertAlmostEqual(request.amount_estimated, 3000.0)

    def test_available_now_sums_family_sublocations(self):
        self._set_stock(self.cement, self.loc_cement, 40)
        self._set_stock(self.cement, self.stock, 20)
        request = self._new_request()
        self.assertEqual(request.line_ids.qty_available_now, 60)
        # el residente (sin acceso a inventario) también la ve
        line = request.line_ids.with_user(self.requester)
        line.invalidate_recordset(['qty_available_now'])
        self.assertEqual(line.qty_available_now, 60)

    def test_available_now_in_line_uom(self):
        uom_dozen = self.env.ref('uom.product_uom_dozen')
        self._set_stock(self.cement, self.loc_cement, 60)
        request = self._new_request()
        request.line_ids.product_uom_id = uom_dozen
        self.assertEqual(request.line_ids.qty_available_now, 5)

    def test_state_flow_reject_and_back_to_draft(self):
        request = self._new_request(user=self.requester)
        request.action_request_approval()
        self.assertEqual(request.state, 'to_approve')
        request.with_user(self.approver).reject_tier()
        self.assertEqual(request.state, 'rejected')
        request.action_draft()
        self.assertEqual(request.state, 'draft')
        self.assertFalse(request.review_ids)
        with self.assertRaises(UserError):
            request.action_process()

    def test_submit_requires_lines(self):
        request = self._new_request(lines=[])
        with self.assertRaises(UserError):
            request.action_request_approval()

    def test_requester_does_not_see_other_sites(self):
        mine = self._new_request(user=self.requester)
        other = self._new_request(project=self.site_b, user=self.other_requester)
        Request = self.env['construction.material.request'].with_user(self.requester)
        visible = Request.search([('id', 'in', (mine | other).ids)])
        self.assertEqual(visible, mine)
        with self.assertRaises(AccessError):
            other.with_user(self.requester).read(['name'])
        # el jefe de la obra A la ve aunque no la haya pedido
        self.assertTrue(mine.with_user(self.approver).read(['name']))
        # logística ve todas
        self.assertEqual(
            Request.with_user(self.logistics).search_count([('id', 'in', (mine | other).ids)]), 2)
