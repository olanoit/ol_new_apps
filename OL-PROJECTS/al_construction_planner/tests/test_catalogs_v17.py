# -*- coding: utf-8 -*-
"""Catálogos de etapas y tipos de recurso (v1.7, M17-02 y M17-03).

Las etapas de mobiliario son registros del catálogo con los códigos de
siempre; una constructora agrega las suyas (trazo, emplacado, masillado) y
el plan las acepta sin código nuevo. El tipo de recurso del catálogo fija el
comportamiento de la línea y el control agrupa por él.
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import PlannerCommon

REF = 'al_construction_planner.'


@tagged('post_install', '-at_install')
class TestStageCatalog(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Stage = cls.env['construction.stage']
        cls.trace = Stage.create({'name': 'Trazo (test)', 'code': 'test_trace', 'kind': 'field',
                                  'sequence': 110})
        cls.board = Stage.create({'name': 'Emplacado (test)', 'code': 'test_board',
                                  'kind': 'field', 'sequence': 120,
                                  'previous_stage_id': cls.trace.id})
        cls.shop = Stage.create({'name': 'Prefabricación en taller (test)',
                                 'code': 'test_shop', 'kind': 'production', 'sequence': 130})

    def test_furniture_stages_keep_their_codes(self):
        codes = self.env['construction.stage']._codes()
        self.assertEqual(codes[:4], ['production', 'assembly', 'installation', 'finishing'])
        line_field = self.env['construction.resource.plan.line']._fields['stage']
        labels = dict(line_field._description_selection(self.env))
        self.assertEqual(labels['installation'], 'Instalación')
        self.assertEqual(labels['test_board'], 'Emplacado (test)')

    def test_plan_accepts_catalog_stages_only(self):
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': self.plan.id, 'resource_type': 'contract',
            'activity_id': self.act_doors.id, 'stage': 'test_board', 'qty_planned': 4,
            'product_uom_id': self.unit.id})
        self.assertEqual(line.stage, 'test_board')
        with self.assertRaises(ValidationError):
            line.stage = 'no_such_stage'

    def test_behavior_by_kind(self):
        Stage = self.env['construction.stage']
        self.assertEqual(set(Stage._production_codes()), {'production', 'assembly', 'test_shop'})
        self.assertIn('test_trace', Stage._field_codes())
        self.assertNotIn('test_shop', Stage._field_codes())
        self.assertEqual(Stage._consumption_code('production'), 'production')
        self.assertEqual(Stage._consumption_code('site'), 'installation')
        # «Asignar contrata» sin etapa: todas las de campo, no las de taller.
        wizard = self.env['construction.plan.contract.wizard'].new({'plan_id': self.plan.id})
        self.assertFalse(wizard.stage)
        self.assertIn('test_trace', wizard._get_stages())
        self.assertNotIn('test_shop', wizard._get_stages())

    def test_used_code_is_locked(self):
        self.env['construction.resource.plan.line'].create({
            'plan_id': self.plan.id, 'resource_type': 'contract',
            'activity_id': self.act_doors.id, 'stage': 'test_trace', 'qty_planned': 1,
            'product_uom_id': self.unit.id})
        with self.assertRaises(UserError):
            self.trace.code = 'test_trace_2'
        with self.assertRaises(UserError):
            self.trace.unlink()
        self.trace.name = 'Trazo y replanteo (test)'
        self.assertIn(('test_trace', 'Trazo y replanteo (test)'),
                      self.env['construction.stage']._get_selection())
        # Una etapa archivada se sigue leyendo en lo ya registrado.
        self.trace.active = False
        self.assertIn('test_trace', self.env['construction.stage']._codes())

    def test_wizard_stages_from_schedule_selection(self):
        self._generate_and_approve()
        wizard = self.env['construction.plan.purchase.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_stages=['test_board'],
        ).create({})
        self.assertEqual(wizard.stage_ids, self.board)
        self.assertFalse(wizard.line_ids)


@tagged('post_install', '-at_install')
class TestResourceTypeCatalog(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.labor_contract = cls.env['construction.resource.type'].create({
            'name': 'Mano de obra de contrata (test)', 'code': 'test_mo_contract',
            'behavior': 'contract', 'supply_method': 'contract'})
        cls.crane = cls.env['product.product'].create({
            'name': 'Andamio (test)', 'type': 'service', 'standard_price': 20.0})
        cls.hour = cls.env.ref('uom.product_uom_hour')

    def _line(self, **vals):
        return self.env['construction.resource.plan.line'].create(dict({
            'plan_id': self.plan.id, 'task_id': self.space_501.id, 'stage': 'installation',
            'qty_planned': 1.0, 'price_unit_planned': 10.0, 'product_uom_id': self.unit.id},
            **vals))

    def test_behavior_gets_default_type(self):
        line = self._line(resource_type='equipment', product_id=self.crane.id, qty_planned=3,
                          price_unit_planned=20.0)
        self.assertEqual(line.resource_type_id, self.env.ref(REF + 'resource_type_equipment'))
        material = self._line(resource_type='material', product_id=self.p_white.id)
        self.assertEqual(material.resource_type_id, self.env.ref(REF + 'resource_type_material'))
        self.assertAlmostEqual(self.plan.amount_equipment, 60.0)

    def test_type_sets_behavior(self):
        line = self._line(resource_type_id=self.labor_contract.id,
                          activity_id=self.act_doors.id, qty_planned=4, price_unit_planned=3.0)
        self.assertEqual(line.resource_type, 'contract')
        self.assertEqual(line.resource_type_id, self.labor_contract)
        line.resource_type_id = self.env.ref(REF + 'resource_type_labor')
        self.assertEqual(line.resource_type, 'labor')

    def test_control_separates_the_four_types(self):
        """Receta con material, mano de obra de contrata, cuadrilla propia y
        equipo: cuatro tipos, cuatro filas en el control."""
        self._line(resource_type='material', product_id=self.p_white.id, qty_planned=2,
                   price_unit_planned=100.0)
        self._line(resource_type_id=self.labor_contract.id, activity_id=self.act_doors.id,
                   qty_planned=10, price_unit_planned=3.0)
        self._line(resource_type='labor', activity_id=self.act_doors.id, qty_planned=8,
                   product_uom_id=self.hour.id, price_unit_planned=12.0)
        self._line(resource_type='equipment', product_id=self.crane.id, qty_planned=2,
                   price_unit_planned=20.0)
        data = self.plan._get_control_data()
        types = self.env['construction.resource.type'].union(*(rtype for _stage, rtype in data))
        self.assertEqual(types, self.labor_contract | self.env.ref(REF + 'resource_type_material')
                         | self.env.ref(REF + 'resource_type_labor')
                         | self.env.ref(REF + 'resource_type_equipment'))
        self.assertAlmostEqual(data[('installation', self.labor_contract)]['planned'], 30.0)
        self.assertIn('Mano de obra de contrata (test)', self.plan.control_html)
        self.assertIn('Equipo', self.plan.control_html)

    def test_one_default_per_behavior(self):
        with self.assertRaises(UserError):
            self.labor_contract.is_default = True
