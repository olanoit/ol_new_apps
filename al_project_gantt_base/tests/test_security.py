# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import GanttCommon


@tagged('post_install', '-at_install')
class TestGanttSecurity(GanttCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plain_user = cls.env['res.users'].create({
            'name': 'Interno sin Gantt',
            'login': 'gantt.plain@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal',
            'login': 'gantt.portal@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.task = cls._create_task('Tarea visible', day_offset=0)

    def test_internal_user_without_group_is_rejected(self):
        with self.assertRaises(AccessError):
            self._get_data(user=self.plain_user)

    def test_portal_user_is_rejected(self):
        with self.assertRaises(AccessError):
            self._get_data(user=self.portal_user)

    def test_gantt_user_is_allowed(self):
        payload = self._get_data(user=self.gantt_user)
        self.assertIn('tasks', payload)

    def test_other_company_project_is_not_visible(self):
        """La visibilidad se apoya en las reglas nativas: sin sudo, no hay fuga."""
        other_company = self.env['res.company'].create({'name': 'Compañía B'})
        other_project = self.env['project.project'].create({
            'name': 'Proyecto de la compañía B',
            'company_id': other_company.id,
            'privacy_visibility': 'employees',
        })
        hidden_task = self._create_task('Tarea ajena', project=other_project, day_offset=0)

        payload = self._get_data(user=self.gantt_user)
        project_ids = {project['id'] for project in payload['projects']}
        task_ids = {task['id'] for task in payload['tasks']}
        self.assertNotIn(other_project.id, project_ids)
        self.assertNotIn(hidden_task.id, task_ids)

        # Pedirlo explícitamente tampoco lo revela.
        payload = self._get_data(user=self.gantt_user, project_ids=[other_project.id])
        self.assertEqual(payload['projects'], [])
        self.assertEqual(payload['tasks'], [])

    def test_followers_only_project_is_hidden(self):
        """Proyecto privado (solo seguidores) del que el usuario no es parte."""
        private_project = self.env['project.project'].create({
            'name': 'Proyecto reservado',
            'privacy_visibility': 'followers',
        })
        private_task = self._create_task('Tarea reservada', project=private_project, day_offset=0)

        payload = self._get_data(user=self.gantt_user)
        self.assertNotIn(private_task.id, {task['id'] for task in payload['tasks']})

    def test_state_colors_are_readonly_for_plain_gantt_user(self):
        color = self.env['al.gantt.state.color'].search([], limit=1)
        self.assertTrue(color, "Los colores por defecto deben existir")
        with self.assertRaises(AccessError):
            color.with_user(self.gantt_user).write({'color': '#000000'})
