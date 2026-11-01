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
from datetime import date, timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.al_construction_planner.models import construction_stage as core_stage
from odoo.addons.al_construction_planner.models import construction_resource_plan as core_plan

from .common import PlannerCommon
from .test_schedule import _approved_demo

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


@tagged('post_install', '-at_install')
class TestPackage116Stage3b(TransactionCase):
    """Bloque 3b: etapa actual y plazo de cada ambiente (M115-04 con
    M116-02), informe «Etapa de los ambientes» (M115-05) y carga semanal con
    plan frente a ejecutado y la semana de la obra (M115-06 con M116-07).
    Sobre el demo del Cronograma (8 ambientes del piso 05)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.resource_calendar_id = cls.env['resource.calendar'].create({
            'name': 'Lunes a viernes (test 3b)', 'company_id': cls.env.company.id,
            'tz': 'America/Lima',
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'name': 'Día %s' % day, 'dayofweek': str(day), 'hour_from': 8, 'hour_to': 17,
                'day_period': 'full_day'}) for day in range(5)]})
        demo = _approved_demo(cls.env, 'TEST 116 3B')
        cls.plan = demo['plan']
        cls.project = demo['project']
        cls.floor = demo['floor']
        cls.Stage = cls.env['construction.space.stage']
        cls.spaces = cls.env['project.task'].search([
            ('project_id', '=', cls.project.id), ('construction_level', '=', 'space')])
        cls.space = cls.spaces[0]
        cls.validator = new_test_user(
            cls.env, 'plan_3b_validador', name='Validador (test)',
            groups='al_construction_planner.group_planner_exec_validator,'
                   'al_construction_planner.group_planner_amounts')
        cls.photo = cls.env['ir.attachment'].create({'name': 'foto.png',
                                                     'datas': base64.b64encode(b'x')})

    def _lines(self, space, stage):
        return self.plan.line_ids.filtered(
            lambda l: l.space_task_id == space and l.stage == stage
            and l.resource_type in ('contract', 'labor'))

    def _report(self, line, qty, day=None, validate=True):
        progress = self.env['construction.task.progress'].create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
            'plan_line_id': line.id, 'qty': qty, 'date': day or date.today(),
            'attachment_ids': [Command.set(self.photo.copy().ids)]})
        if validate:
            progress.with_user(self.validator).action_validate()
        return progress

    def _stages(self, space):
        """Etapas del ambiente con líneas de contrata, en su orden."""
        catalog = {s.code: s for s in self.env['construction.stage'].search([])}
        records = self.Stage.search([('space_task_id', '=', space.id)])
        return sorted(records, key=lambda r: catalog[r.stage]._tree_key())

    # ------------------------------------------------------------------
    # M115-04 · árbol 1
    # ------------------------------------------------------------------
    def test_current_stage(self):
        space = self.space
        self.assertTrue(self.project._construction_space_state_labels())
        self.assertEqual(space.construction_current_stage, 'pending')
        space.sudo().write({'construction_measured': True})
        self.assertEqual(space.construction_current_stage, 'measured')
        driven = [r for r in self._stages(space) if self._lines(space, r.stage)]
        first, second = driven[0], driven[1]
        # Avance en la primera etapa con contratas: esa etapa con su %; las
        # etapas anteriores sin contratas (producción en taller) cuentan
        # como terminadas.
        lines = self._lines(space, first.stage)
        for line in lines[1:]:
            self._report(line, line.qty_planned)
        self._report(lines[0], lines[0].qty_planned / 2)
        self.assertEqual(space.construction_current_stage, first.stage)
        self.assertGreater(space.construction_current_stage_progress, 0)
        self.assertLess(space.construction_current_stage_progress, 100)
        self.assertEqual(space.construction_current_stage_end, first.date_end)
        self._report(lines[0], lines[0].qty_planned / 2)
        self.assertEqual(space.construction_current_stage, second.stage)
        self.assertEqual(space.construction_current_stage_progress, 0)
        # Todas al 100 %: la última etapa mientras los módulos no estén
        # entregados; con los módulos entregados, Entregado.
        for record in driven[1:]:
            for line in self._lines(space, record.stage):
                self._report(line, line.qty_planned)
        self.assertEqual(space.construction_current_stage, driven[-1].stage)
        self.assertEqual(space.construction_current_stage_progress, 100)
        modules = self.env['project.task'].search([
            ('construction_space_task_id', '=', space.id), ('construction_level', '=', 'module')])
        modules.sudo().write({'construction_unit_state': 'delivered'})
        self.assertEqual(space.construction_current_stage, 'delivered')
        self.assertEqual(space.construction_stage_schedule, 'done')
        # Un ambiente de otro piso no se movió.
        self.assertEqual(self.spaces[1].construction_current_stage, 'pending')

    def test_current_stage_without_space_states(self):
        """Obra cuyo perfil no mide ambientes (construcción por partidas):
        sin Pendiente, Medido ni Entregado."""
        template = self.project.construction_level_template_id \
            or self.env['construction.level.template'].search([], limit=1)
        profile = self.env['construction.vertical.profile'].create({
            'name': 'Partidas (test 3b)', 'code': 'PART3B', 'feature_measurement': False,
            'level_template_id': template.id})
        self.project.construction_profile_id = profile
        self.assertFalse(self.project._construction_space_state_labels())
        self.spaces._construction_refresh_current_stage()
        first = self._stages(self.space)[0]
        self.assertEqual(self.space.construction_current_stage, first.stage)
        payload = self.env['al.gantt.data'].with_user(self.validator).get_data(
            [self.project.id], {'construction_schedule': True, 'construction_plan_id': self.plan.id})
        codes = [state['code'] for state in payload['construction']['space_states']]
        self.assertNotIn('pending', codes)
        self.assertNotIn('delivered', codes)

    # ------------------------------------------------------------------
    # M115-04 · árbol 2
    # ------------------------------------------------------------------
    def test_schedule(self):
        space = self.space
        start, end = date(2026, 11, 2), date(2026, 11, 13)   # lunes a viernes, 10 días hábiles

        def check(today, pct, expected, text=None):
            space.sudo().with_context(construction_current_stage_refresh=True).write({
                'construction_current_stage': 'assembly',
                'construction_current_stage_progress': pct,
                'construction_current_stage_start': start,
                'construction_current_stage_end': end})
            task = space.with_context(construction_today=today)
            self.assertEqual(task.construction_stage_schedule, expected, (today, pct))
            if text:
                self.assertIn(text, task.construction_stage_schedule_label)

        check(date(2026, 10, 30), 0, 'on_time', 'inicia 02/11')
        check(date(2026, 11, 3), 0, 'risk', 'debía iniciar 02/11')
        # 5 de 10 días hábiles: se espera 50 %; con 40 % está a tiempo (margen
        # 20) y con 20 % en riesgo.
        check(date(2026, 11, 6), 40, 'on_time')
        check(date(2026, 11, 6), 20, 'risk', 'esperado')
        check(date(2026, 11, 16), 80, 'late', 'atrasada 3 d')
        check(date(2026, 11, 16), 100, 'done')
        space.sudo().with_context(construction_current_stage_refresh=True).write({
            'construction_current_stage_progress': 50, 'construction_current_stage_start': False})
        self.assertEqual(space.construction_stage_schedule, 'no_dates')
        # El filtro «Solo atrasados o en riesgo» busca por el plazo.
        check(date(2026, 11, 16), 80, 'late')
        found = self.env['project.task'].with_context(construction_today=date(2026, 11, 16)).search(
            [('construction_stage_schedule', 'in', ['late', 'risk']),
             ('project_id', '=', self.project.id)])
        self.assertIn(space, found)

    # ------------------------------------------------------------------
    # Cronograma y M115-05
    # ------------------------------------------------------------------
    def test_schedule_payload_and_report(self):
        self.space.sudo().write({'construction_measured': True})
        payload = self.env['al.gantt.data'].with_user(self.validator).get_data(
            [self.project.id], {'construction_schedule': True, 'construction_plan_id': self.plan.id})
        tasks = {task['id']: task for task in payload['tasks']}
        current = tasks[self.space.id]['construction']['current']
        self.assertEqual(current['code'], 'measured')
        self.assertTrue(current['is_state'])
        counts = tasks[self.floor.id]['construction']['current_counts']
        self.assertEqual(counts, {'measured': 1, 'pending': len(self.spaces) - 1})
        codes = [state['code'] for state in payload['construction']['space_states']]
        self.assertEqual(codes[:2], ['pending', 'measured'])
        self.assertEqual(codes[-1], 'delivered')
        # Filtro por etapa actual: el ambiente y sus ancestros.
        only = self.env['al.gantt.data'].with_user(self.validator).get_data(
            [self.project.id], {'construction_schedule': True, 'construction_plan_id': self.plan.id,
                                'construction_current_stages': ['measured']})
        ids = {task['id'] for task in only['tasks']}
        self.assertIn(self.space.id, ids)
        self.assertIn(self.floor.id, ids)
        self.assertFalse(ids & set((self.spaces - self.space).ids))
        # Informe: cada ambiente una vez, en su etapa actual.
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner.action_construction_space_stage_report')
        self.assertIn('construction_current_stage', action['domain'])
        groups = self.env['project.task']._read_group(
            [('construction_current_stage', '!=', False), ('project_id', '=', self.project.id)],
            ['construction_current_stage'], ['__count'])
        self.assertEqual(dict(groups), {'measured': 1, 'pending': len(self.spaces) - 1})
        # Niveles 1 y 2 de la plantilla: piso y departamento.
        self.assertEqual(self.space.construction_level1_task_id, self.floor)
        self.assertEqual(self.space.construction_level2_task_id, self.space.parent_id)

    # ------------------------------------------------------------------
    # M115-06 con M116-07
    # ------------------------------------------------------------------
    def test_weekly_load_plan_vs_executed(self):
        self.project.construction_week_start_day = '3'   # jueves
        load = self.plan.with_user(self.validator).get_schedule_load()
        self.assertTrue(load['weeks'])
        for start, end in zip(load['weeks'], load['week_ends']):
            self.assertEqual(fields.Date.to_date(start).weekday(), 3)
            self.assertEqual(fields.Date.to_date(end).weekday(), 2)
        drivers = self.plan.line_ids.filtered(lambda l: l.resource_type in ('contract', 'labor'))
        self.assertAlmostEqual(load['total'], round(sum(drivers.mapped('amount_planned')), 2), 1)
        # Un avance validado en la semana de su fecha; uno reportado, no.
        line = drivers.filtered(lambda l: l.space_task_id == self.space)[0]
        day = fields.Date.to_date(load['weeks'][0]) + timedelta(days=1)
        validated = self._report(line, line.qty_planned / 2, day)
        self._report(line, line.qty_planned / 4, day, validate=False)
        load = self.plan.with_user(self.validator).get_schedule_load()
        self.assertAlmostEqual(load['executed_total'], validated.amount, 2)
        self.assertAlmostEqual(load['executed_totals'][0], validated.amount, 2)
        row = next(r for r in load['rows'] if r['stage'] == line.stage
                   and r['executed_total'])
        self.assertAlmostEqual(row['executed'][0], validated.amount, 2)
        group = next(g for g in load['groups'] if g['stage'] == line.stage)
        self.assertIn(row, group['rows'])
        self.assertEqual(load['thresholds'], {'green': 95, 'amber': 70})
        # La semana de la carga es la de la liquidación (CR-10).
        period = self.project._construction_period(day)[0]
        self.assertEqual(load['weeks'][0], fields.Date.to_string(period))
        # Con la semana desde el viernes, las columnas van de viernes a jueves.
        self.project.construction_week_start_day = '4'
        load = self.plan.with_user(self.validator).get_schedule_load()
        self.assertTrue(all(fields.Date.to_date(w).weekday() == 4 for w in load['weeks']))
