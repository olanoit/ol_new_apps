# -*- coding: utf-8 -*-
"""Línea base: captura inmutable y cálculo del desvío."""
from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import GanttCommon


@tagged('post_install', '-at_install')
class TestGanttBaseline(GanttCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.task_a = cls._create_task('A', day_offset=0, duration_days=2)
        cls.task_b = cls._create_task('B', day_offset=5, duration_days=3)

    def _create_baseline(self, name='Base 1'):
        return self.env(user=self.gantt_user)['al.gantt.data'].create_baseline(
            [self.project.id], name,
        )

    def test_capture_stores_current_dates(self):
        result = self._create_baseline()
        self.assertTrue(result['ok'])
        self.assertEqual(result['baselines'][0]['task_count'], 2)

        baseline = self.env['al.gantt.baseline'].browse(result['baselines'][0]['id'])
        line = baseline.line_ids.filtered(lambda l: l.task_id == self.task_a)
        self.assertEqual(line.date_end, self.task_a[self.end_field])

    def test_baselines_are_listed_in_the_payload(self):
        self._create_baseline('Base para listar')
        payload = self._get_data(user=self.gantt_user, project_ids=[self.project.id])
        names = {baseline['name'] for baseline in payload['baselines']}
        self.assertIn('Base para listar', names)

    def test_variance_after_moving_a_task(self):
        result = self._create_baseline()
        baseline_id = result['baselines'][0]['id']

        self.task_a[self.end_field] = self.task_a[self.end_field] + timedelta(days=3)
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'baseline_id': baseline_id},
        )
        row = self._task_by_id(payload, self.task_a.id)
        self.assertTrue(payload['meta']['baseline']['applied'])
        self.assertEqual(row['baseline_variance_days'], 3.0)

        untouched = self._task_by_id(payload, self.task_b.id)
        self.assertEqual(untouched['baseline_variance_days'], 0.0)

    def test_lines_are_immutable(self):
        result = self._create_baseline()
        baseline = self.env['al.gantt.baseline'].browse(result['baselines'][0]['id'])
        with self.assertRaises(UserError):
            baseline.line_ids[0].write({'date_end': self.base_date})

    def test_unknown_baseline_is_ignored(self):
        payload = self._get_data(
            user=self.gantt_user, project_ids=[self.project.id],
            options={'baseline_id': -1},
        )
        self.assertFalse(payload['meta']['baseline']['applied'])
        self.assertIsNone(self._task_by_id(payload, self.task_a.id)['baseline_end'])
