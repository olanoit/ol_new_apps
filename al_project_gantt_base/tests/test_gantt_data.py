# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo.tests.common import tagged

from .common import GanttCommon
from ..models.gantt_field_map import CONFIG_PARAM


@tagged('post_install', '-at_install')
class TestGanttData(GanttCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.task_a = cls._create_task('A — con inicio y fin', day_offset=0, duration_days=2)
        cls.task_b = cls._create_task('B — depende de A', day_offset=3, duration_days=1)
        cls.task_b.depend_on_ids = [(6, 0, cls.task_a.ids)]
        cls.task_child = cls._create_task(
            'C — subtarea de A', day_offset=1, duration_days=1, parent_id=cls.task_a.id,
        )
        cls.milestone = cls.env['project.milestone'].create({
            'name': 'Entrega parcial',
            'project_id': cls.project.id,
            'deadline': cls.base_date.date() + timedelta(days=10),
        })

    # ------------------------------------------------------------------
    # Forma del contrato
    # ------------------------------------------------------------------
    def test_payload_shape(self):
        payload = self._get_data(user=self.gantt_user)
        for key in ('contract_version', 'field_map', 'projects', 'tasks',
                    'links', 'milestones', 'colors', 'filters',
                    'applied_filters', 'meta'):
            self.assertIn(key, payload, f"Falta la clave {key} en el contrato")
        for key in ('count', 'total', 'limit', 'truncated', 'undated_count', 'tz',
                    'editable', 'can_create', 'can_reschedule_chain'):
            self.assertIn(key, payload['meta'])
        self.assertTrue(payload['meta']['editable'],
                        "El usuario del test puede escribir sus tareas")

    def test_project_entry(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        self.assertEqual(len(payload['projects']), 1)
        project = payload['projects'][0]
        self.assertEqual(project['id'], self.project.id)
        self.assertEqual(project['task_count'], 3)

    def test_task_serialization(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        task = self._task_by_id(payload, self.task_a.id)
        self.assertIsNotNone(task)
        self.assertEqual(task['name'], 'A — con inicio y fin')
        self.assertEqual(task['project_id'], self.project.id)
        self.assertTrue(task['end'].endswith('Z'), "Las fechas se emiten en ISO UTC")
        self.assertFalse(task['undated'])
        self.assertTrue(task['editable'], "editable refleja el permiso real de escritura")
        self.assertIn('color', task)
        if self.start_field:
            self.assertFalse(task['start_is_inferred'])
            self.assertTrue(task['start'].endswith('Z'))

    def test_hierarchy(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        child = self._task_by_id(payload, self.task_child.id)
        self.assertEqual(child['parent_id'], self.task_a.id)
        self.assertFalse(child['orphaned'])

    def test_parent_outside_the_set_is_reported_as_orphan(self):
        """Si el padre queda fuera del filtro, la hija se emite como raíz."""
        self.task_a.state = '1_canceled'
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'states': ['01_in_progress']},
        )
        self.assertIsNone(self._task_by_id(payload, self.task_a.id))
        child = self._task_by_id(payload, self.task_child.id)
        self.assertIsNotNone(child)
        self.assertIsNone(child['parent_id'])
        self.assertTrue(child['orphaned'])

    def test_links(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        links = [link for link in payload['links'] if link['target'] == self.task_b.id]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['source'], self.task_a.id)
        self.assertEqual(links[0]['type'], 'FS')
        self.assertNotIn('depend_on_ids', payload['tasks'][0],
                         "depend_on_ids no debe duplicarse dentro de la tarea")

    def test_link_with_one_end_outside_the_set_is_dropped(self):
        other_project = self.env['project.project'].create({
            'name': 'Otro proyecto', 'privacy_visibility': 'employees',
        })
        outside = self._create_task('Externa', project=other_project, day_offset=0)
        self.task_b.depend_on_ids = [(4, outside.id)]

        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        sources = {link['source'] for link in payload['links']}
        self.assertNotIn(outside.id, sources)
        self.assertIn(self.task_a.id, sources)

    def test_milestones(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        names = {milestone['name'] for milestone in payload['milestones']}
        self.assertIn('Entrega parcial', names)

    # ------------------------------------------------------------------
    # Fechas y avance
    # ------------------------------------------------------------------
    def test_start_is_inferred_when_missing(self):
        """Con solo fecha de fin, la barra se calcula hacia atrás."""
        if not self.start_field:
            self.skipTest("La instancia no tiene campo de fecha de inicio")
        task = self._create_task('Sin inicio', day_offset=5, with_start=False)
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        row = self._task_by_id(payload, task.id)
        self.assertTrue(row['start_is_inferred'])
        self.assertIsNotNone(row['start'])
        self.assertLess(row['start'], row['end'])

    def test_undated_tasks(self):
        task = self.env['project.task'].create({
            'name': 'Sin fechas', 'project_id': self.project.id,
        })
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        self.assertIsNone(self._task_by_id(payload, task.id),
                          "Por defecto las tareas sin fin no entran en el timeline")

        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'include_undated': True},
        )
        row = self._task_by_id(payload, task.id)
        self.assertIsNotNone(row)
        self.assertTrue(row['undated'])
        self.assertIsNone(row['end'])
        self.assertEqual(payload['meta']['undated_count'], 1)

    def test_mode_none_draws_nothing(self):
        """Sin campo de fin no hay barras; las tareas solo salen si se piden."""
        self.env['ir.config_parameter'].sudo().set_param(CONFIG_PARAM, '{"date_end": null}')
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        self.assertEqual(payload['field_map']['mode'], 'none')
        self.assertEqual(payload['tasks'], [])
        self.assertEqual(payload['meta']['total'], 3)

        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'include_undated': True},
        )
        self.assertEqual(len(payload['tasks']), 3)
        self.assertTrue(all(task['undated'] for task in payload['tasks']))

    def test_progress_derived_or_real(self):
        self.task_a.state = '1_done'
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        row = self._task_by_id(payload, self.task_a.id)
        if payload['field_map']['progress']:
            self.assertFalse(row['progress_is_derived'])
        else:
            self.assertTrue(row['progress_is_derived'])
            self.assertEqual(row['progress'], 100.0)

    # ------------------------------------------------------------------
    # Filtros, límite y rendimiento
    # ------------------------------------------------------------------
    def test_filter_by_state(self):
        self.task_b.state = '1_canceled'
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'states': ['1_canceled']},
        )
        self.assertEqual([task['id'] for task in payload['tasks']], [self.task_b.id])

    def test_filter_by_user(self):
        self.task_a.user_ids = [(6, 0, self.gantt_user.ids)]
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'user_ids': self.gantt_user.ids},
        )
        ids = [task['id'] for task in payload['tasks']]
        self.assertIn(self.task_a.id, ids)
        self.assertNotIn(self.task_b.id, ids)
        row = self._task_by_id(payload, self.task_a.id)
        self.assertEqual(row['user_ids'][0]['name'], self.gantt_user.name)

    def test_filter_by_date_range(self):
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={
                'date_from': (self.base_date + timedelta(days=10)).isoformat(),
                'date_to': (self.base_date + timedelta(days=20)).isoformat(),
            },
        )
        self.assertEqual(payload['tasks'], [])

    # ------------------------------------------------------------------
    # Opciones de filtrado que consume la interfaz
    # ------------------------------------------------------------------
    def test_filter_options_list_states_and_assignees(self):
        """Los valores de los desplegables los da el servidor, no la interfaz."""
        self.task_a.user_ids = [(6, 0, self.gantt_user.ids)]
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        options = payload['filters']

        state_values = {state['value'] for state in options['states']}
        self.assertIn('01_in_progress', state_values)
        self.assertIn('1_done', state_values)
        self.assertTrue(all(state['label'] for state in options['states']),
                        "Cada estado debe traer su etiqueta traducida")

        users = {user['id']: user for user in options['users']}
        self.assertIn(self.gantt_user.id, users)
        self.assertEqual(users[self.gantt_user.id]['task_count'], 1)

    def test_filter_options_only_include_visible_assignees(self):
        """Un responsable de otro proyecto no aparece si ese proyecto no se pide."""
        other_project = self.env['project.project'].create({
            'name': 'Proyecto aparte', 'privacy_visibility': 'employees',
        })
        other_user = self.env['res.users'].create({
            'name': 'Ajeno',
            'login': 'gantt.other@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        task = self._create_task('Tarea aparte', project=other_project, day_offset=0)
        task.user_ids = [(6, 0, other_user.ids)]

        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        user_ids = {user['id'] for user in payload['filters']['users']}
        self.assertNotIn(other_user.id, user_ids)

    def test_applied_filters_are_echoed(self):
        options = {
            'states': ['1_done'],
            'user_ids': self.gantt_user.ids,
            'date_from': '2026-03-01 00:00:00',
            'date_to': '2026-04-01 23:59:59',
            'include_undated': True,
        }
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id], options=options,
        )
        applied = payload['applied_filters']
        self.assertEqual(applied['states'], ['1_done'])
        self.assertEqual(applied['user_ids'], self.gantt_user.ids)
        self.assertEqual(applied['date_from'], '2026-03-01 00:00:00')
        self.assertTrue(applied['include_undated'])

    def test_combined_filters(self):
        """Estado + responsable + rango, todos a la vez."""
        self.task_a.user_ids = [(6, 0, self.gantt_user.ids)]
        self.task_a.state = '1_done'
        self.task_b.user_ids = [(6, 0, self.gantt_user.ids)]

        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={
                'states': ['1_done'],
                'user_ids': self.gantt_user.ids,
                'date_from': self.base_date.isoformat(),
                'date_to': (self.base_date + timedelta(days=30)).isoformat(),
            },
        )
        self.assertEqual([task['id'] for task in payload['tasks']], [self.task_a.id])

    def test_limit_and_truncated_flag(self):
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id], options={'limit': 2},
        )
        self.assertEqual(len(payload['tasks']), 2)
        self.assertTrue(payload['meta']['truncated'])
        self.assertEqual(payload['meta']['total'], 3)

        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        self.assertFalse(payload['meta']['truncated'])

    def test_user_names_resolved_in_batch(self):
        """Los responsables de todas las tareas se resuelven de una vez."""
        users = self.env['res.users'].create([{
            'name': f'Responsable {index}',
            'login': f'gantt.resp{index}@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        } for index in range(3)])
        self.task_a.user_ids = [(6, 0, users.ids)]
        self.task_b.user_ids = [(6, 0, users[:2].ids)]

        GanttData = type(self.env['al.gantt.data'])
        calls = []
        original = GanttData._read_user_names

        def spy(self_, records):
            calls.append(len(records))
            return original(self_, records)

        self.patch(GanttData, '_read_user_names', spy)
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])

        self.assertEqual(len(calls), 1, "Debe haber una sola resolución de nombres por consulta")
        names = {user['name'] for user in self._task_by_id(payload, self.task_a.id)['user_ids']}
        self.assertEqual(names, set(users.mapped('name')))

    def test_inactive_user_keeps_its_name(self):
        """Un responsable dado de baja debe seguir mostrándose con nombre."""
        retired = self.env['res.users'].create({
            'name': 'Responsable de baja',
            'login': 'gantt.retired@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.task_a.user_ids = [(6, 0, retired.ids)]
        retired.active = False

        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        row = self._task_by_id(payload, self.task_a.id)
        self.assertEqual([user['name'] for user in row['user_ids']], ['Responsable de baja'])

    def test_unknown_project_returns_empty_payload(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[-1])
        self.assertEqual(payload['projects'], [])
        self.assertEqual(payload['tasks'], [])
        self.assertEqual(payload['meta']['count'], 0)


@tagged('post_install', '-at_install')
class TestGanttCalendar(GanttCommon):
    """El sombreado de no laborables sale del calendario real del proyecto."""

    def test_calendar_comes_from_the_project(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        calendar = payload['calendar']
        self.assertIn('working_days', calendar)
        self.assertIn('holidays', calendar)
        self.assertEqual(
            calendar['working_days'],
            sorted({int(day) for day in self.project.resource_calendar_id.attendance_ids.mapped('dayofweek')})
            or [0, 1, 2, 3, 4],
        )
        self.assertFalse(calendar['mixed'])

    def test_holidays_are_reported(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Fiestas Patrias',
            'calendar_id': self.project.resource_calendar_id.id,
            'date_from': '2026-07-28 00:00:00',
            'date_to': '2026-07-29 23:59:59',
        })
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        names = {holiday['name'] for holiday in payload['calendar']['holidays']}
        self.assertIn('Fiestas Patrias', names)

    def test_mixed_calendars_are_flagged(self):
        other_company = self.env['res.company'].create({'name': 'Compañía D'})
        other_calendar = self.env['resource.calendar'].create({
            'name': 'Turno noche', 'company_id': other_company.id,
        })
        other_company.resource_calendar_id = other_calendar
        project = self.env['project.project'].create({
            'name': 'Proyecto con otro calendario',
            'company_id': other_company.id,
            'privacy_visibility': 'employees',
        })
        self._create_task('Tarea', project=project, day_offset=0)

        payload = self.env(user=self.gantt_user).user.company_ids  # noqa: F841
        self.gantt_user.company_ids = [(4, other_company.id)]
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id, project.id],
        )
        self.assertTrue(payload['calendar']['mixed'],
                        "Con dos calendarios distintos hay que avisar de cuál se dibuja")


@tagged('post_install', '-at_install')
class TestAssignableUsers(GanttCommon):
    """El formulario ofrece todas las personas asignables, no solo las ocupadas."""

    def test_assignable_users_are_all_internal_active_users(self):
        free_user = self.env['res.users'].create({
            'name': 'Nadie le asignó nada',
            'login': 'gantt.free@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        busy_user = self.gantt_user
        task = self._create_task('Con responsable', day_offset=0)
        task.user_ids = [(6, 0, busy_user.ids)]

        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        filter_ids = {user['id'] for user in payload['filters']['users']}
        assignable_ids = {user['id'] for user in payload['filters']['assignable_users']}

        self.assertIn(busy_user.id, filter_ids)
        self.assertNotIn(free_user.id, filter_ids,
                         "El filtro solo ofrece a quien tiene tareas")
        self.assertIn(free_user.id, assignable_ids,
                      "El formulario debe poder asignar a cualquiera")
        self.assertIn(busy_user.id, assignable_ids)

    def test_assignable_users_exclude_portal_and_archived(self):
        portal_user = self.env['res.users'].create({
            'name': 'Portal asignable', 'login': 'gantt.portal.assign@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        archived = self.env['res.users'].create({
            'name': 'Archivado', 'login': 'gantt.archived@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        archived.active = False

        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        assignable_ids = {user['id'] for user in payload['filters']['assignable_users']}
        self.assertNotIn(portal_user.id, assignable_ids)
        self.assertNotIn(archived.id, assignable_ids)

    def test_assignable_users_are_sorted_by_name(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        names = [user['name'] for user in payload['filters']['assignable_users']]
        self.assertEqual(names, sorted(names))
