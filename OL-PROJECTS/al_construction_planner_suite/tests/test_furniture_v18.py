# -*- coding: utf-8 -*-
"""Modelo del mueble de mobiliario (v1.8, M18-17 a M18-20): tipo de mueble y
de módulo, método de unión propuesto por reglas, catálogo de actividades con
listas de tarifas por familia y obra, y contratas desde las piezas."""
from odoo import Command
from odoo.tests import tagged

from .common import PlannerCommon

REF = 'al_construction_planner_furniture.'


@tagged('post_install', '-at_install')
class TestFurnitureModelV18(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env['product.product']
        cls.screw = Product.create({'name': 'Tornillo 4x50 (test v18)', 'type': 'consu'})
        cls.screw_install = Product.create({'name': 'Tornillo 5x60 (test v18)', 'type': 'consu'})
        cls.dowel = Product.create({'name': 'Tarugo 8x30 (test v18)', 'type': 'consu'})
        cls.company.write({
            'construction_join_screw_product_ids': [Command.set(cls.screw.ids)],
            'construction_join_dowel_product_ids': [Command.set(cls.dowel.ids)]})

        def module(code, name, materials, pieces=()):
            return Command.create({
                'code': code, 'name': name, 'module_type': 'low', 'width_mm': 600,
                'ml_group': 'low',
                'material_ids': [Command.create({'product_id': p.id, 'qty': q, 'stage': st})
                                 for p, q, st in materials],
                'piece_ids': [Command.create({'qty': q, 'length_mm': l, 'width_mm': w,
                                              'piece_type': t}) for q, l, w, t in pieces]})

        cls.typology_v18 = cls.env['construction.typology'].create({
            'project_id': cls.project.id, 'code': 'C04', 'name': 'COCINA 04 (test)',
            'family': 'kitchen', 'module_line_ids': [
                module('M1', 'MOD BAJO 665', [(cls.screw, 12, 'assembly'),
                                              (cls.dowel, 12, 'assembly'),
                                              (cls.screw_install, 4, 'installation')],
                       [(2, 730, 400, 'PUERTA'), (2, 780, 560, 'COSTADO')]),
                module('M2', 'MOD BAJO 800', [(cls.screw, 25, 'assembly')]),
                module('M3', 'MOD ALTO MICROONDAS 600', [(cls.screw, 20, 'assembly')]),
                module('M4', 'MOD ZOCALO', []),
                module('M5', 'MOD RARO', [(cls.screw, 3, 'assembly')]),
            ]})
        cls.space_601 = cls.task('Cocina 601', 'space', cls.apt_501,
                                 construction_typology_id=cls.typology_v18.id)

    def _module(self, code):
        return self.typology_v18.module_line_ids.filtered(lambda m: m.code == code)

    def test_join_method_and_special_kind(self):
        """Criterio M18-18: 12 tornillos y 12 tarugos es mixto, 25 tornillos es
        tornillo, el zócalo va sin unión; los 5x60 de instalación no cuentan."""
        self.assertEqual(self._module('M1').join_method, 'mixed')
        self.assertEqual(self._module('M2').join_method, 'screw')
        self.assertEqual(self._module('M4').special_kind, 'plinth')
        self.assertEqual(self._module('M4').join_method, 'none')
        self.assertEqual(self._module('M3').module_class, 'special')
        self.assertEqual(self._module('M3').special_kind, 'microwave')
        self.assertFalse(self._module('M5').join_method)
        self.assertIn('no calza', self._module('M5').join_warning)
        self._module('M5').join_method = 'minifix'
        self.assertEqual(self._module('M5').join_method, 'minifix')

    def test_catalog_lines_and_project_rate_list(self):
        """Criterio M18-19: el módulo mixto genera «Armado módulo mixto» y el de
        microondas «Armado microondas», en 1.2 con la tarifa de la lista de la
        obra; M18-20: la colocación de puertas sale de las piezas PUERTA."""
        mixed = self.env.ref(REF + 'activity_mob_arm_mix')
        micro = self.env.ref(REF + 'activity_mob_arm_mic')
        doors = self.env.ref(REF + 'activity_mob_com_pue')
        self.env['construction.rate.list'].create({
            'name': 'Cocinas MOMEN (test)', 'family': 'kitchen_bath',
            'project_id': self.project.id, 'line_ids': [
                Command.create({'activity_id': mixed.id, 'price': 7.5}),
                Command.create({'activity_id': doors.id, 'price': 3.2})]})
        self._generate(space_task_ids=[Command.set(self.space_601.ids)])
        lines = self.plan.line_ids.filtered(lambda l: l.space_task_id == self.space_601)
        mixed_line = lines.filtered(lambda l: l.activity_id == mixed)
        self.assertEqual(len(mixed_line), 1)
        self.assertEqual(mixed_line.stage, 'assembly')
        self.assertEqual(mixed_line.task_id.construction_join_method, 'mixed')
        self.assertAlmostEqual(mixed_line.price_unit_planned, 7.5)
        micro_line = lines.filtered(lambda l: l.activity_id == micro)
        self.assertEqual(micro_line.task_id.construction_special_kind, 'microwave')
        # Sin versión de la obra, la lista general de cocina y baño.
        self.assertAlmostEqual(micro_line.price_unit_planned, 7.0)
        door_line = lines.filtered(lambda l: l.activity_id == doors)
        self.assertAlmostEqual(door_line.qty_planned, 0.8)
        self.assertAlmostEqual(door_line.price_unit_planned, 3.2)
        # La receta del módulo trae sus materiales con su sub etapa.
        screws = lines.filtered(lambda l: l.product_id == self.screw_install)
        self.assertEqual(screws.stage, 'installation')
        self.assertAlmostEqual(screws.qty_planned, 4.0)
        # Closet y cajones: otra lista, más baja.
        self.typology_v18.family = 'closet'
        self.assertAlmostEqual(self.env.ref(REF + 'activity_mob_arm_tor').with_context(
            construction_rate_family='closet_drawer')._get_rate(self.project)[0], 5.5)
