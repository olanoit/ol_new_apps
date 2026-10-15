# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestGenerate(PlannerCommon):

    def _lines(self, **filters):
        lines = self.plan.line_ids
        for field, value in filters.items():
            lines = lines.filtered(lambda l, f=field, v=value: l[f] == v)
        return lines

    def _modules(self, space):
        return self.env['project.task'].search([
            ('parent_id', '=', space.id), ('construction_level', '=', 'module')])

    def test_preview(self):
        wizard = self._wizard()
        data = wizard._collect()
        self.assertEqual(len(data['modules_to_create']), 14)
        kinds = data['line_kinds']
        self.assertEqual(kinds['assembly_module'][0], 14)
        self.assertAlmostEqual(kinds['assembly_module'][1], 108.0)
        self.assertEqual(kinds['contract_space'][0], 8)
        self.assertAlmostEqual(kinds['contract_space'][1], 214.50)
        self.assertEqual(kinds['material_staged'][0], 10)
        self.assertEqual(kinds['material_unstaged'][0], 2)
        self.assertIn('108.00', wizard.preview_html)
        # Advertencias no bloqueantes: sin etapa, sin costo y ML en el ambiente.
        self.assertIn('2 líneas de material sin etapa', wizard.warning_html)
        self.assertIn('12 líneas sin costo', wizard.warning_html)
        self.assertIn('Cocina 01', wizard.warning_html)
        self.assertFalse(self._modules(self.space_501), 'La vista previa no crea nada')

    def test_generate_space_501(self):
        """Dpto 501 (tipología 01): 7 módulos con su armado (S/ 54.00) y las
        actividades por ambiente; los materiales cuelgan del ambiente."""
        self._generate(space_task_ids=[(6, 0, self.space_501.ids)])
        modules = self._modules(self.space_501)
        self.assertEqual(len(modules), 7)
        self.assertEqual(set(modules.mapped('construction_unit_state')), {'planned'})
        self.assertEqual(sorted(modules.mapped('construction_module_code')), sorted(
            self.typology.module_line_ids.mapped('code')))
        assembly = self._lines(resource_type='contract', task_level='module')
        self.assertEqual(len(assembly), 7)
        self.assertEqual(assembly.module_task_id, modules)
        self.assertAlmostEqual(sum(assembly.mapped('amount_planned')), 54.0)
        space_contract = self._lines(resource_type='contract', task_id=self.space_501)
        self.assertAlmostEqual(sum(space_contract.mapped('amount_planned')), 107.25)
        install_low = space_contract.filtered(lambda l: l.activity_id == self.act_inst_low)
        self.assertEqual((install_low.qty_planned, install_low.price_unit_planned), (2.12, 18.0))
        self.assertEqual(install_low.stage, 'installation')
        materials = self._lines(resource_type='material')
        self.assertEqual(len(materials), 6)
        self.assertEqual(materials.task_id, self.space_501)
        self.assertEqual(materials.filtered(lambda l: not l.stage).product_id, self.p_rh)
        self.assertEqual(self.plan.line_count, 17)
        self.assertEqual(self.plan.unstaged_line_count, 1)
        self.assertEqual(self.plan.unpriced_line_count, 6)
        self.assertAlmostEqual(self.plan.amount_contract, 161.25)
        self.assertEqual(self._lines(source='generated'), self.plan.line_ids)
        if self.project.account_id:
            self.assertEqual(materials[0].analytic_distribution,
                             {str(self.project.account_id.id): 100.0})

    def test_regenerate_keeps_modules_and_costs(self):
        self._generate()
        self.assertEqual(self.plan.line_count, 34)
        # El planificador aplica el costo de los materiales (W-12).
        self._lines(product_id=self.p_screw).write({
            'price_unit_planned': 0.05, 'price_basis': 'Última compra'})
        manual = self.env['construction.resource.plan.line'].create({
            'plan_id': self.plan.id, 'task_id': self.apt_501.id, 'resource_type': 'service',
            'stage': 'finishing', 'product_id': self.p_cap.id,
            'product_uom_id': self.unit.id, 'qty_planned': 1, 'price_unit_planned': 50})
        self._generate()
        self.assertEqual(len(self._modules(self.space_501)), 7, 'Sin módulos duplicados')
        self.assertEqual(len(self._modules(self.space_502)), 7)
        self.assertEqual(self.plan.line_count, 35)
        self.assertTrue(manual.exists(), 'Las líneas manuales se conservan')
        screws = self._lines(product_id=self.p_screw)
        self.assertEqual(set(screws.mapped('price_unit_planned')), {0.05})
        self.assertAlmostEqual(sum(screws.mapped('amount_planned')), 2 * 121 * 0.05)
        # Agregar suma líneas sin crear módulos nuevos.
        self._generate(mode='add', space_task_ids=[(6, 0, self.space_502.ids)],
                       include_material=False)
        self.assertEqual(len(self._modules(self.space_502)), 7)
        self.assertEqual(self.plan.line_count, 35 + 11)

    def test_filters_by_stage_and_type(self):
        self._generate(stage_production=False, stage_finishing=False, include_material=True,
                       space_task_ids=[(6, 0, self.space_501.ids)])
        stages = set(self.plan.line_ids.mapped('stage'))
        self.assertNotIn('production', stages)
        self.assertNotIn('finishing', stages)
        # La melamina RH no tiene etapa: entra igual para que se vea la advertencia.
        self.assertIn(False, stages)
        with self.assertRaises(UserError):
            self._generate(stage_production=False, stage_assembly=False,
                           stage_installation=False, stage_finishing=False)

    def test_existing_eto_modules(self):
        """Ambiente con módulos del ETO: no se duplican; el que falta se avisa
        y, con anchos, la instalación por ML baja al módulo."""
        typology = self.typology.copy({'code': '01-ETO'})
        for module, width, group in zip(typology.module_line_ids,
                                        (600, 450, 900, 900, 600, 900, 450),
                                        ('low', 'low', 'high', 'high', 'high', 'none', 'low')):
            module.write({'width_mm': width, 'ml_group': group})
        self.space_502.construction_typology_id = typology
        for code in typology.module_line_ids.mapped('code')[:6]:
            self.task(code, 'module', self.space_502, construction_module_code=code)
        wizard = self._wizard(space_task_ids=[(6, 0, self.space_502.ids)])
        self.assertIn('Cajonera', wizard.warning_html)
        wizard.action_generate()
        self.assertEqual(len(self._modules(self.space_502)), 6)
        install = self._lines(activity_id=self.act_inst_low)
        self.assertEqual(set(install.task_id.mapped('construction_level')), {'module'})
        self.assertAlmostEqual(sum(install.mapped('qty_planned')), 1.05,
                               msg='La cajonera no existe: 600 + 450 mm')
        high = self._lines(activity_id=self.act_inst_high)
        self.assertAlmostEqual(sum(high.mapped('qty_planned')), 2.40)

    def test_space_without_typology(self):
        self.space_502.construction_typology_id = False
        wizard = self._wizard()
        self.assertIn('Ambientes sin tipología', wizard.warning_html)
        wizard.action_generate()
        self.assertFalse(self._lines(space_task_id=self.space_502))

    def test_without_create_modules(self):
        wizard = self._wizard(create_modules=False, space_task_ids=[(6, 0, self.space_501.ids)])
        self.assertIn('Ambientes sin módulos', wizard.warning_html)
