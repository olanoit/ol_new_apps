# -*- coding: utf-8 -*-
"""Ruta crítica: holguras y cadena crítica calculadas en el servidor."""
from odoo.tests.common import tagged

from .common import GanttCommon


@tagged('post_install', '-at_install')
class TestGanttCriticalPath(GanttCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Cadena larga: A(5d) -> B(10d) -> C(5d), y una tarea corta en paralelo
        # que cuelga de A y no condiciona el final.
        cls.task_a = cls._create_task('A', day_offset=0, duration_days=5)
        cls.task_b = cls._create_task('B', day_offset=5, duration_days=10)
        cls.task_c = cls._create_task('C', day_offset=15, duration_days=5)
        cls.task_side = cls._create_task('Paralela corta', day_offset=5, duration_days=1)
        cls.task_b.depend_on_ids = [(6, 0, cls.task_a.ids)]
        cls.task_c.depend_on_ids = [(6, 0, cls.task_b.ids)]
        cls.task_side.depend_on_ids = [(6, 0, cls.task_a.ids)]

    def _payload(self):
        return self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'critical_path': True},
        )

    def test_not_computed_unless_requested(self):
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        self.assertFalse(payload['meta']['critical_path']['computed'])
        self.assertIsNone(self._task_by_id(payload, self.task_a.id).get('slack_hours'))

    def test_chain_is_critical_and_side_task_is_not(self):
        if not self.start_field:
            self.skipTest("Sin fecha de inicio no hay duraciones que encadenar")
        payload = self._payload()
        summary = payload['meta']['critical_path']
        self.assertTrue(summary['computed'])

        for task in (self.task_a, self.task_b, self.task_c):
            row = self._task_by_id(payload, task.id)
            self.assertTrue(row['critical'], f"{task.name} debería estar en la ruta crítica")
            self.assertEqual(row['slack_hours'], 0.0)

        side = self._task_by_id(payload, self.task_side.id)
        self.assertFalse(side['critical'])
        self.assertGreater(side['slack_hours'], 0.0)

    def test_project_finish_matches_last_task(self):
        if not self.start_field:
            self.skipTest("Sin fecha de inicio no hay duraciones que encadenar")
        payload = self._payload()
        self.assertEqual(
            payload['meta']['critical_path']['project_finish'],
            self._task_by_id(payload, self.task_c.id)['end'],
        )

    def test_parent_inherits_critical_from_child(self):
        if not self.start_field:
            self.skipTest("Sin fecha de inicio no hay duraciones que encadenar")
        parent = self._create_task('Contenedora', day_offset=0, duration_days=20)
        self.task_b.parent_id = parent
        payload = self._payload()
        self.assertTrue(self._task_by_id(payload, parent.id)['critical'],
                        "Una tarea contenedora es crítica si lo es alguna hija")
