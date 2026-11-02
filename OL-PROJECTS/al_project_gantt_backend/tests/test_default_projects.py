# -*- coding: utf-8 -*-
"""El Gantt de proyectos no abre con todos los proyectos: abre con la última
selección del usuario o, la primera vez, con el proyecto de actividad más
reciente."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGanttDefaultProjects(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Usuario del Gantt (proyectos)',
            'login': 'gantt.default.projects@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('project.group_project_user').id,
                cls.env.ref('al_project_gantt_base.group_gantt_user').id,
            ])],
        })
        Project = cls.env['project.project']
        cls.old = Project.create({'name': 'Proyecto antiguo (test Gantt)'})
        cls.recent = Project.create({'name': 'Proyecto reciente (test Gantt)'})
        cls.env['project.task'].create({'name': 'Tarea vieja', 'project_id': cls.old.id})
        cls.task = cls.env['project.task'].create({'name': 'Tarea nueva',
                                                   'project_id': cls.recent.id})

    def test_first_time_opens_the_most_active_project(self):
        Project = self.env['project.project'].with_user(self.user)
        # La tarea modificada al final decide (la más nueva, en la misma
        # transacción, desempata por id).
        ids = Project.get_gantt_default_project_ids()
        self.assertEqual(ids, self.recent.ids)

    def test_saved_selection_is_used_and_filtered(self):
        Project = self.env['project.project'].with_user(self.user)
        saved = Project.set_gantt_project_ids([self.old.id, self.recent.id, 999999])
        self.assertEqual(sorted(saved), sorted([self.old.id, self.recent.id]),
                         'solo proyectos que existen y puede ver')
        self.assertEqual(sorted(Project.get_gantt_default_project_ids()),
                         sorted([self.old.id, self.recent.id]))
        # Un proyecto archivado deja de abrirse.
        self.old.active = False
        self.assertEqual(Project.get_gantt_default_project_ids(), self.recent.ids)
