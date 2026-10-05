# -*- coding: utf-8 -*-
"""Base común de los tests: los datos se construyen a partir del mapeo de
campos detectado, para que la suite pase igual con o sin ``project_enterprise``
(que es quien aporta ``planned_date_begin``) y con o sin ``hr_timesheet``.
"""
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase


class GanttCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.field_map = cls.env['al.gantt.field.map'].get_map()
        cls.start_field = cls.field_map['date_start']
        cls.end_field = cls.field_map['date_end']
        cls.base_date = datetime(2026, 3, 2, 8, 0, 0)  # lunes

        cls.gantt_user = cls.env['res.users'].create({
            'name': 'Gantt Tester',
            'login': 'gantt.tester@example.com',
            'email': 'gantt.tester@example.com',
            # Odoo 19: res.users.groups_id pasó a llamarse group_ids.
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('al_project_gantt_base.group_gantt_user').id,
            ])],
        })

        cls.project = cls.env['project.project'].create({
            'name': 'Gantt — Proyecto de prueba',
            'allow_milestones': True,
            'privacy_visibility': 'employees',
        })

    @classmethod
    def _task_dates(cls, day_offset=0, duration_days=2, with_start=True):
        """Valores de fecha según el mapeo detectado."""
        values = {}
        start = cls.base_date + timedelta(days=day_offset)
        end = start + timedelta(days=duration_days)
        if cls.start_field and with_start:
            values[cls.start_field] = start
        if cls.end_field:
            values[cls.end_field] = end
        return values

    @classmethod
    def _create_task(cls, name, project=None, day_offset=0, duration_days=2,
                     with_start=True, **extra):
        values = {
            'name': name,
            'project_id': (project or cls.project).id,
        }
        values.update(cls._task_dates(day_offset, duration_days, with_start))
        values.update(extra)
        return cls.env['project.task'].create(values)

    def _get_data(self, user=None, project_ids=None, options=None):
        env = self.env(user=user) if user else self.env
        return env['project.project'].get_gantt_data(
            project_ids=project_ids, options=options,
        )

    @staticmethod
    def _task_by_id(payload, task_id):
        return next((task for task in payload['tasks'] if task['id'] == task_id), None)
