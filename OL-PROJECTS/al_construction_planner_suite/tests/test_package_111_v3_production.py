# -*- coding: utf-8 -*-
"""Paquete 1.7 parte 2, vigente según el 1.9: requerimiento de producción al
jefe de producción (M17-18) y usabilidad del asistente (M17-25)."""
from datetime import timedelta

from odoo import fields
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon

DATE_REVIEW = 'al_construction_planner_mrp.mail_activity_production_date_review'


@tagged('post_install', '-at_install')
class TestPackage111V3Production(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.head = new_test_user(cls.env, 'm1718_jefe_produccion', groups='mrp.group_mrp_user',
                                 name='Jefe de producción (test)')
        cls.company.write({'construction_production_date_review': True,
                           'construction_production_head_id': cls.head.id})
        code = cls.env['construction.stage']._production_codes()[0]
        today = fields.Date.context_today(cls.env.user)
        cls.stage = cls.env['construction.space.stage'].create({
            'space_task_id': cls.space_501.id, 'stage': code,
            'date_start': today, 'date_end': today + timedelta(days=4)})
        cls.production = cls.env['mrp.production'].create({
            'product_id': cls.kitchen.product_variant_id.id, 'bom_id': cls.bom.id,
            'construction_plan_id': cls.plan.id,
            'construction_space_task_ids': [(6, 0, cls.space_501.ids)]})

    # M17-25: el aviso dice el departamento, no solo «Cocina».
    def test_space_label_with_apartment(self):
        Wizard = self.env['construction.plan.production.wizard']
        self.assertEqual(Wizard._space_label(self.space_501), 'Dpto 501 / Cocina')
        self.assertEqual(Wizard._space_label(self.space_502), 'Dpto 502 / Cocina')

    # M17-18: actividad al jefe y fecha confirmada en la orden y el cronograma.
    def test_confirmed_date_moves_production_stage(self):
        self.production._construction_schedule_date_review()
        activity = self.production.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref(DATE_REVIEW))
        self.assertEqual(activity.user_id, self.head)
        self.assertIn(str(self.stage.date_end), activity.note)
        confirmed = self.stage.date_end + timedelta(days=7)
        duration = self.stage.date_end - self.stage.date_start
        # El jefe de producción solo tiene «Fabricación: usuario».
        self.production.with_user(self.head).construction_date_confirmed = confirmed
        self.assertEqual(self.stage.date_end, confirmed)
        self.assertEqual(self.stage.date_end - self.stage.date_start, duration)
        self.assertEqual(self.production.date_deadline.date(), confirmed)
        self.assertFalse(self.production.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref(DATE_REVIEW)))

    def test_option_off_no_activity(self):
        self.company.construction_production_date_review = False
        self.production._construction_schedule_date_review()
        self.assertFalse(self.production.activity_ids)


# Las pruebas heredadas ya corren en su clase.
for _name in dir(PlannerCommon):
    if _name.startswith('test_') and callable(getattr(PlannerCommon, _name)) \
            and _name not in vars(TestPackage111V3Production):
        setattr(TestPackage111V3Production, _name, None)
