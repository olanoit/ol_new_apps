# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from .common import load_demo


def _approved_demo(env, prefix):
    env['tier.definition'].search([('model', '=', 'construction.resource.plan')]).active = False
    demo = load_demo(env, prefix)
    plan = demo['plan']
    if not plan.project_id.account_id:
        plan.project_id._create_analytic_account()
    plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
    plan.action_request_approval()
    assert plan.state == 'approved', plan.state
    return demo


@tagged('post_install', '-at_install')
class TestSchedule(TransactionCase):
    """Fase 8, cronograma con recursos (P-15): etapas de cada ambiente, capa de
    datos del Gantt heredada, arrastre de etapas con recálculo de la necesidad
    y aviso a Logística, carga semanal y asistentes con la selección.
    Criterios de aceptación 11 y 12 sobre el piso 05 del demo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        demo = _approved_demo(cls.env, 'TEST CRONO')
        cls.plan = demo['plan']
        cls.project = demo['project']
        cls.floor = demo['floor']
        cls.leandro = demo['leandro']
        cls.Stage = cls.env['construction.space.stage']
        cls.spaces = cls.env['project.task'].search([
            ('project_id', '=', cls.project.id), ('construction_level', '=', 'space')])
        cls.planner = new_test_user(
            cls.env, 'plan_crono_planificador', name='Planificador (test)',
            groups='al_construction_planner.group_planner_planner')
        cls.reporter = new_test_user(
            cls.env, 'plan_crono_capataz', name='Capataz (test)',
            groups='al_construction_planner.group_planner_progress')
        cls.env['res.users'].create({
            'name': 'Logística (test)', 'login': 'plan_crono_logistica',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('al_construction_material_request.group_construction_logistics').id,
            ])]})

    def _stage(self, space, stage):
        return self.Stage.search([('space_task_id', '=', space.id), ('stage', '=', stage)])

    def _gantt(self, **options):
        return self.env['al.gantt.data'].with_user(self.planner).get_data(
            [self.project.id], dict({'construction_schedule': True}, **options))

    # ------------------------------------------------------------------
    # Etapas del ambiente
    # ------------------------------------------------------------------
    def test_stages_created_with_the_plan(self):
        self.assertEqual(len(self.spaces), 8)
        stages = self.Stage.search([('project_id', '=', self.project.id)])
        # 8 ambientes × 4 etapas con líneas.
        self.assertEqual(len(stages), 32)
        space = self.spaces[0]
        production = self._stage(space, 'production')
        installation = self._stage(space, 'installation')
        # Sin fechas en el ambiente: desde el inicio del plan, una semana por etapa.
        self.assertEqual(production.date_start, self.plan.date_start)
        self.assertEqual(installation.date_start, self.plan.date_start + timedelta(days=14))
        self.assertEqual(installation.date_end, installation.date_start + timedelta(days=4))
        self.assertEqual(installation.predecessor_id, self._stage(space, 'assembly'))
        self.assertFalse(production.predecessor_id)
        self.assertEqual(installation.partner_id, self.env['res.partner'])
        lines = self.plan.line_ids.filtered(
            lambda l: l.space_task_id == space and l.stage == 'installation')
        self.assertAlmostEqual(installation.amount_planned, sum(lines.mapped('amount_planned')))
        # Una sola por ambiente y etapa; el plan no crea repetidas.
        self.assertFalse(self.Stage._sync_from_plan(self.plan))
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception), self.cr.savepoint():
            self.Stage.create({'space_task_id': space.id, 'stage': 'installation',
                               'date_start': date(2026, 11, 2), 'date_end': date(2026, 11, 6)})
        with self.assertRaises(ValidationError):
            installation.date_end = installation.date_start - timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.Stage.create({'space_task_id': self.floor.id, 'stage': 'production',
                               'date_start': date(2026, 11, 2), 'date_end': date(2026, 11, 6)})

    def test_sync_button_creates_missing_stages(self):
        self._stage(self.spaces[0], 'finishing').unlink()
        action = self.plan.action_sync_space_stages()
        self.assertEqual(action['params']['type'], 'success')
        self.assertTrue(self._stage(self.spaces[0], 'finishing'))
        self.assertEqual(self.plan.action_sync_space_stages()['params']['type'], 'info')

    # ------------------------------------------------------------------
    # Capa de datos del Gantt heredada
    # ------------------------------------------------------------------
    def test_gantt_data_without_option_is_unchanged(self):
        payload = self.env['al.gantt.data'].with_user(self.planner).get_data(
            [self.project.id], {'include_undated': True})
        self.assertNotIn('construction', payload)
        self.assertNotIn('construction_stages', payload)
        self.assertNotIn('construction', payload['tasks'][0])

    def test_gantt_data_stage_rows(self):
        payload = self._gantt()
        levels = {task['construction']['level'] for task in payload['tasks']}
        # Los módulos no se listan: las barras son las etapas.
        self.assertEqual(levels, {'floor', 'apartment', 'space'})
        self.assertEqual(len(payload['tasks']), 1 + 8 + 8)
        self.assertEqual(payload['construction']['plan_id'], self.plan.id)
        floor = next(t for t in payload['tasks'] if t['id'] == self.floor.id)
        self.assertAlmostEqual(floor['construction']['amount'], 8944.44)
        self.assertEqual(floor['construction']['progress'], 0.0)
        self.assertEqual(len(payload['construction_stages']), 32)
        # Producción → Armado → Instalación → Acabado en cada ambiente.
        self.assertEqual(len(payload['construction_stage_links']), 8 * 3)
        row = next(r for r in payload['construction_stages'] if r['stage'] == 'installation')
        self.assertTrue(row['unassigned'])
        self.assertTrue(row['editable'])
        self.assertEqual(row['name'], 'Instalación')
        # La producción es solo material: no necesita contrata ni cuadrilla.
        production = next(r for r in payload['construction_stages'] if r['stage'] == 'production')
        self.assertFalse(production['unassigned'])
        # Pisos, departamentos y ambientes sin fechas toman las de sus etapas.
        self.assertEqual(payload['meta']['undated_count'], 0)

        # Solo una etapa: filas y montos de esa etapa.
        payload = self._gantt(construction_stage='installation')
        self.assertEqual({r['stage'] for r in payload['construction_stages']}, {'installation'})
        floor = next(t for t in payload['tasks'] if t['id'] == self.floor.id)
        installation = self.plan.line_ids.filtered(lambda l: l.stage == 'installation')
        self.assertAlmostEqual(floor['construction']['amount'],
                               round(sum(installation.mapped('amount_planned')), 2))

    def test_gantt_data_task_rows(self):
        self.env['project.task'].search([
            ('project_id', '=', self.project.id),
            ('construction_level', '=', 'module')]).date_deadline = '2026-11-20 12:00:00'
        payload = self._gantt(construction_rows='tasks')
        modules = [t for t in payload['tasks'] if t['construction'].get('level') == 'module']
        self.assertEqual(len(modules), 66)
        self.assertEqual(modules[0]['construction']['unit_state'], 'Planificado')
        self.assertFalse(payload['construction_stages'])

    def test_assigned_stage_shows_contract_and_alerts(self):
        self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.floor.ids,
        ).create({'stage': 'installation', 'partner_id': self.leandro.id,
                  'date_start': date(2026, 10, 26)}).action_assign()
        stage = self._stage(self.spaces[0], 'installation')
        self.assertEqual(stage.partner_id, self.leandro)
        payload = self._gantt()
        row = next(r for r in payload['construction_stages'] if r['id'] == stage.id)
        self.assertEqual(row['partner_name'], self.leandro.display_name)
        self.assertFalse(row['unassigned'])
        floor = next(t for t in payload['tasks'] if t['id'] == self.floor.id)
        self.assertIn(self.leandro.display_name, floor['construction']['partners'])
        # Una etapa sin contrata que empieza en menos de dos semanas es alerta.
        finishing = self._stage(self.spaces[0], 'finishing')
        today = date.today()
        finishing.with_context(construction_stage_keep_lines=True).write(
            {'date_start': today + timedelta(days=3), 'date_end': today + timedelta(days=7)})
        row = next(r for r in self._gantt()['construction_stages'] if r['id'] == finishing.id)
        self.assertTrue(row['alerts'])

    # ------------------------------------------------------------------
    # Arrastrar etapas (criterio 12)
    # ------------------------------------------------------------------
    def _request_for_floor(self):
        wizard = self.env['construction.plan.request.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.floor.ids,
        ).create({'group_by': 'floor'})
        return self.env['construction.material.request'].browse(
            wizard.action_create()['res_id'])

    def test_drag_installation_shifts_need_and_warns_logistics(self):
        request = self._request_for_floor()
        installation = self.plan.line_ids.filtered(lambda l: l.stage == 'installation')
        others = self.plan.line_ids - installation
        old = {line.id: line.date_needed for line in self.plan.line_ids}
        request.date_required = min(old[line.id] for line in installation)
        stages = self.Stage.search([('project_id', '=', self.project.id),
                                    ('stage', '=', 'installation')])
        self.assertEqual(len(stages), 8)
        notified = []
        for stage in stages:
            result = stage.with_user(self.planner).action_gantt_reschedule(
                stage.date_start + timedelta(days=7), stage.date_end + timedelta(days=7))
            notified += result['notified']
            self.assertEqual(result['stages'][0]['id'], stage.id)
        for line in installation:
            self.assertEqual(line.date_needed, old[line.id] + timedelta(days=7))
        for line in others:
            self.assertEqual(line.date_needed, old[line.id])
        # El requerimiento queda con fecha anterior a la nueva necesidad: un
        # solo aviso a Logística, aunque se arrastraron 8 etapas.
        self.assertIn(request.display_name, notified)
        activity = request.activity_ids
        self.assertEqual(len(activity), 1)
        self.assertIn('postergó 7 días', activity.note)
        self.assertTrue(self.plan.message_ids.filtered(
            lambda m: 'movida 7 días en el cronograma' in (m.body or '')))

    def test_drag_with_chain_pushes_next_stages(self):
        space = self.spaces[0]
        assembly = self._stage(space, 'assembly')
        installation = self._stage(space, 'installation')
        finishing = self._stage(space, 'finishing')
        old_installation = installation.date_start
        lines = self.plan.line_ids.filtered(
            lambda l: l.space_task_id == space and l.stage == 'installation')
        old_need = {line.id: line.date_needed for line in lines}
        result = assembly.action_gantt_reschedule(
            assembly.date_start + timedelta(days=7), assembly.date_end + timedelta(days=7),
            chain=True)
        self.assertEqual(len(result['stages']), 3)
        # La instalación empieza el lunes siguiente al fin del armado.
        self.assertEqual(installation.date_start, old_installation + timedelta(days=7))
        self.assertEqual(installation.date_start.weekday(), 0)
        self.assertGreater(finishing.date_start, installation.date_end)
        for line in lines:
            self.assertEqual(line.date_needed, old_need[line.id] + timedelta(days=7))
        # Sin cadena solo se mueve la etapa arrastrada.
        result = assembly.action_gantt_reschedule(
            assembly.date_start + timedelta(days=7), assembly.date_end + timedelta(days=7))
        self.assertEqual(len(result['stages']), 1)

    def test_reporter_cannot_move_stages(self):
        stage = self._stage(self.spaces[0], 'installation')
        with self.assertRaises(AccessError):
            stage.with_user(self.reporter).action_gantt_reschedule(
                stage.date_start + timedelta(days=7), stage.date_end + timedelta(days=7))

    def test_reschedule_wizard_moves_stages(self):
        stages = self.Stage.search([('project_id', '=', self.project.id),
                                    ('stage', '=', 'installation')])
        before = {stage.id: stage.date_start for stage in stages}
        assembly = self._stage(self.spaces[0], 'assembly')
        assembly_start = assembly.date_start
        wizard = self.env['construction.plan.reschedule.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.floor.ids,
            construction_selection_stages=['installation'],
        ).create({'mode': 'shift', 'days': 14})
        self.assertFalse(wizard.stage_assembly)
        self.assertTrue(wizard.stage_installation)
        wizard.action_apply()
        for stage in stages:
            self.assertEqual(stage.date_start, before[stage.id] + timedelta(days=14))
        self.assertEqual(assembly.date_start, assembly_start)

    # ------------------------------------------------------------------
    # Asistentes con la selección del cronograma (criterio 11)
    # ------------------------------------------------------------------
    def test_contract_wizard_from_schedule_selection(self):
        Wizard = self.env['construction.plan.contract.wizard'].with_user(self.planner)
        # Marcar el piso con el filtro «Instalación» o las 8 barras de
        # instalación del piso: la misma selección para el asistente.
        for task_ids in (self.floor.ids, self.spaces.ids):
            wizard = Wizard.with_context(
                default_plan_id=self.plan.id, construction_selection_task_ids=task_ids,
                construction_selection_stages=['installation'],
            ).create({'partner_id': self.leandro.id})
            self.assertEqual(wizard.stage, 'installation')
            self.assertFalse(wizard.whole_project)
            self.assertEqual(len(wizard.line_ids), 8)
            self.assertAlmostEqual(wizard.amount_total, 941.17)
        # Con varias etapas marcadas, el asistente toma todas.
        wizard = Wizard.with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.floor.ids,
            construction_selection_stages=['assembly', 'installation'],
        ).create({'partner_id': self.leandro.id})
        self.assertFalse(wizard.stage)
        self.assertFalse(wizard.stage_production)
        self.assertTrue(wizard.stage_assembly and wizard.stage_installation)

    def test_selection_summary_by_stage(self):
        summary = self.plan.get_selection_summary(
            [str(self.floor.id)], {'stages': ['installation']})
        installation = self.plan.line_ids.filtered(lambda l: l.stage == 'installation')
        self.assertAlmostEqual(summary['total'], round(sum(installation.mapped('amount_planned')), 2))
        self.assertAlmostEqual(summary['contract'], 941.17)

    # ------------------------------------------------------------------
    # Carga semanal
    # ------------------------------------------------------------------
    def test_weekly_load(self):
        load = self.plan.get_schedule_load()
        drivers = self.plan.line_ids.filtered(lambda l: l.resource_type in ('contract', 'labor'))
        self.assertAlmostEqual(load['total'], round(sum(drivers.mapped('amount_planned')), 2))
        self.assertAlmostEqual(load['total'], 2301.53)
        # Una etapa por semana desde el lunes 12/10; la producción no tiene
        # contratas: la carga empieza con el armado, el 19/10.
        self.assertEqual(load['weeks'], ['2026-10-19', '2026-10-26', '2026-11-02'])
        installation = next(r for r in load['rows'] if r['stage'] == 'installation')
        self.assertTrue(installation['unassigned'])
        self.assertAlmostEqual(installation['total'], 941.17)
        self.assertEqual(installation['values'][0], 0.0)
        self.assertAlmostEqual(installation['values'][1], 941.17)
        self.assertAlmostEqual(sum(load['totals']), load['total'], places=1)
        only = self.plan.get_schedule_load('installation')
        self.assertEqual([r['stage'] for r in only['rows']], ['installation'])

    def test_schedule_action(self):
        action = self.plan.action_open_schedule()
        self.assertEqual(action['tag'], 'al_construction_planner.schedule')
        self.assertEqual(action['context']['construction_plan_id'], self.plan.id)
        self.assertTrue(self.planner.has_group('al_project_gantt_base.group_gantt_user'))


@tagged('post_install', '-at_install')
class TestScheduleTour(HttpCase):

    def test_schedule_tour(self):
        # El cronograma abre el plan aprobado más reciente: el de este test.
        _approved_demo(self.env, 'TEST TOUR CRONO')
        self.start_tour('/odoo/action-al_construction_planner.action_construction_schedule',
                        'al_construction_planner_schedule', login='admin')
