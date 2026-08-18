# -*- coding: utf-8 -*-
"""La interfaz de backend no tiene lógica propia: lo que hay que garantizar es
que la acción y los menús existen, apuntan al componente correcto y están
restringidos a los grupos del Gantt."""
from odoo.modules.module import get_manifest
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGanttBackendAction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gantt_user = cls.env['res.users'].create({
            'name': 'Usuario con Gantt',
            'login': 'gantt.backend.user@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('al_project_gantt_base.group_gantt_user').id,
            ])],
        })

    def test_client_action_points_to_the_component(self):
        action = self.env.ref('al_project_gantt_backend.action_gantt_backend')
        self.assertEqual(action.type, 'ir.actions.client')
        self.assertEqual(action.tag, 'al_project_gantt.backend')

    def test_menus_are_restricted_to_gantt_groups(self):
        gantt_user = self.env.ref('al_project_gantt_base.group_gantt_user')
        gantt_manager = self.env.ref('al_project_gantt_base.group_gantt_manager')

        root = self.env.ref('al_project_gantt_backend.menu_gantt_root')
        view = self.env.ref('al_project_gantt_backend.menu_gantt_view')
        config = self.env.ref('al_project_gantt_backend.menu_gantt_configuration')

        self.assertIn(gantt_user, root.group_ids)
        self.assertIn(gantt_user, view.group_ids)
        self.assertIn(gantt_manager, config.group_ids)
        self.assertEqual(view.action, self.env.ref('al_project_gantt_backend.action_gantt_backend'))

    def test_menu_is_hidden_for_user_without_group(self):
        plain_user = self.env['res.users'].create({
            'name': 'Interno sin Gantt',
            'login': 'gantt.backend.plain@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        # La visibilidad de menús no se resuelve en el search, sino en
        # _filter_visible_menus() (lo que usa load_menus para el webclient).
        root = self.env.ref('al_project_gantt_backend.menu_gantt_root')
        visible = root.with_user(plain_user)._filter_visible_menus()
        self.assertFalse(visible, "El menú no debe ser visible sin el grupo del Gantt")

        visible = root.with_user(self.gantt_user)._filter_visible_menus()
        self.assertTrue(visible, "Con el grupo del Gantt el menú sí debe verse")

    def test_smart_button_is_on_the_project_form(self):
        """El botón inteligente abre el Gantt acotado a ese proyecto."""
        view = self.env.ref('al_project_gantt_backend.project_project_view_form_gantt_button')
        self.assertEqual(view.inherit_id, self.env.ref('project.edit_project'))
        self.assertIn('action_open_gantt', view.arch)

        project = self.env['project.project'].create({'name': 'Proyecto del botón'})
        action = project.with_user(self.gantt_user).action_open_gantt()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'al_project_gantt.backend')
        self.assertEqual(action['context']['gantt_project_ids'], project.ids)
        self.assertIn(project.display_name, action['name'])

    def test_gantt_task_count_only_counts_dated_tasks(self):
        project = self.env['project.project'].create({'name': 'Contador'})
        field_map = self.env['al.gantt.field.map'].get_map()
        self.env['project.task'].create([
            {'name': 'Con fecha', 'project_id': project.id,
             field_map['date_end']: '2026-11-02 09:00:00'},
            {'name': 'Sin fecha', 'project_id': project.id},
        ])
        project.invalidate_recordset()
        self.assertEqual(project.gantt_task_count, 1)

    def test_library_is_not_in_the_backend_bundle(self):
        """La librería (627 KB) debe cargarse de forma perezosa, no en el bundle."""
        manifest = get_manifest('al_project_gantt_backend')
        bundle = manifest['assets']['web.assets_backend']
        self.assertFalse(
            [path for path in bundle if 'dhtmlxgantt' in path],
            "dhtmlxgantt no debe declararse en web.assets_backend",
        )
        self.assertIn(
            'al_project_gantt_base/static/src/js/gantt_adapter.js', bundle,
            "El adaptador compartido sí debe estar en el bundle",
        )
