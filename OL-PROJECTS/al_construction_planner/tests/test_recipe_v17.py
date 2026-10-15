# -*- coding: utf-8 -*-
"""Receta independiente del mueble (v1.7, M17-04).

La partida «Muro drywall RF» (ARQ-03.02.01) genera su plan desde su Work
Item, con material, mano de obra y equipo, sin crear una tipología de
mueble. El APU es el de ``construccion_dev_1``: 11 materiales, 3 líneas de
mano de obra y 1 equipo por m².
"""
import base64
from io import BytesIO

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import float_round

from .test_levels_v17 import TestFreeLevels

# (código, naturaleza, cantidad por m², costo): Work Item 19 de construccion_dev_1.
DRYWALL_APU = [
    ('EQ-0014', 'equipment', 1.0, 2.36),
    ('MAT-0080', 'material', 0.055, 33.00),
    ('MAT-0267', 'material', 0.064, 38.92),
    ('MAT-0266', 'material', 0.032, 47.36),
    ('MAT-0126', 'material', 0.09, 24.40),
    ('MAT-0073', 'material', 0.021, 13.76),
    ('MAT-0255', 'material', 0.927, 0.20),
    ('MAT-0171', 'material', 0.894, 16.82),
    ('MAT-0231', 'material', 0.861, 11.25),
    ('MAT-0117', 'material', 1.358, 6.10),
    ('MAT-0172', 'material', 0.164, 36.00),
    ('MAT-0202', 'material', 0.686, 44.32),
    ('MO-0002', 'labour', 0.0421052631578947, 34.07),
    ('MO-0005', 'labour', 0.842105263157895, 28.39),
    ('MO-0006', 'labour', 0.421052631578947, 20.22),
]


