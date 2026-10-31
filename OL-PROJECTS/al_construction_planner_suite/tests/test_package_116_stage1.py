# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 1 · base común.

- M116-01 (CR-19): etapas según el perfil de la obra, sin cambiar el código
  guardado; las ayudas de etapa reciben la obra (C-02) y «Generar plan» toma
  las etapas del perfil (C-03).
- CR-23: «Reemplazar lo generado» no duplica las líneas copiadas por «Nueva
  versión» y la línea regenerada hereda su línea anterior.
- CR-22 a): el envío reactiva una actividad archivada con el mismo código.
- M116-02: nombres de los estados del ambiente que no son etapas.
- M116-11: APU en cualquier nivel, «Subnivel de obra», «Lleva APU», el nodo
  con APU como ambiente (I-10) y el envío por la ruta de la hoja (I-12)."""
from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.al_construction_planner.models.common import budget_code_levels

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage116Stage1(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Stage = env['construction.stage'].with_context(active_test=False)
        cls.ref = staticmethod(lambda xmlid: env.ref('al_construction_planner.%s' % xmlid))
        cls.works = Stage.search([('code', 'like', 'works_%')])
        cls.furniture_profile = cls.ref('profile_furniture')
        cls.works_profile = env['construction.vertical.profile'].create({
            'name': 'Construcción (test 1.16)', 'code': 'works_test_116',
            'level_template_id': cls.ref('level_template_works').id,
            'stage_ids': [Command.set(cls.works.ids)],
            'default_stage_id': cls.ref('stage_works_execution').id,
            'feature_measurement': False,
        })
        # Plantilla PROF 4 de prueba: el APU en cualquier nivel.
        cls.prof4 = env['construction.level.template'].create({
            'name': 'PROF 4 (test 1.16)', 'apu_any_level': True, 'line_ids': [
                Command.create({'sequence': 10, 'name': 'Especialidad (N1)', 'role': 'group'}),
                Command.create({'sequence': 20, 'name': 'Sub-especialidad (N2)', 'role': 'group'}),
                Command.create({'sequence': 30, 'name': 'Partida (N3)', 'role': 'space'}),
                Command.create({'sequence': 40, 'name': 'Subpartida 1 (N4)',
                                'role': 'work_sublevel'})]})
        cls.levels = cls.prof4.line_ids.sorted('sequence')
        cls.site = env['project.project'].create({
            'name': 'Obra de construcción (test 1.16)', 'is_construction_site': True,
            'construction_profile_id': cls.works_profile.id,
            'construction_level_template_id': cls.prof4.id})
        if not cls.site.account_id:
            cls.site._create_analytic_account()
        cls.project.construction_profile_id = cls.furniture_profile
        cls.recipe = env['construction.execution.template'].create({
            'code': 'R116', 'name': 'Receta de prueba 1.16', 'uom_id': cls.unit.id,
            'line_ids': [Command.create({
                'resource_type': 'material', 'product_id': cls.p_screw.id, 'qty': 2.0,
                'product_uom_id': cls.unit.id, 'stage': 'works_execution'})]})

    def _node(self, name, depth, parent=None, **vals):
        return self.env['project.task'].create(dict({
            'name': name, 'project_id': self.site.id,
            'construction_level_line_id': self.levels[depth - 1].id,
            'parent_id': parent.id if parent else False}, **vals))

    # ------------------------------------------------------------------
    # M116-01
    # ------------------------------------------------------------------
    def test_stages_offered_by_profile(self):
        Stage = self.env['construction.stage']
        self.assertEqual(set(Stage._offered_codes(self.site)), set(self.works.mapped('code')))
        furniture = set(Stage._offered_codes(self.project))
        self.assertFalse(furniture & set(self.works.mapped('code')))
        self.assertIn('cleaning', furniture, '2.3 Limpieza es del perfil de mobiliario')
        # Sin obra: las activas de todo el catálogo.
        self.assertTrue(set(Stage._offered_codes()) >= furniture)
        # C-02: el consumo sin etapa de la obra de construcción cae en una
        # etapa de construcción; la de mobiliario, en una de mobiliario.
        self.assertIn(Stage._consumption_code('site', self.site), self.works.mapped('code'))
        self.assertNotIn(Stage._consumption_code('site', self.project),
                         self.works.mapped('code'))
        self.assertTrue(set(Stage._field_codes(self.site)) <= set(self.works.mapped('code')))
        self.assertEqual(Stage._default_code(self.site), 'works_execution')

    def test_archived_stage_still_reads(self):
        stage = self.ref('stage_works_finishing')
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': self.env['construction.resource.plan'].create(
                {'project_id': self.site.id}).id,
            'resource_type': 'material', 'product_id': self.p_screw.id, 'qty_planned': 1,
            'product_uom_id': self.unit.id, 'stage': stage.code})
        stage.active = False
        self.env.invalidate_all()
        self.assertEqual(line.stage, stage.code)
        self.assertIn(stage.code, dict(line._fields['stage']._description_selection(self.env)))
        self.assertNotIn(stage.code, line.construction_stage_codes,
                         'archivada: se lee, pero no se ofrece')

    def test_contract_wizard_offers_profile_stages(self):
        plan = self.env['construction.resource.plan'].create({'project_id': self.site.id})
        wizard = self.env['construction.plan.contract.wizard'].new({
            'plan_id': plan.id, 'whole_project': True})
        self.assertEqual(set(wizard.construction_stage_codes),
                         set(self.works.filtered('active').mapped('code')))

    def test_import_rejects_other_profile_stage(self):
        Stage = self.env['construction.stage']
        with self.assertRaises(UserError):
            Stage._check_project_code('assembly', self.site, what='fila 3')
        Stage._check_project_code('works_layout', self.site)
        wizard = self.env['construction.recipe.import.wizard'].create(
            {'project_id': self.site.id})
        self.assertIsNone(wizard._stage_code('1.2 Armado'))
        self.assertEqual(wizard._stage_code(''), 'works_execution')

    def test_generate_plan_takes_profile_stages(self):
        wizard = self._wizard()
        self.assertIn('cleaning', wizard.stage_ids.mapped('code'),
                      '«Generar plan» de mobiliario ya no descarta 2.3 Limpieza')
        self.assertFalse(set(wizard.stage_ids.mapped('code')) & set(self.works.mapped('code')))

    # ------------------------------------------------------------------
    # CR-23 y CR-22 a)
    # ------------------------------------------------------------------
    def test_new_version_does_not_duplicate_recipe_lines(self):
        partida = self._node('1 Arquitectura', 1)
        sub = self._node('1.01 Muros', 2, partida)
        apu = self._node('1.01.01 Muro', 3, sub, construction_execution_template_id=self.recipe.id,
                         construction_qty=10.0)
        plan = self.env['construction.resource.plan'].create({'project_id': self.site.id})
        Wizard = self.env['construction.plan.recipe.wizard']
        Wizard.create({'plan_id': plan.id}).action_generate()
        manual = self.env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'task_id': apu.id, 'resource_type': 'material',
            'product_id': self.p_cap.id, 'qty_planned': 3, 'product_uom_id': self.unit.id,
            'stage': 'works_execution', 'price_unit_planned': 1.0})
        plan.line_ids.price_unit_planned = 1.0
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        action = self.env['construction.plan.replan.wizard'].create(
            {'plan_id': plan.id, 'reason': 'Cambio de receta (test)'}).action_create_version()
        version = self.env['construction.resource.plan'].browse(action['res_id'])
        self.assertEqual(len(version.line_ids), 2)
        Wizard.create({'plan_id': version.id, 'mode': 'replace'}).action_generate()
        screws = version.line_ids.filtered(lambda l: l.product_id == self.p_screw)
        self.assertEqual(len(screws), 1, 'una sola línea por recurso, partida y etapa')
        self.assertEqual(screws.source, 'recipe')
        self.assertEqual(screws.previous_line_id.plan_id, plan,
                         'hereda la línea anterior: las asignaciones pasan a ella')
        kept = version.line_ids.filtered(lambda l: l.product_id == self.p_cap)
        self.assertEqual(kept.previous_line_id, manual, 'la línea manual se conserva')

    def test_archived_activity_is_reactivated(self):
        Activity = self.env['construction.labor.activity']
        activity = Activity.create({
            'code': 'SER-116', 'name': 'Eliminación de desmonte (test)', 'stage': 'assembly',
            'uom_id': self.unit.id})
        activity.active = False
        found = Activity._construction_get_by_code('SER-116', self.env.company, self.site)
        self.assertEqual(found, activity)
        self.assertTrue(activity.active)
        self.assertEqual(activity.stage, 'works_execution',
                         'su etapa de otro perfil pasa a la por defecto del perfil')

    # ------------------------------------------------------------------
    # M116-02
    # ------------------------------------------------------------------
    def test_space_state_labels(self):
        labels = self.project._construction_space_state_labels()
        self.assertEqual(labels['measured'], 'Medido')
        self.assertEqual(self.site._construction_space_state_labels(), {},
                         'construcción por partidas no usa Pendiente, Medido ni Entregado')
        self.env.company.construction_state_measured_label = 'Relevado'
        self.assertEqual(self.project._construction_space_state_labels()['measured'], 'Relevado')

    # ------------------------------------------------------------------
    # M116-11
    # ------------------------------------------------------------------
    def test_budget_code_levels(self):
        self.assertEqual(budget_code_levels('13.0102'), ['13', '13.01', '13.0102'])
        self.assertEqual(budget_code_levels('1.02.01.01'),
                         ['1', '1.02', '1.02.01', '1.02.01.01'])
        self.assertEqual(budget_code_levels(''), [])

    def test_template_rules(self):
        Template = self.env['construction.level.template']
        with self.assertRaises(ValidationError):
            Template.create({'name': 'Sin APU libre (test)', 'line_ids': [
                Command.create({'sequence': 1, 'name': 'Partida', 'role': 'space'}),
                Command.create({'sequence': 2, 'name': 'Subpartida', 'role': 'work_sublevel'})]})
        # La validación corre también al crear un nivel suelto.
        with self.assertRaises(ValidationError):
            self.env['construction.level.template.line'].create({
                'template_id': self.prof4.id, 'sequence': 50, 'name': 'Detalle',
                'role': 'module'})
        with self.assertRaises(ValidationError):
            Template.create({'name': 'Siete niveles (test)', 'apu_any_level': True,
                             'line_ids': [Command.create({'sequence': 1, 'name': 'N1',
                                                          'role': 'group'}),
                                          Command.create({'sequence': 2, 'name': 'N2',
                                                          'role': 'space'})] + [
                Command.create({'sequence': 10 + n, 'name': 'S%s' % n, 'role': 'work_sublevel'})
                for n in range(5)]})

    def test_apu_at_any_level(self):
        spec = self._node('1 Movilización', 1)
        sub = self._node('1.01 Obras provisionales', 2, spec)
        partida = self._node('1.01.01 Trazo y replanteo', 3, sub)
        apu = self._node('1.01.01.01 Trazo y replanteo', 4, partida,
                         construction_execution_template_id=self.recipe.id, construction_qty=5)
        self.assertTrue(apu.construction_has_apu)
        self.assertFalse(partida.construction_has_apu, 'la partida sin APU solo agrupa')
        self.assertEqual(apu.construction_space_task_id, apu, 'I-10: el ambiente es el nodo con APU')
        # Una sub-especialidad con APU (096-26: «1.01 ARQUITECTURA (DETALLES)»).
        detail = self._node('1.02 Detalles', 2, spec, construction_has_apu=True)
        self.assertEqual(detail.construction_space_task_id, detail)
        SpaceStage = self.env['construction.space.stage']
        dates = {'date_start': '2026-11-02', 'date_end': '2026-11-06'}
        SpaceStage.create(dict(dates, space_task_id=apu.id, stage='works_execution'))
        with self.assertRaises(ValidationError):
            SpaceStage.create(dict(dates, space_task_id=partida.id, stage='works_execution'))
        with self.assertRaises(ValidationError):
            partida.construction_has_apu = True

    def test_send_by_path_and_too_deep(self):
        customer = self.env['res.partner'].create({'name': 'Cliente 1.16 (test)'})
        order = self.env['sale.order'].create({'partner_id': customer.id,
                                               'project_id': self.site.id})
        product = self.env['product.product'].create({'name': 'Partida (test 1.16)',
                                                      'type': 'service'})

        def line(item, name, path):
            return self.env['sale.order.line'].create({
                'order_id': order.id, 'product_id': product.id, 'name': '%s %s' % (item, name),
                'product_uom_qty': 1, 'construction_budget_item': item,
                'construction_budget_path': path})

        line('1.01.01', 'Movilización', [['1', 'Obras provisionales'], ['1.01', 'Generales']])
        line('1.02.01.01', 'Trazo', [['1', 'Obras provisionales'], ['1.02', 'Trazos'],
                                     ['1.02.01', 'Trazo y replanteo']])
        line('2.01', 'Detalles', [['2', 'Arquitectura']])
        order.action_construction_create_levels()
        Task = self.env['project.task']
        apus = Task.search([('project_id', '=', self.site.id),
                            ('construction_has_apu', '=', True)])
        self.assertEqual(len(apus), 3)
        depth = {task.name: task.construction_level_line_id for task in apus}
        self.assertEqual(depth['1.01.01 Movilización'], self.levels[2])
        self.assertEqual(depth['1.02.01.01 Trazo'], self.levels[3])
        self.assertEqual(depth['2.01 Detalles'], self.levels[1])
        title = Task.search([('project_id', '=', self.site.id),
                             ('name', '=', '1.02.01 Trazo y replanteo')])
        self.assertFalse(title.construction_has_apu)
        # Una fila de nivel 5 en una obra PROF 4 detiene el envío.
        line('1.02.01.01.01', 'Demasiado hondo', [['1', 'a'], ['1.02', 'b'], ['1.02.01', 'c'],
                                                  ['1.02.01.01', 'd']])
        with self.assertRaises(UserError):
            order.action_construction_create_levels()

    def test_depth_profiles_are_idempotent(self):
        Profile = self.env['construction.vertical.profile'].with_context(active_test=False)
        Profile._construction_ensure_depth_profiles()
        count = Profile.search_count([])
        Profile._construction_ensure_depth_profiles()
        self.assertEqual(Profile.search_count([]), count)
        prof6 = self.env.ref('al_construction_planner.profile_construction_prof6')
        self.assertTrue(prof6.level_template_id.apu_any_level)
        self.assertEqual(len(prof6.level_template_id.line_ids), 6)
