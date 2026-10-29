# -*- coding: utf-8 -*-
"""Grupos en dos ejes (requerimiento CREVAL v1.0, capítulo 5): ejes
independientes, controles de cada eje y migración sin pérdida de permisos."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_construction_planner.models.common import migrate_axis_groups

G = 'al_construction_planner.group_planner_'


@tagged('post_install', '-at_install')
class TestAxisGroups(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['project.project'].create({
            'name': 'Obra de los dos ejes (test)', 'is_construction_site': True})
        template = cls.env['construction.level.template'].create({
            'name': 'Especialidad y partida (test)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Partida', 'role': 'space'})]})
        cls.project.construction_level_template_id = template
        lines = template.line_ids.sorted('sequence')
        specialty = cls.env['project.task'].create({
            'name': 'Arquitectura (test)', 'project_id': cls.project.id,
            'construction_level_line_id': lines[0].id})
        cls.task = cls.env['project.task'].create({
            'name': 'Partida 01 (test)', 'project_id': cls.project.id,
            'parent_id': specialty.id, 'construction_level_line_id': lines[1].id})
        cls.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False
        cls.product = cls.env['product.product'].create({'name': 'Cemento (test)'})
        cls.plan = cls.env['construction.resource.plan'].create({'project_id': cls.project.id})
        cls.env['construction.resource.plan.line'].create({
            'plan_id': cls.plan.id, 'task_id': cls.task.id, 'resource_type': 'material',
            'product_id': cls.product.id, 'product_uom_id': cls.product.uom_id.id,
            'qty_planned': 10.0, 'price_unit_planned': 25.0})

    def _user(self, login, groups):
        return new_test_user(self.env, login, groups=','.join(G + g for g in groups))

    # ------------------------------------------------------------------
    # Grupos
    # ------------------------------------------------------------------
    def test_ladders_and_privileges(self):
        plan_privilege = self.env.ref(
            'al_construction_planner.res_groups_privilege_construction_plan')
        exec_privilege = self.env.ref(
            'al_construction_planner.res_groups_privilege_construction_planner')
        self.assertEqual(plan_privilege.group_ids.mapped(lambda g: g.get_external_id()[g.id]),
                         [G + 'plan_viewer', G + 'plan_planner', G + 'plan_approver'])
        # Los puentes pueden sumar roles al eje (p. ej. la jefatura de
        # producción); la escalera del núcleo va primero.
        self.assertEqual(
            exec_privilege.group_ids.mapped(lambda g: g.get_external_id()[g.id])[:4],
            [G + 'progress', G + 'user', G + 'exec_validator', G + 'exec_approver'])
        # El grupo anterior y la jefatura salen de las selecciones.
        self.assertFalse(self.env.ref(G + 'planner').privilege_id)
        self.assertFalse(self.env.ref(G + 'project_head').privilege_id)

    def test_axes_are_independent(self):
        executor = self._user('eje_solo_ejecucion', ['exec_validator'])
        planner = self._user('eje_solo_plan', ['plan_planner'])
        self.assertTrue(executor.has_group(G + 'plan_viewer'))
        self.assertFalse(executor.has_group(G + 'plan_planner'))
        self.assertFalse(planner.has_group(G + 'user'))
        self.assertFalse(planner.has_group(G + 'progress'))
        admin = self._user('eje_admin', ['manager'])
        for group in ('plan_approver', 'exec_approver', 'amounts', 'revenue'):
            self.assertTrue(admin.has_group(G + group), group)

    def test_compatibility_groups(self):
        old = self._user('eje_planificador_anterior', ['planner'])
        self.assertTrue(old.has_group(G + 'plan_planner'))
        self.assertTrue(old.has_group(G + 'exec_validator'))
        head = self._user('eje_jefatura', ['project_head'])
        self.assertTrue(head.has_group(G + 'plan_approver'))
        self.assertTrue(head.has_group(G + 'exec_approver'))

    # ------------------------------------------------------------------
    # Controles
    # ------------------------------------------------------------------
    def test_executor_cannot_edit_draft_plan(self):
        executor = self._user('eje_ejecuta', ['user'])
        line = self.plan.line_ids.with_user(executor)
        self.assertEqual(line.qty_planned, 10.0)
        with self.assertRaises(UserError):
            line.qty_planned = 12.0
        with self.assertRaises(UserError):
            self.plan.with_user(executor).exceed_tolerance = 5.0
        planner = self._user('eje_planifica', ['plan_planner'])
        self.plan.line_ids.with_user(planner).qty_planned = 12.0
        self.assertEqual(self.plan.amount_material, 300.0)

    def test_executor_marks_approved_plan_in_progress(self):
        stage = self.env['construction.stage'].create({
            'name': 'Obra gruesa (test)', 'code': 'axis_test_stage', 'sequence': 900})
        self.plan.line_ids.with_context(construction_plan_force=True).stage = stage.code
        self.plan.action_request_approval()
        self.assertEqual(self.plan.state, 'approved')
        executor = self._user('eje_ejecuta2', ['user'])
        self.plan.with_user(executor)._mark_in_progress()
        self.assertEqual(self.plan.state, 'in_progress')

    def test_validation_needs_exec_validator(self):
        executor = self._user('eje_reporta', ['user'])
        validator = self._user('eje_valida', ['exec_validator'])
        progress = self.env['construction.task.progress'].new({})
        with self.assertRaises(UserError):
            progress.with_user(executor)._check_validator()
        progress.with_user(validator)._check_validator()
        # Plan: aprueba no valida la ejecución.
        approver = self._user('eje_aprueba_plan', ['plan_approver'])
        with self.assertRaises(UserError):
            progress.with_user(approver)._check_validator()

    # ------------------------------------------------------------------
    # Migración (5.3)
    # ------------------------------------------------------------------
    def _snapshot(self, user):
        """Permisos efectivos del usuario en los modelos de la vertical y
        los menús que ve."""
        models = [name for name in self.env if name.startswith('construction.')]
        perms = {(model, mode) for model in models for mode in ('read', 'write', 'create', 'unlink')
                 if self.env[model].with_user(user).has_access(mode)}
        menus = set(self.env['ir.ui.menu'].with_user(user)._visible_menu_ids())
        return perms, menus

    def test_migration_keeps_permissions(self):
        profiles = {
            'mig_reporta': ['progress'],
            'mig_usuario': ['user'],
            'mig_planificador': ['planner'],
            'mig_jefatura': ['project_head'],
            'mig_admin': ['manager'],
            'mig_ingresos': ['revenue'],
            'mig_asistente': ['assistant'],
        }
        users = {login: self._user(login, groups) for login, groups in profiles.items()}
        # Un menú que en la base solo cita al Planificador anterior (versiones
        # viejas o hecho a mano) y las entradas a la ejecución sin activar.
        legacy_menu = self.env['ir.ui.menu'].create({
            'name': 'Menú anterior (test)',
            'parent_id': self.env.ref('al_construction_planner.menu_planner_reports_plan').id,
            'action': 'ir.actions.act_window,%s' % self.env.ref(
                'al_construction_planner.action_construction_resource_plan_line_analysis').id,
            'group_ids': [Command.set(self.env.ref(G + 'planner').ids)]})
        internal = self.env.ref('base.group_user')
        feature = self.env.ref(G + 'feature_exec_planner')
        internal.implied_ids = [Command.unlink(feature.id)]
        self.env.transaction.invalidate_ormcache()
        before = {login: self._snapshot(user) for login, user in users.items()}
        tier = self.env['tier.definition'].create({
            'name': 'Plan (test)', 'model_id': self.env.ref(
                'al_construction_planner.model_construction_resource_plan').id,
            'review_type': 'group', 'reviewer_group_id': self.env.ref(G + 'project_head').id})
        migrate_axis_groups(self.env)
        self.env.transaction.invalidate_ormcache()
        for login, user in users.items():
            user.invalidate_recordset()
            perms, menus = self._snapshot(user)
            self.assertLessEqual(before[login][0], perms, login)
            self.assertLessEqual(before[login][1], menus, login)
        self.assertIn(self.env.ref(G + 'plan_planner'), legacy_menu.group_ids)
        self.assertIn(feature, internal.implied_ids)
        planner = users['mig_planificador']
        self.assertNotIn(self.env.ref(G + 'planner'), planner.group_ids)
        self.assertIn(self.env.ref(G + 'plan_planner'), planner.group_ids)
        self.assertIn(self.env.ref(G + 'exec_validator'), planner.group_ids)
        head = users['mig_jefatura']
        self.assertIn(self.env.ref(G + 'project_head'), head.group_ids)
        self.assertIn(self.env.ref(G + 'exec_approver'), head.group_ids)
        # La regla del plan que revisaba la jefatura pasa a Plan: aprueba, y sus
        # revisores siguen siendo los mismos.
        self.assertEqual(tier.reviewer_group_id, self.env.ref(G + 'plan_approver'))
        self.assertIn(head, tier.reviewer_group_id.user_ids)
        # Ajustar un eje no toca el otro: se baja la ejecución del planificador
        # migrado y conserva el plan.
        planner.group_ids = [Command.unlink(self.env.ref(G + 'exec_validator').id)]
        self.assertFalse(planner.has_group(G + 'exec_validator'))
        self.assertTrue(planner.has_group(G + 'plan_planner'))
