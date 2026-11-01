# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4, bloque 4b (M116-10): los ML de closets, baños,
lavanderías y ductos cuentan para la obra.

Criterios: la tipología suma «ML de mueble completo» aparte de bajo y alto, el
ML total los suma a los tres, y una actividad de instalación de closet por ML
genera en el plan la cantidad de ML de los closets.
"""
from odoo.tests import tagged

from odoo.addons.al_construction_planner.models.common import ML_COUNTED, ML_GROUPS

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage116Stage4FullFurniture(PlannerCommon):

    def test_full_furniture_ml(self):
        self.assertIn('full', dict(ML_GROUPS))
        self.assertEqual(ML_COUNTED, ('low', 'high', 'full'))
        closet = self.env['construction.typology'].create({
            'project_id': self.project.id, 'code': 'CL01', 'name': 'Closet 01',
            'family': 'closet',
            'module_line_ids': [
                (0, 0, {'sequence': 1, 'code': 'CL01-M', 'module_type': 'other',
                        'width_mm': 1200, 'ml_group': 'full',
                        'assembly_activity_id': self.act_screw.id}),
                (0, 0, {'sequence': 2, 'code': 'ZOC', 'module_type': 'other',
                        'width_mm': 800, 'ml_group': 'none',
                        'assembly_activity_id': self.act_screw.id})],
        })
        self.assertAlmostEqual(closet.ml_full, 1.2)
        self.assertAlmostEqual(closet.ml_low + closet.ml_high, 0.0)
        self.assertAlmostEqual(closet.ml_total, 1.2, msg='el zócalo sigue sin ML')
        kitchen_total = self.typology.ml_low + self.typology.ml_high
        self.assertAlmostEqual(self.typology.ml_total, kitchen_total)
        self.assertAlmostEqual(closet._ml_of_group('full'), 1.2)
        # Instalación de closet por ML: la tarifa va en la lista de su familia
        # (configuración); el plan toma los ML de los closets.
        install = self.env['construction.labor.activity'].create({
            'code': 'INS-CLO', 'name': 'Instalación de closet por ML', 'stage': 'installation',
            'default_price': 12.0, 'uom_id': self.meter.id, 'ml_based': True,
            'ml_group': 'full'})
        self.env['construction.labor.rate'].create({
            'activity_id': install.id, 'project_id': self.project.id, 'price': 14.0})
        space = self.task('Closet', 'space', self.apt_501, construction_typology_id=closet.id)
        self._generate()
        lines = self.plan.line_ids.filtered(
            lambda l: l.activity_id == install and l.space_task_id == space)
        self.assertAlmostEqual(sum(lines.mapped('qty_planned')), 1.2)
        # La cocina no recibe la actividad del closet.
        self.assertFalse(self.plan.line_ids.filtered(
            lambda l: l.activity_id == install and l.space_task_id == self.space_501))
        # Árbol de recursos: el ML del ambiente es el total.
        self.assertAlmostEqual(self.plan._tree_space_ml(space)[space.id], 1.2)
