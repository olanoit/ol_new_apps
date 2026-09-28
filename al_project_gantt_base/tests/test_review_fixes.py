# -*- coding: utf-8 -*-
"""Correcciones de la auditoría de la suite Gantt.

Cada test fija un defecto concreto que ya se vio en la práctica: padre perdido
al editar una subtarea huérfana, avance en otra escala, edición imposible sin
campo de inicio, fuga de datos por las líneas base, cadena incompleta con dos
predecesoras, ruta crítica medida contra otro proyecto y filtros desplazados
por el huso horario.
"""
import json
from datetime import timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .common import GanttCommon
from ..models.gantt_field_map import CONFIG_PARAM


@tagged('post_install', '-at_install')
class TestGanttReviewFixes(GanttCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls._create_task('Padre', day_offset=0, duration_days=4)
        cls.child = cls._create_task(
            'Hija', day_offset=1, duration_days=1, parent_id=cls.parent.id,
        )

    def _apply(self, changeset, user=None):
        env = self.env(user=user or self.gantt_user)
        return env['project.project'].apply_gantt_changes(changeset)

    # ------------------------------------------------------------------
    # Subtarea huérfana: editarla no le quita el padre
    # ------------------------------------------------------------------
    def test_editing_an_orphan_keeps_its_real_parent(self):
        self.parent.state = '1_canceled'
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'states': ['01_in_progress']},
        )
        row = self._task_by_id(payload, self.child.id)
        self.assertTrue(row['orphaned'])
        self.assertIsNone(row['parent_id'])

        # La interfaz solo manda lo que cambió: un renombrado no lleva parent_id.
        self._apply({'tasks': {'update': [{'id': self.child.id, 'name': 'Hija renombrada'}]}})
        self.assertEqual(self.child.name, 'Hija renombrada')
        self.assertEqual(self.child.parent_id, self.parent,
                         "Una edición que no toca el padre no puede desvincular la subtarea")

    def test_reparent_to_an_unreadable_task_is_rejected(self):
        private_project = self.env['project.project'].create({
            'name': 'Privado', 'privacy_visibility': 'followers',
        })
        private_task = self._create_task('Oculta', project=private_project)
        with self.assertRaises(AccessError):
            self._apply({'tasks': {'update': [{'id': self.child.id, 'parent_id': private_task.id}]}})

    # ------------------------------------------------------------------
    # Avance: siempre en porcentaje, y solo se escribe si se puede guardar
    # ------------------------------------------------------------------
    def test_timesheet_progress_is_a_fraction_scaled_to_percent(self):
        FieldMap = self.env['al.gantt.field.map']
        field_map = {'progress': 'progress'}
        self.assertEqual(FieldMap.get_progress_factor(field_map), 100.0)
        progress, derived = self.env['al.gantt.data']._compute_progress(
            {'progress': 0.5, 'state': '01_in_progress'}, field_map,
        )
        self.assertEqual(progress, 50.0, "0.5 de hr_timesheet es el 50 %")
        self.assertFalse(derived)

    def test_progress_scale_can_be_forced(self):
        self.env['ir.config_parameter'].sudo().set_param(
            CONFIG_PARAM, json.dumps({'progress_scale': 1}),
        )
        self.assertEqual(
            self.env['al.gantt.field.map'].get_progress_factor({'progress': 'progress'}), 1.0,
        )

    def test_computed_progress_is_not_offered_nor_written(self):
        FieldMap = self.env['al.gantt.field.map']
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        writable = FieldMap.is_progress_writable(payload['field_map'])
        self.assertEqual(payload['meta']['can_edit_progress'], writable)
        progress_field = payload['field_map']['progress']
        if not progress_field:
            self.skipTest("La instancia no tiene campo de avance")
        field = self.env['project.task']._fields[progress_field]
        if field.compute and not field.inverse:
            self.assertFalse(writable, "Un calculado sin inverse se recalcula solo")
            before = self.child[progress_field]
            self._apply({'tasks': {'update': [{'id': self.child.id, 'progress': 40}]}})
            self.assertEqual(self.child[progress_field], before)

    # ------------------------------------------------------------------
    # Sin campo de inicio (Community): se guarda el fin y no falla
    # ------------------------------------------------------------------
    def test_deadline_only_saves_the_end_and_ignores_the_start(self):
        self.env['ir.config_parameter'].sudo().set_param(
            CONFIG_PARAM, json.dumps({'date_start': None}),
        )
        field_map = self.env['al.gantt.field.map'].get_map()
        self.assertEqual(field_map['mode'], 'deadline_only')
        new_end = self.base_date + timedelta(days=20)
        result = self._apply({'tasks': {'update': [{
            'id': self.child.id,
            'start': (new_end - timedelta(hours=8)).isoformat() + 'Z',
            'end': new_end.isoformat() + 'Z',
        }]}})
        self.assertTrue(result['ok'])
        self.assertEqual(self.child[field_map['date_end']], new_end)

    # ------------------------------------------------------------------
    # Líneas base: sin acceso directo por ORM
    # ------------------------------------------------------------------
    def test_baseline_lines_are_not_readable_through_the_orm(self):
        self.env(user=self.gantt_user)['al.gantt.data'].create_baseline([self.project.id], 'B')
        with self.assertRaises(AccessError):
            self.env(user=self.gantt_user)['al.gantt.baseline.line'].search_read([], ['task_id'])
        with self.assertRaises(AccessError):
            self.env(user=self.gantt_user)['al.gantt.baseline'].search_read([], ['name'])
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        self.assertIn('B', {baseline['name'] for baseline in payload['baselines']})

    def test_baseline_of_an_invisible_project_is_not_applied(self):
        private_project = self.env['project.project'].create({
            'name': 'Privado', 'privacy_visibility': 'followers',
        })
        self._create_task('Oculta', project=private_project)
        result = self.env['al.gantt.data'].create_baseline([private_project.id], 'Ajena')
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'baseline_id': result['baselines'][0]['id']},
        )
        self.assertFalse(payload['meta']['baseline']['applied'])

    def test_baseline_header_only_allows_renaming(self):
        result = self.env['al.gantt.data'].create_baseline([self.project.id], 'Original')
        baseline = self.env['al.gantt.baseline'].browse(result['baselines'][0]['id'])
        baseline.name = 'Renombrada'
        other = self.env['project.project'].create({'name': 'Otro'})
        with self.assertRaises(UserError):
            baseline.project_id = other

    # ------------------------------------------------------------------
    # Reprogramación en cadena con dos predecesoras
    # ------------------------------------------------------------------
    def test_chain_repushes_a_task_reached_twice(self):
        if not (self.start_field and self.end_field):
            self.skipTest("La cadena necesita inicio y fin")
        # A -> S, A -> B, B -> S, S -> C. Al mover A, S (más corta, se procesa
        # antes) se empuja primero por A; luego B la vuelve a empujar más
        # lejos, y C tiene que quedar detrás del fin definitivo de S.
        task_a = self._create_task('A', day_offset=0, duration_days=1)
        task_s = self._create_task('S', day_offset=1, duration_days=1)
        task_b = self._create_task('B', day_offset=1, duration_days=4)
        task_c = self._create_task('C', day_offset=3, duration_days=1)
        task_b.depend_on_ids = [(6, 0, task_a.ids)]
        task_s.depend_on_ids = [(6, 0, (task_a | task_b).ids)]
        task_c.depend_on_ids = [(6, 0, task_s.ids)]

        self._apply({
            'tasks': {'update': [{
                'id': task_a.id,
                'start': (self.base_date + timedelta(days=1)).isoformat() + 'Z',
                'end': (self.base_date + timedelta(days=2)).isoformat() + 'Z',
            }]},
            'reschedule_chain': True,
        })
        self.assertGreaterEqual(task_s[self.start_field], task_b[self.end_field])
        self.assertGreaterEqual(task_c[self.start_field], task_s[self.end_field])

    # ------------------------------------------------------------------
    # Ruta crítica por proyecto
    # ------------------------------------------------------------------
    def test_critical_path_is_measured_per_project(self):
        tasks = [
            {'id': 1, 'project_id': 10, 'parent_id': None,
             'start': '2026-03-01T08:00:00Z', 'end': '2026-03-20T08:00:00Z'},
            {'id': 2, 'project_id': 20, 'parent_id': None,
             'start': '2026-03-01T08:00:00Z', 'end': '2026-03-03T08:00:00Z'},
        ]
        self.env['al.gantt.data']._apply_critical_path(tasks, [])
        self.assertTrue(tasks[0]['critical'])
        self.assertTrue(tasks[1]['critical'],
                        "La última tarea de un proyecto corto también es crítica en su proyecto")

    # ------------------------------------------------------------------
    # Filtros de fecha en la hora del usuario
    # ------------------------------------------------------------------
    def test_date_filter_bounds_use_the_user_timezone(self):
        data = self.env(user=self.gantt_user)['al.gantt.data']
        self.gantt_user.tz = 'America/Lima'
        self.assertEqual(data._local_to_utc('2026-03-02 00:00:00'), '2026-03-02 05:00:00')
        self.gantt_user.tz = False
        self.assertEqual(data._local_to_utc('2026-03-02 00:00:00'), '2026-03-02 00:00:00')

    def test_export_dates_use_the_user_timezone(self):
        data = self.env(user=self.gantt_user)['al.gantt.data']
        self.gantt_user.tz = 'America/Lima'
        # 03:00 UTC del día 3 son las 22:00 del día 2 en Lima.
        self.assertEqual(str(data._to_date('2026-03-03T03:00:00Z')), '2026-03-02')
        self.assertEqual(str(data._to_date('2026-03-03')), '2026-03-03')

    # ------------------------------------------------------------------
    # Contrato: proyectos disponibles aunque se acote la consulta
    # ------------------------------------------------------------------
    def test_available_projects_survive_the_selection(self):
        other = self.env['project.project'].create({
            'name': 'Otro visible', 'privacy_visibility': 'employees',
        })
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        self.assertEqual([p['id'] for p in payload['projects']], [self.project.id])
        self.assertIn(other.id, {p['id'] for p in payload['available_projects']})

    # ------------------------------------------------------------------
    # Colores: solo valores CSS inocuos
    # ------------------------------------------------------------------
    def test_color_must_be_hex_or_a_css_name(self):
        Color = self.env['al.gantt.state.color']
        Color.create({'name': 'Hex', 'state_key': 'x_hex', 'color': '#1a7d3d'})
        Color.create({'name': 'Nombre', 'state_key': 'x_name', 'color': 'red'})
        with self.assertRaises(ValidationError):
            Color.create({'name': 'Mal', 'state_key': 'x_bad',
                          'color': 'red; background:url(http://x)'})

    def test_report_requires_the_gantt_group(self):
        report = self.env.ref('al_project_gantt_base.action_report_gantt')
        self.assertIn(self.env.ref('al_project_gantt_base.group_gantt_user'), report.group_ids)
