# -*- coding: utf-8 -*-
"""Capa de escritura: qué se guarda, qué se rechaza y cómo se reprograma."""
from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .common import GanttCommon


@tagged('post_install', '-at_install')
class TestGanttWrite(GanttCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.task_a = cls._create_task('A', day_offset=0, duration_days=2)
        cls.task_b = cls._create_task('B', day_offset=5, duration_days=3)
        cls.task_b.depend_on_ids = [(6, 0, cls.task_a.ids)]

    def _apply(self, changeset, user=None):
        env = self.env(user=user) if user else self.env(user=self.gantt_user)
        return env['project.project'].apply_gantt_changes(changeset)

    # ------------------------------------------------------------------
    # Actualización
    # ------------------------------------------------------------------
    def test_move_task_saves_dates(self):
        if not self.start_field:
            self.skipTest("La instancia no tiene campo de fecha de inicio")
        new_start = self.base_date + timedelta(days=10)
        new_end = new_start + timedelta(days=2)
        result = self._apply({'tasks': {'update': [{
            'id': self.task_a.id,
            'start': new_start.isoformat() + 'Z',
            'end': new_end.isoformat() + 'Z',
        }]}})
        self.assertTrue(result['ok'])
        self.assertEqual(result['updated'], [self.task_a.id])
        self.assertEqual(self.task_a[self.start_field], new_start)
        self.assertEqual(self.task_a[self.end_field], new_end)

    def test_rename_task(self):
        self._apply({'tasks': {'update': [{'id': self.task_a.id, 'name': 'A renombrada'}]}})
        self.assertEqual(self.task_a.name, 'A renombrada')

    def test_empty_name_is_rejected(self):
        with self.assertRaises(UserError):
            self._apply({'tasks': {'update': [{'id': self.task_a.id, 'name': '   '}]}})

    def test_inverted_dates_are_rejected(self):
        if not self.start_field:
            self.skipTest("La instancia no tiene campo de fecha de inicio")
        with self.assertRaises(UserError):
            self._apply({'tasks': {'update': [{
                'id': self.task_a.id,
                'start': (self.base_date + timedelta(days=5)).isoformat() + 'Z',
                'end': self.base_date.isoformat() + 'Z',
            }]}})

    def test_reparent_task(self):
        self._apply({'tasks': {'update': [{'id': self.task_b.id, 'parent_id': self.task_a.id}]}})
        self.assertEqual(self.task_b.parent_id, self.task_a)

    # ------------------------------------------------------------------
    # Creación y borrado
    # ------------------------------------------------------------------
    def test_create_task_returns_mapping(self):
        start = self.base_date + timedelta(days=20)
        result = self._apply({'tasks': {'create': [{
            'temp_id': 'tmp1',
            'project_id': self.project.id,
            'name': 'Tarea desde el Gantt',
            'start': start.isoformat() + 'Z',
            'end': (start + timedelta(days=1)).isoformat() + 'Z',
        }]}})
        self.assertIn('tmp1', result['created'])
        task = self.env['project.task'].browse(result['created']['tmp1'])
        self.assertEqual(task.name, 'Tarea desde el Gantt')
        self.assertEqual(task.project_id, self.project)
        self.assertEqual(task[self.end_field], start + timedelta(days=1))

    def test_create_without_project_is_rejected(self):
        with self.assertRaises(UserError):
            self._apply({'tasks': {'create': [{'temp_id': 'x', 'name': 'Sin proyecto'}]}})

    def test_delete_task(self):
        task = self._create_task('Para borrar', day_offset=1)
        result = self._apply({'tasks': {'delete': [task.id]}})
        self.assertEqual(result['deleted'], [task.id])
        self.assertFalse(task.exists())

    # ------------------------------------------------------------------
    # Dependencias
    # ------------------------------------------------------------------
    def test_create_and_delete_link(self):
        task_c = self._create_task('C', day_offset=9, duration_days=1)
        result = self._apply({'links': {'create': [{'source': self.task_b.id, 'target': task_c.id}]}})
        self.assertEqual(len(result['links_created']), 1)
        self.assertIn(self.task_b, task_c.depend_on_ids)

        result = self._apply({'links': {'delete': [{'source': self.task_b.id, 'target': task_c.id}]}})
        self.assertEqual(len(result['links_deleted']), 1)
        self.assertNotIn(self.task_b, task_c.depend_on_ids)

    def test_cyclic_link_is_rejected_by_odoo(self):
        """La detección de ciclos es nativa: no se reimplementa."""
        with self.assertRaises(Exception):
            self._apply({'links': {'create': [
                {'source': self.task_b.id, 'target': self.task_a.id},
            ]}})

    # ------------------------------------------------------------------
    # Permisos
    # ------------------------------------------------------------------
    def test_task_of_another_company_cannot_be_written(self):
        other_company = self.env['res.company'].create({'name': 'Compañía C'})
        other_project = self.env['project.project'].create({
            'name': 'Proyecto ajeno', 'company_id': other_company.id,
            'privacy_visibility': 'employees',
        })
        hidden = self._create_task('Ajena', project=other_project, day_offset=0)
        with self.assertRaises(AccessError):
            self._apply({'tasks': {'update': [{'id': hidden.id, 'name': 'Intruso'}]}})
        self.assertNotEqual(hidden.name, 'Intruso')

    def test_portal_user_is_rejected(self):
        portal_user = self.env['res.users'].create({
            'name': 'Portal write', 'login': 'gantt.portal.write@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        with self.assertRaises(AccessError):
            self._apply({'tasks': {'update': [{'id': self.task_a.id, 'name': 'x'}]}},
                        user=portal_user)

    # ------------------------------------------------------------------
    # Reprogramación en cadena
    # ------------------------------------------------------------------
    def test_chain_pushes_successor(self):
        if not self.start_field:
            self.skipTest("La instancia no tiene campo de fecha de inicio")
        original_duration = self.task_b[self.end_field] - self.task_b[self.start_field]
        new_end = self.base_date + timedelta(days=7)  # se solapa con B (empieza el día 5)
        self._apply({
            'tasks': {'update': [{
                'id': self.task_a.id,
                'start': (new_end - timedelta(days=2)).isoformat() + 'Z',
                'end': new_end.isoformat() + 'Z',
            }]},
            'reschedule_chain': True,
        })
        self.assertEqual(self.task_b[self.start_field], new_end,
                         "La sucesora debe empezar justo al terminar la predecesora")
        self.assertEqual(self.task_b[self.end_field] - self.task_b[self.start_field],
                         original_duration, "La duración de la sucesora no cambia")

    def test_chain_does_not_pull_tasks_back(self):
        """Mover una tarea hacia atrás no comprime el plan."""
        if not self.start_field:
            self.skipTest("La instancia no tiene campo de fecha de inicio")
        before = self.task_b[self.start_field]
        self._apply({
            'tasks': {'update': [{
                'id': self.task_a.id,
                'start': (self.base_date - timedelta(days=5)).isoformat() + 'Z',
                'end': (self.base_date - timedelta(days=3)).isoformat() + 'Z',
            }]},
            'reschedule_chain': True,
        })
        self.assertEqual(self.task_b[self.start_field], before)

    def test_chain_is_transitive(self):
        if not self.start_field:
            self.skipTest("La instancia no tiene campo de fecha de inicio")
        task_c = self._create_task('C', day_offset=9, duration_days=1)
        task_c.depend_on_ids = [(6, 0, self.task_b.ids)]
        self._apply({
            'tasks': {'update': [{
                'id': self.task_a.id,
                'start': (self.base_date + timedelta(days=8)).isoformat() + 'Z',
                'end': (self.base_date + timedelta(days=10)).isoformat() + 'Z',
            }]},
            'reschedule_chain': True,
        })
        self.assertGreaterEqual(self.task_b[self.start_field], self.base_date + timedelta(days=10))
        self.assertGreaterEqual(task_c[self.start_field], self.task_b[self.end_field])

    def test_editable_flag_reflects_real_permission(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        row = self._task_by_id(payload, self.task_a.id)
        self.assertTrue(row['editable'])
        self.assertTrue(payload['meta']['editable'])
        self.assertTrue(payload['meta']['can_create'])

    # ------------------------------------------------------------------
    # Campos del formulario de tarea
    # ------------------------------------------------------------------
    def test_form_fields_are_saved(self):
        """Etapa, responsables, prioridad, etiquetas y horas."""
        stage = self.env['project.task.type'].create({
            'name': 'En ejecución', 'sequence': 5, 'project_ids': [(6, 0, self.project.ids)],
        })
        tag = self.env['project.tags'].create({'name': 'Estructuras'})

        self._apply({'tasks': {'update': [{
            'id': self.task_a.id,
            'stage_id': stage.id,
            'user_ids': self.gantt_user.ids,
            'tag_ids': tag.ids,
            'priority': '3',
            'allocated_hours': 12.5,
        }]}})

        self.assertEqual(self.task_a.stage_id, stage)
        self.assertEqual(self.task_a.user_ids, self.gantt_user)
        self.assertEqual(self.task_a.tag_ids, tag)
        self.assertEqual(self.task_a.priority, '3')
        self.assertEqual(self.task_a.allocated_hours, 12.5)

    def test_form_fields_can_be_cleared(self):
        stage = self.env['project.task.type'].create({
            'name': 'Temporal', 'project_ids': [(6, 0, self.project.ids)],
        })
        self.task_a.write({'stage_id': stage.id, 'user_ids': [(6, 0, self.gantt_user.ids)]})

        self._apply({'tasks': {'update': [{
            'id': self.task_a.id, 'stage_id': False, 'user_ids': [],
        }]}})
        self.assertFalse(self.task_a.stage_id)
        self.assertFalse(self.task_a.user_ids)

    def test_description_is_stored_as_html(self):
        """El contrato acepta descripción en texto plano y la guarda escapada."""
        self._apply({'tasks': {'update': [{
            'id': self.task_a.id, 'description': 'Revisar con <el> residente',
        }]}})
        self.assertIn('&lt;el&gt;', self.task_a.description)
        self.assertTrue(self.task_a.description.startswith('<p>'))

    def test_form_options_include_stages_and_priorities(self):
        stage = self.env['project.task.type'].create({
            'name': 'Cierre', 'project_ids': [(6, 0, self.project.ids)],
        })
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        options = payload['filters']
        self.assertIn(stage.id, [item['id'] for item in options['stages']])
        self.assertIn('3', [item['value'] for item in options['priorities']])
        self.assertIn('tags', options)

    def test_activity_state_travels_in_the_payload(self):
        self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get_id('project.task'),
            'res_id': self.task_a.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Llamar al proveedor',
            'date_deadline': self.base_date.date(),
            'user_id': self.gantt_user.id,
        })
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        row = self._task_by_id(payload, self.task_a.id)
        self.assertTrue(row['activity_state'])
        self.assertEqual(row['activity_summary'], 'Llamar al proveedor')
