# -*- coding: utf-8 -*-
"""Adicionales de la contrata (requerimiento CREVAL v1.0, 3.9): el cambio de
obra aprobado se agrega a la orden de contrata y, si pasa el monto aprobado,
la diferencia vuelve a aprobación. Datos ficticios."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.al_construction_planner_subcontract.tests.test_contract_terms_creval import (
    ContractTermsCommon,
)


@tagged('post_install', '-at_install')
class TestAdditional(ContractTermsCommon):

    def test_additional_to_contract_order(self):
        _wizard, order = self._assign()
        order.button_confirm()
        approved = order.construction_amount_approved
        change = self.env['construction.change.order'].create({
            'project_id': self.project.id, 'kind': 'additional', 'requested_by': 'contractor',
            'reason': 'Sellado adicional pedido por la supervisión',
            'line_ids': [(0, 0, {
                'task_id': self.extra_task.id, 'resource_type': 'contract',
                'activity_id': self.act_seal.id, 'stage': 'creval_tab', 'qty': 50.0,
                'price_unit': 18.0})]})
        self.assertFalse(change.construction_can_add_to_order)
        change.action_approve()
        self.assertTrue(change.construction_can_add_to_order)
        with self.assertRaises(UserError):
            change.action_add_to_contract_order()  # sin contratista
        change.construction_contractor_id = self.contractor
        change.action_add_to_contract_order()
        line = change.construction_purchase_line_ids
        self.assertEqual(line.order_id, order)
        self.assertTrue(line.construction_is_additional)
        self.assertEqual(line.product_qty, 50.0)
        self.assertEqual(line.construction_task_id, self.extra_task)
        # La orden pasa su monto aprobado: la diferencia espera aprobación y el
        # adicional no se valoriza hasta entonces.
        self.assertGreater(order.amount_total, approved)
        self.assertTrue(order.construction_needs_reapproval)
        self.assertTrue(line.construction_additional_pending)
        progress = self.env['construction.task.progress'].create({
            'task_id': self.extra_task.id, 'activity_id': self.act_seal.id,
            'date': date(2026, 11, 4), 'qty': 40.0,
            'attachment_ids': [(0, 0, {'name': 'foto.jpg', 'datas': b'iVBORw0KGgo='})]})
        progress.action_validate()
        order.action_construction_approve_extension()
        self.assertFalse(order.construction_needs_reapproval)
        self.assertFalse(line.construction_additional_pending)
        self.assertEqual(order.construction_amount_approved, order.amount_total)
        self.assertFalse(change.construction_can_add_to_order)