@tagged('post_install', '-at_install')
class TestRecipe(TestFreeLevels):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hour = cls.env.ref('uom.product_uom_hour')
        Product = cls.env['product.product']
        cls.apu_products = {}
        for code, nature, _qty, cost in DRYWALL_APU:
            cls.apu_products[code] = Product.create({
                'name': 'Recurso %s (test)' % code, 'default_code': 'T17-%s' % code,
                'type': 'service' if nature != 'material' else 'consu',
                'uom_id': (cls.hour if nature == 'labour' else cls.unit).id,
                'standard_price': cost})
        cls.partida_product = Product.create({
            'name': 'Muro drywall RF (test)', 'default_code': 'T17-ARQ-03.02.01',
            'type': 'service', 'uom_id': cls.m2.id})
        cls.wizard = cls.env['construction.recipe.import.wizard'].create({
            'source': 'work_item', 'default_stage_id': cls.board.id})

    def _work_items(self):
        return [{
            'ref': 'ARQ-03.02.01', 'name': 'Muro de drywall RF a dos caras', 'uom': self.m2,
            'product': self.partida_product, 'source_ref': 'x_work_item,19',
            'lines': [{'product': self.apu_products[code], 'qty': qty, 'cost': cost,
                       'nature': nature, 'uom': self.apu_products[code].uom_id}
                      for code, nature, qty, cost in DRYWALL_APU],
        }]

    def _copy_work_items(self, wizard=None):
        wizard = wizard or self.wizard
        recipes, refs = wizard._recipes_from_work_items(self._work_items())
        return wizard._upsert_recipes(recipes, 'work_item', refs)

    def test_recipe_from_work_item(self):
        templates, created, _updated = self._copy_work_items()
        self.assertEqual(created, 1)
        recipe = templates
        self.assertEqual((recipe.code, recipe.uom_id, recipe.source, recipe.source_ref),
                         ('ARQ-03.02.01', self.m2, 'work_item', 'x_work_item,19'))
        behaviors = recipe.line_ids.mapped('resource_type')
        self.assertEqual((behaviors.count('material'), behaviors.count('labor'),
                          behaviors.count('equipment')), (11, 3, 1))
        labor = recipe.line_ids.filtered(lambda l: l.resource_type == 'labor')
        self.assertEqual(labor.activity_id.mapped('code'),
                         ['T17-MO-0002', 'T17-MO-0005', 'T17-MO-0006'])
        self.assertEqual(set(labor.activity_id.mapped('uom_id')), {self.hour})
        # Cada línea redondeada a la moneda (mitad hacia arriba), como en la receta.
        expected = sum(float_round(qty * cost, 2) for _code, _nature, qty, cost in DRYWALL_APU)
        self.assertAlmostEqual(recipe.amount_unit, expected, places=2)
        # Volver a copiar no duplica la receta ni las actividades.
        _templates, created, updated = self._copy_work_items()
        self.assertEqual((created, updated), (0, 1))
        self.assertEqual(len(recipe.line_ids), 15)
        self.assertEqual(self.env['construction.labor.activity'].search_count(
            [('code', 'like', 'T17-MO-')]), 3)

    def test_plan_from_recipe_without_typology(self):
        recipe = self._copy_work_items()[0]
        self.drywall.write({'construction_execution_template_id': recipe.id,
                            'construction_qty': 120.0})
        typologies = self.env['construction.typology'].search_count([])
        wizard = self.env['construction.plan.recipe.wizard'].create({
            'plan_id': self.plan_site.id, 'task_ids': [(6, 0, self.drywall.ids)]})
        self.assertIn('15 líneas en 1 niveles', wizard.preview_html)
        wizard.action_generate()
        lines = self.plan_site.line_ids.filtered(lambda l: l.source == 'recipe')
        self.assertEqual(len(lines), 15)
        self.assertEqual(set(lines.task_id), {self.drywall})
        self.assertEqual(set(lines.mapped('resource_type')), {'material', 'labor', 'equipment'})
        self.assertEqual(set(lines.mapped('stage')), {'test17_board'})
        operario = lines.filtered(lambda l: l.activity_id.code == 'T17-MO-0005')
        self.assertAlmostEqual(operario.qty_planned, 0.842105263157895 * 120, places=2)
        self.assertEqual(operario.product_uom_id, self.hour)
        # La cantidad del plan va a 2 decimales y cada monto a la moneda.
        self.assertAlmostEqual(sum(lines.mapped('amount_planned')), sum(
            float_round(float_round(qty * 120, 2) * cost, 2) for _c, _n, qty, cost in DRYWALL_APU), places=2)
        self.assertEqual(self.env['construction.typology'].search_count([]), typologies)
        # Regenerar reemplaza lo generado desde la receta y conserva lo manual.
        manual = self.plan_site.line_ids.filtered(lambda l: l.source == 'manual')
        self.drywall.construction_qty = 60.0
        self.env['construction.plan.recipe.wizard'].create({
            'plan_id': self.plan_site.id, 'task_ids': [(6, 0, self.drywall.ids)],
        }).action_generate()
        lines = self.plan_site.line_ids.filtered(lambda l: l.source == 'recipe')
        self.assertEqual(len(lines), 15)
        self.assertAlmostEqual(sum(lines.mapped('amount_planned')), sum(
            float_round(float_round(qty * 60, 2) * cost, 2) for _c, _n, qty, cost in DRYWALL_APU), places=2)
        self.assertEqual(self.plan_site.line_ids.filtered(lambda l: l.source == 'manual'), manual)

    def test_labor_as_contract(self):
        wizard = self.env['construction.recipe.import.wizard'].create({
            'source': 'work_item', 'labor_behavior': 'contract',
            'default_stage_id': self.board.id})
        recipe = self._copy_work_items(wizard)[0]
        self.assertEqual(recipe.line_ids.filtered('activity_id').mapped('resource_type'),
                         ['contract'] * 3)

    def test_work_items_need_the_construction_package(self):
        if 'x_work_item' in self.env:
            self.skipTest('La base tiene el paquete Construction.')
        with self.assertRaises(UserError):
            self.wizard._read_work_items()

    def _workbook(self, recipes, levels):
        from openpyxl import Workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'RECETAS'
        sheet.append(['Código de la receta', 'Nombre de la receta', 'Unidad de la receta',
                      'Tipo de recurso', 'Código del recurso', 'Cantidad por unidad', 'Etapa',
                      'Costo unitario'])
        for row in recipes:
            sheet.append(row)
        sheet = workbook.create_sheet('NIVELES')
        sheet.append(['Disciplina', 'Subpartida', 'Partida', 'Actividad', 'Receta', 'Metrado'])
        for row in levels:
            sheet.append(row)
        output = BytesIO()
        workbook.save(output)
        return base64.b64encode(output.getvalue())

    def test_excel_recipes_and_levels(self):
        file = self._workbook(
            [('PIN-01', 'Pintura látex dos manos', 'm2', 'Material', 'T17-MAT-0080', 0.12,
              'Masillado (test)', 33.0),
             ('PIN-01', None, None, 'equipment', 'T17-EQ-0014', 0.5, 'test17_putty', None)],
            [('ARQ Arquitectura', 'ARQ-05 Pintura', 'ARQ-05.02.01 Pintura esmalte', None,
              'PIN-01', 80),
             ('MEC Mecánicas', 'MEC-01 Ductos', 'MEC-01.01.01 Ducto', 'Tramo 1', None, None)])
        wizard = self.env['construction.recipe.import.wizard'].create({
            'source': 'excel', 'project_id': self.site.id, 'file': file,
            'filename': 'pintura.xlsx'})
        wizard.action_import()
        recipe = self.env['construction.execution.template'].search([('code', '=', 'PIN-01')])
        self.assertEqual((recipe.uom_id, recipe.source, len(recipe.line_ids)),
                         (self.m2, 'excel', 2))
        self.assertEqual(recipe.line_ids.mapped('stage'), ['test17_putty', 'test17_putty'])
        partida = self.env['project.task'].search([
            ('project_id', '=', self.site.id), ('name', '=', 'ARQ-05.02.01 Pintura esmalte')])
        # Bajo la disciplina y la subpartida que ya existían.
        self.assertEqual(partida.parent_id, self.paint)
        self.assertEqual(partida.construction_level_line_id, self.levels['Partida'])
        self.assertEqual((partida.construction_execution_template_id, partida.construction_qty),
                         (recipe, 80.0))
        tramo = self.env['project.task'].search([
            ('project_id', '=', self.site.id), ('name', '=', 'Tramo 1')])
        self.assertEqual(tramo.construction_level, 'module')
        self.assertEqual(tramo.parent_id.parent_id.parent_id.name, 'MEC Mecánicas')
        tasks = self.env['project.task'].search_count([('project_id', '=', self.site.id)])
        wizard.action_import()
        self.assertEqual(self.env['project.task'].search_count(
            [('project_id', '=', self.site.id)]), tasks)
        self.assertEqual(len(recipe.line_ids), 2)


# Solo las pruebas propias: las de TestFreeLevels ya corren en su clase.
for _name in dir(TestFreeLevels):
    if _name.startswith('test_') and _name not in vars(TestRecipe):
        setattr(TestRecipe, _name, None)
