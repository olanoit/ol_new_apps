# -*- coding: utf-8 -*-
"""v1.5, fase 14: contrato de obra, hitos de cobro y valorización por hitos."""
import base64
from datetime import date

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon

PDF = base64.b64encode(b'%PDF-1.4 conformidad')


@tagged('post_install', '-at_install')
class TestContractV15(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.revenue = new_test_user(
            cls.env, 'plan_ingresos_v15', name='Ingresos (test)',
            groups='al_construction_planner.group_planner_revenue,'
                   'al_construction_planner.group_planner_manager,sales_team.group_sale_salesman_all_leads')
        cls.customer = cls.env['res.partner'].create({'name': 'Inmobiliaria Andina (test)'})
        product = cls.env['product.product'].create({
            'name': 'Cocinas (test)', 'type': 'service', 'invoice_policy': 'delivery'})
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.customer.id,
            'order_line': [Command.create({'product_id': product.id, 'name': 'Cocinas',
                                           'product_uom_qty': 1, 'price_unit': 1000.0,
                                           'tax_ids': [Command.clear()]})]})
        cls.order.action_confirm()
        cls.manual = cls.env['construction.milestone.template'].create({
            'name': 'Manual 60/40 (test)', 'line_ids': [
                Command.create({'sequence': 1, 'name': 'Avance', 'pct': 60, 'trigger': 'manual'}),
                Command.create({'sequence': 2, 'name': 'Llegada', 'pct': 40,
                                'trigger': 'material_arrival'})]})
        cls.contract = cls.env['construction.contract'].create({
            'name': 'Cocinas MOMEN (test)', 'project_id': cls.project.id,
            'partner_id': cls.customer.id, 'sale_order_id': cls.order.id,
            'milestone_template_id': cls.manual.id, 'discount_factor': 1.0,
            'advance_pct': 10.0, 'guarantee_pct': 5.0,
            'price_line_ids': [Command.create({
                'typology_id': cls.typology.id, 'unit_price': 500.0,
                'sale_line_id': cls.order.order_line.id})],
            'document_ids': [Command.create({'name': 'Dossier de calidad', 'required': True})],
        })

    def _confirm(self, valuation):
        valuation._action_confirm({
            'confirm_date': date(2026, 11, 18), 'confirm_name': 'Ing. Rosa Quispe',
            'confirm_role': 'Residente',
            'confirm_attachment_ids': [Command.create({'name': 'ok.pdf', 'datas': PDF})],
        }, {line: line.amount_delivered for line in valuation.line_ids})

    def test_templates_sum_100(self):
        self.assertEqual(self.env.ref(
            'al_construction_planner.milestone_template_80_15_5').summary, '80 / 15 / 5')
        with self.assertRaises(ValidationError):
            self.env['construction.milestone.template'].create({
                'name': 'Mal (test)', 'line_ids': [
                    Command.create({'name': 'A', 'pct': 50, 'trigger': 'manual'}),
                    Command.create({'name': 'B', 'pct': 40, 'trigger': 'manual'})]})

    def test_mark_units(self):
        wizard = self.env['construction.contract.unit.wizard'].create({
            'contract_id': self.contract.id, 'mode': 'even'})
        wizard.action_apply()
        self.assertFalse(self.contract.task_ids, 'el piso 05 es impar')
        wizard = self.env['construction.contract.unit.wizard'].create({
            'contract_id': self.contract.id, 'mode': 'odd'})
        wizard.action_apply()
        self.assertEqual(self.contract.task_ids, self.apt_501 | self.apt_502)
        wizard = self.env['construction.contract.unit.wizard'].create({
            'contract_id': self.contract.id, 'mode': 'list', 'task_ids': [(6, 0, self.apt_501.ids)]})
        wizard.action_apply()
        self.assertEqual(self.contract.task_ids, self.apt_501)
        self.assertEqual(self.apt_501.construction_contract_id, self.contract)
        self.assertEqual(self.space_501.construction_contract_id, self.contract, 'por su unidad')
        self.assertFalse(self.apt_502.construction_contract_id)

    def test_milestones_and_valuations(self):
        contract = self.contract.with_user(self.revenue)
        contract.action_generate_milestones()
        self.assertEqual(len(contract.milestone_ids), 4, '2 unidades × 2 hitos')
        self.assertEqual(sorted(set(contract.milestone_ids.mapped('amount'))), [200.0, 300.0])
        self.assertEqual(contract.amount_total, 1000.0)
        contract.action_activate()
        with self.assertRaises(UserError):
            contract.action_prepare_valuation()  # sin avance
        first = contract.milestone_ids.filtered(
            lambda m: m.task_id == self.apt_501 and m.trigger == 'manual')
        first.manual_pct = 50
        self.assertEqual(first.progress_pct, 50)
        action = contract.action_prepare_valuation()
        valuation = self.env['construction.valuation'].browse(action['res_id'])
        self.assertEqual(valuation.contract_id, self.contract)
        self.assertEqual(valuation.line_ids.amount_delivered, 150.0)
        self.assertAlmostEqual(valuation.line_ids.progress_cumulative, 0.15)
        self.assertEqual(valuation.milestone_line_ids.amount, 150.0)
        with self.assertRaises(UserError):
            valuation.action_send()  # falta el dossier
        self.contract.document_ids.received = True
        valuation.action_send()
        self._confirm(valuation)
        self.assertEqual(first.billed_pct, 50)
        # El mismo hito se termina de cobrar en la siguiente valorización.
        first.manual_pct = 100
        second = self.env['construction.valuation'].browse(
            contract.action_prepare_valuation()['res_id'])
        self.assertEqual(second.milestone_line_ids.pct_before, 50)
        self.assertEqual(second.line_ids.amount_delivered, 150.0)
        self.assertEqual(second.line_ids.confirmed_before, 150.0)

    def test_material_arrival_trigger(self):
        self._generate()
        self.contract.action_generate_milestones()
        arrival = self.contract.milestone_ids.filtered(
            lambda m: m.task_id == self.apt_501 and m.trigger == 'material_arrival')
        self.assertEqual(arrival.progress_pct, 0)
        modules = self.env['project.task'].search([
            ('construction_apartment_task_id', '=', self.apt_501.id),
            ('construction_level', '=', 'module')])
        modules[:len(modules) // 2 + 1].construction_unit_state = 'on_site'
        arrival.invalidate_recordset(['progress_pct'])
        self.assertAlmostEqual(arrival.progress_pct,
                               round((len(modules) // 2 + 1) / len(modules) * 100, 2))
