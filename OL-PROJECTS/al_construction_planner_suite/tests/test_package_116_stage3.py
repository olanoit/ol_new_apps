# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 3 · bloque 3a: barra, panel y nombres largos.

- M115-01: el botón de la barra toma el nombre de su acción.
- M115-02: cada botón trae su grupo (Programar, Ejecutar).
- M115-03: el panel ampliado trae ejecutado y saldo en soles, solo para
  quien ve montos.
- M116-08 / CR-25: ancho máximo de los nombres por compañía, en la sesión.
- CR-26: con Fabricación, las ayudas nombran la orden de fabricación; el
  núcleo habla de producción en taller."""
import base64

from odoo import Command
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_planner.models import construction_stage as core_stage
from odoo.addons.al_construction_planner.models import construction_resource_plan as core_plan

from .common import PlannerCommon

PURCHASE = 'al_construction_planner_purchase.action_plan_purchase_wizard'
REQUEST = 'al_construction_planner_purchase.action_plan_request_wizard'
PRODUCTION = 'al_construction_planner_mrp.action_plan_production_wizard'
CONTRACT = 'al_construction_planner_subcontract.action_plan_contract_wizard'
PROGRESS = 'al_construction_planner.action_plan_progress_wizard'


@tagged('post_install', '-at_install')
class TestPackage116Stage3a(PlannerCommon):

    def _actions(self, user=None):
        Plan = self.env['construction.resource.plan']
        return {action['xmlid']: action
                for action in (Plan.with_user(user) if user else Plan).get_tree_actions()}

    # ------------------------------------------------------------------
    # M115-01 y M115-02
    # ------------------------------------------------------------------
    def test_button_names_from_action(self):
        actions = self._actions(self.planner)
        self.assertEqual(actions[PURCHASE]['name'], 'Programar compra masiva')
        self.assertEqual(actions[REQUEST]['name'], 'Requerimiento de materiales para obra')
        self.assertEqual(actions[PRODUCTION]['name'], 'Requerimiento de fabricación')
        self.assertEqual(actions[CONTRACT]['name'], 'Asignar contrata')
        # El nombre se cambia en la base, sin tocar código.
        self.env.ref(CONTRACT).name = 'Encargar a una contrata'
        self.assertEqual(self._actions(self.planner)[CONTRACT]['name'], 'Encargar a una contrata')

    def test_button_groups(self):
        actions = self._actions(self.planner)
        self.assertEqual({actions[x]['group'] for x in (PURCHASE, REQUEST, PRODUCTION)},
                         {'program'})
        self.assertEqual(actions[CONTRACT]['group'], 'execute')
        self.assertEqual(actions[PURCHASE]['group_label'], 'Programar')
        self.assertEqual(actions[CONTRACT]['group_label'], 'Ejecutar')
        groups = self.env['construction.resource.plan'].get_tree_action_groups()
        self.assertEqual([key for key, _label in groups], ['consult', 'program', 'execute'])
        # Quien no tiene el grupo de avance no recibe «Registrar avance».
        progress_group = self.env['res.groups'].create({'name': 'Avance 1.16 (test)'})
        self.env.ref(PROGRESS).group_ids = progress_group
        user = new_test_user(self.env, 'plan_sin_avance_116', name='Sin avance (test)',
                             groups='al_construction_planner.group_planner_user')
        self.assertNotIn(PROGRESS, self._actions(user))
        self.assertIn(CONTRACT, self._actions(user))

    # ------------------------------------------------------------------
    # M115-03
    # ------------------------------------------------------------------
    def test_panel_executed_and_balance(self):
        self.space_501.construction_typology_id = self.typology
        self._generate_and_approve()
        line = self.plan.line_ids.filtered(
            lambda l: l.resource_type == 'contract' and l.activity_id == self.act_screw)[:1]
        self.assertTrue(line)
        photo = self.env['ir.attachment'].create({'name': 'foto.png',
                                                  'datas': base64.b64encode(b'x')})
        progress = self.env['construction.task.progress'].create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
            'plan_line_id': line.id, 'qty': line.qty_planned / 2,
            'attachment_ids': [Command.set(photo.ids)]})
        progress.with_user(self.planner).action_validate()
        self.assertEqual(progress.state, 'validated')
        summary = self.plan.with_user(self.planner).get_selection_summary(['p'])
        screw = next(r for r in summary['resources']
                     if r['resource_type'] == 'contract' and r['name'] == self.act_screw.display_name)
        self.assertAlmostEqual(screw['amount_executed'], progress.amount, places=2)
        self.assertAlmostEqual(screw['amount_balance'], screw['amount'] - progress.amount, places=2)
        material = next(r for r in summary['resources'] if r['resource_type'] == 'material')
        self.assertIs(material['amount_executed'], False)
        self.assertIs(material['amount_balance'], False)
        # Por etapa: el ejecutado de la etapa de la línea.
        group = next(g for g in summary['groups'] if g['resource_type'] == 'contract')
        stage_rows = [r for s in group['stages'] for r in s['resources']
                      if r['name'] == self.act_screw.display_name]
        self.assertAlmostEqual(sum(r['amount_executed'] for r in stage_rows), progress.amount, 2)
        # Sin el grupo de montos no hay soles.
        viewer = new_test_user(self.env, 'plan_consulta_116', name='Consulta (test)',
                               groups='al_construction_planner.group_planner_user')
        masked = self.plan.with_user(viewer).get_selection_summary(['p'])
        self.assertTrue(all(r['amount_executed'] is False and r['amount_balance'] is False
                            for r in masked['resources']))

    # ------------------------------------------------------------------
    # M116-08 / CR-25
    # ------------------------------------------------------------------
    def test_name_max_width(self):
        self.assertEqual(self.company.construction_name_max_width, 360)
        # La interfaz la recibe con la sesión (ir.http.session_info, que
        # necesita una petición: se prueba en la interfaz).
        self.assertIn('construction_name_max_width',
                      self.env['res.config.settings']._fields)
        # Las vistas dinámicas del plan (Análisis de control) llevan la clase común.
        pivots = self.env['ir.ui.view'].search([
            ('type', '=', 'pivot'), ('model', '=', 'construction.resource.plan.line')])
        self.assertTrue(pivots)
        for view in pivots:
            self.assertIn('o_cp_wrap_names', view.arch_db)

    # ------------------------------------------------------------------
    # CR-26
    # ------------------------------------------------------------------
    def test_manufacturing_texts(self):
        # Núcleo: producción en taller, sin la orden de fabricación.
        core_texts = [
            core_stage.ConstructionStage.kind._args__['help'],
            core_stage.ConstructionStage.production_consumption._args__['string'],
            core_stage.ConstructionStage.production_consumption._args__['help'],
            core_stage.ConstructionResourceType.behavior._args__['help'],
        ]
        line_class = core_plan.ConstructionResourcePlanLine
        core_texts += [getattr(line_class, name)._args__['help']
                       for name in ('qty_requested', 'qty_dispatched', 'qty_consumed')]
        for text in core_texts:
            self.assertNotIn('fabricación', text.replace('Fabricación:', ''))
            self.assertNotIn(' OF', text)
            self.assertNotIn('planta', text)
        # Con el puente de Fabricación, las ayudas la nombran.
        Stage = self.env['construction.stage']
        self.assertEqual(Stage._fields['production_consumption'].string,
                         'Consume en la orden de fabricación')
        self.assertIn('orden de fabricación', Stage._fields['kind'].help)
        self.assertIn('órdenes de fabricación',
                      self.env['construction.resource.plan.line']._fields['qty_requested'].help)
