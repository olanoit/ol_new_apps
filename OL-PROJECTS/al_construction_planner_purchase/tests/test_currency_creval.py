# -*- coding: utf-8 -*-
"""Partidas en dólares en una obra en soles (requerimiento CREVAL v1.0, 6.5):
una línea del plan en dólares genera desde la compra masiva una orden de
compra en dólares, y el control de saldo de la partida se lleva en soles con
el tipo de cambio de la orden, con la diferencia de cambio aparte. Datos
ficticios."""
from datetime import date, datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestDollarLine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        cls.usd = env.ref('base.USD')
        if cls.company.currency_id == cls.usd:
            cls.usd = env.ref('base.EUR')
        cls.usd.active = True
        Rate = env['res.currency.rate']
        Rate.create({'name': date(2026, 1, 1), 'currency_id': cls.usd.id,
                     'company_id': cls.company.root_id.id, 'inverse_company_rate': 3.5})
        Rate.create({'name': date(2026, 3, 1), 'currency_id': cls.usd.id,
                     'company_id': cls.company.root_id.id, 'inverse_company_rate': 3.8})
        env['tier.definition'].search([('model', 'in', (
            'construction.resource.plan', 'purchase.request', 'purchase.order'))]).active = False
        stage = env['construction.stage'].create({
            'name': 'Mobiliario (test)', 'code': 'usd_test_stage', 'sequence': 930})
        template = env['construction.level.template'].create({
            'name': 'Especialidad y partida (test dólares)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Partida', 'role': 'space'})]})
        lines = template.line_ids.sorted('sequence')
        cls.project = env['project.project'].create({
            'name': 'Obra en soles (test)', 'is_construction_site': True,
            'construction_level_template_id': template.id})
        group = env['project.task'].create({'name': 'Equipamiento (test)',
                                            'project_id': cls.project.id,
                                            'construction_level_line_id': lines[0].id})
        cls.partida = env['project.task'].create({
            'name': 'Sillas (test)', 'project_id': cls.project.id, 'parent_id': group.id,
            'construction_level_line_id': lines[1].id})
        cls.chair = env['product.product'].create({
            'name': 'Silla ergonómica (test)', 'type': 'consu', 'purchase_ok': True})
        cls.plan = env['construction.resource.plan'].create(
            {'project_id': cls.project.id, 'date_start': date(2026, 2, 1)})
        cls.line = env['construction.resource.plan.line'].create({
            'plan_id': cls.plan.id, 'task_id': cls.partida.id, 'resource_type': 'material',
            'product_id': cls.chair.id, 'product_uom_id': cls.chair.uom_id.id,
            'qty_planned': 10.0, 'stage': stage.code, 'price_currency_id': cls.usd.id,
            'price_unit_currency': 180.0})
        cls.plan.action_request_approval()
        cls.vendor = env['res.partner'].create({'name': 'Muebles Import (test)'})

    def test_dollar_purchase_and_control(self):
        self.assertAlmostEqual(self.line.price_unit_planned, 630.0)  # 180 × 3.5
        wizard = self.env['construction.plan.purchase.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create({})
        request = self.env['purchase.request'].browse(wizard.action_create()['res_id'])
        pr_line = request.line_ids
        self.assertEqual(pr_line.construction_currency_id, self.usd)
        self.assertEqual(pr_line.construction_price_unit_currency, 180.0)
        request.button_to_approve()
        request.button_approved()
        maker = self.env['purchase.request.line.make.purchase.order'].with_context(
            active_model='purchase.request.line', active_ids=pr_line.ids,
        ).create({'supplier_id': self.vendor.id})
        action = maker.make_purchase_order()
        order = self.env['purchase.order'].browse(set(action['domain'][0][2]))
        self.assertEqual(order.currency_id, self.usd)
        self.assertEqual(order.order_line.price_unit, 180.0)
        order.button_confirm()
        order.date_approve = datetime(2026, 3, 5, 15, 0)
        self.line.invalidate_recordset()
        # 10 sillas × 180 × (3.8 − 3.5): la diferencia de cambio, sin desvío de
        # precio.
        self.assertAlmostEqual(self.line.amount_fx_diff, 540.0)
        self.assertAlmostEqual(self.line.amount_price_diff, 0.0)
        committed, _actual = self.line._get_line_execution()[self.line]
        self.assertAlmostEqual(committed, 6300.0 + 540.0)
