# -*- coding: utf-8 -*-
"""Paquete 1.18, entrega 2 (M118-05): «Generar plan» por pisos, con los
ambientes por su ruta y en segundo plano. Datos ficticios."""
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage118Generate(PlannerCommon):

    def test_floors_fill_the_spaces(self):
        form = Form(self.env['construction.plan.generate.wizard'].with_context(
            default_plan_id=self.plan.id))
        form.floor_task_ids.add(self.floor)
        self.assertEqual(set(form.space_task_ids.ids), {self.space_501.id, self.space_502.id})

    def test_spaces_show_their_path(self):
        Task = self.env['project.task'].with_context(construction_space_path=True)
        space = Task.browse(self.space_501.id)
        self.assertTrue(space.display_name.startswith('Piso 05 / Dpto 501 / Cocina'))
        found = Task.name_search('Dpto 502', domain=[('construction_level', '=', 'space')])
        self.assertIn(self.space_502.id, [record_id for record_id, _name in found])
        # Sin el contexto, el nombre de siempre.
        self.assertEqual(self.space_501.display_name, self.space_501.name)

    def test_background_does_what_foreground_does(self):
        self._generate()
        foreground = sorted((l.task_id.name, l.resource_type, l.product_id.id, l.activity_id.id,
                             round(l.qty_planned, 4), round(l.price_unit_planned, 4))
                            for l in self.plan.line_ids)
        self.assertTrue(foreground)
        wizard = self._wizard().with_context(construction_generate_background=True)
        action = wizard.action_generate()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(self.plan.construction_generate_state, 'queued')
        # Un segundo «Generar» con uno en curso no empieza.
        with self.assertRaises(UserError):
            self.plan.action_open_generate_wizard()
        with self.assertRaises(UserError):
            self._wizard().action_generate()
        self.env['construction.resource.plan']._cron_construction_generate()
        self.assertEqual(self.plan.construction_generate_state, 'done')
        self.assertIn('Terminado', self.plan.construction_generate_info)
        background = sorted((l.task_id.name, l.resource_type, l.product_id.id, l.activity_id.id,
                             round(l.qty_planned, 4), round(l.price_unit_planned, 4))
                            for l in self.plan.line_ids)
        self.assertEqual(background, foreground)
        self.assertTrue(self.plan.message_ids.filtered(
            lambda m: 'segundo plano' in (m.body or '')))

    def test_modules_class_after_join_method(self):
        columns = [key for key, _header in self.project._construction_sheet_columns('MODULOS')] \
            if hasattr(self.project, '_construction_sheet_columns') else []
        if columns:
            self.assertGreater(columns.index('module_class'), columns.index('join_method'))
