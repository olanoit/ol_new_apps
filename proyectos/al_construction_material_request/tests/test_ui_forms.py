# -*- coding: utf-8 -*-
"""Simula la interfaz con ``Form``: ejecuta los mismos onchange que el
navegador, con registros a medio rellenar (líneas sin material ni unidad,
proyectos y tareas sin guardar…)."""
from ast import literal_eval

from odoo import Command
from odoo.tests import Form, tagged

from .common import ConstructionRequestCommon


@tagged('post_install', '-at_install')
class TestUiForms(ConstructionRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Con unidades activas la columna Unidad está en la vista.
        cls.requester.group_ids = [Command.link(cls.env.ref('uom.group_uom').id)]
        cls.logistics.group_ids = [Command.link(cls.env.ref('uom.group_uom').id)]

    def test_new_request_with_half_filled_lines(self):
        """La línea nueva sin material ni unidad no debe romper el onchange."""
        self._set_stock(self.cement, self.stock, 60)
        uom_dozen = self.env.ref('uom.product_uom_dozen')
        Request = self.env['construction.material.request'].with_user(self.requester)
        with Form(Request) as form:
            form.project_id = self.site_a
            with form.line_ids.new() as line:
                # sin material todavía: se recalculan situación, disponible…
                self.assertEqual(line.line_state, 'pending')
                line.product_qty = 3
                line.product_id = self.cement
                self.assertEqual(line.qty_available_now, 60)
                line.product_uom_id = uom_dozen
                self.assertEqual(line.qty_available_now, 5)
            with form.line_ids.new() as line:
                line.product_id = self.steel
                line.product_qty = 0
                self.assertEqual(line.line_state, 'pending')
                line.product_qty = 10
            self.assertEqual(form.amount_estimated, 3 * 12 * 30.0 + 10 * 45.0)
        request = form.record
        self.assertEqual(len(request.line_ids), 2)
        self.assertEqual(request.line_ids[0].product_uom_id, uom_dozen)

    def test_change_project_and_task_on_new_request(self):
        task = self.env['project.task'].create({'name': 'Zapatas (test)', 'project_id': self.site_a.id})
        Request = self.env['construction.material.request'].with_user(self.requester)
        with Form(Request) as form:
            form.project_id = self.site_a
            form.task_id = task
            with form.line_ids.new() as line:
                line.product_id = self.cement
                self.assertEqual(line.task_id, task)
            form.project_id = self.site_b
            self.assertEqual(form.location_dest_id, self.site_b.construction_location_id)
            form.task_id = self.env['project.task']

    def test_new_project_marked_as_site(self):
        with Form(self.env['project.project']) as form:
            form.name = 'Hospital C (test)'
            form.is_construction_site = True
        project = form.record
        self.assertTrue(project.construction_location_id)
        self.assertEqual(project.construction_request_count, 0)

    def test_new_task_form(self):
        Task = self.env['project.task'].with_context(default_project_id=self.site_a.id)
        with Form(Task) as form:
            form.name = 'Columnas (test)'
        self.assertEqual(form.record.construction_request_count, 0)

    def test_settings_form(self):
        with Form(self.env['res.config.settings']) as form:
            self.assertEqual(form.construction_src_location_id, self.stock)
        form.record.execute()

    def test_tier_definition_form_from_action(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_material_request.action_construction_tier_definition')
        TierDefinition = self.env['tier.definition'].with_context(
            **literal_eval(action['context']))
        with Form(TierDefinition) as form:
            form.name = 'Nivel extra (test)'
            form.review_type = 'individual'
            form.reviewer_id = self.approver
        self.assertEqual(form.record.model, 'construction.material.request')

    def test_edit_existing_requests_in_each_state(self):
        self._set_stock(self.cement, self.stock, 60)
        draft = self._new_request(user=self.requester)
        with Form(draft.with_user(self.requester)) as form:
            with form.line_ids.edit(0) as line:
                line.product_qty = 80
            with form.line_ids.new() as line:
                line.product_id = self.steel

        processed = self._new_request(user=self.requester)
        processed.action_request_approval()
        processed.with_user(self.approver).validate_tier()
        processed = processed.with_env(self.env)
        processed.with_user(self.logistics).action_process()
        # logística ajusta la fecha requerida de un requerimiento en proceso
        with Form(processed.with_user(self.logistics)) as form:
            form.date_required = '2026-12-01'
        self.assertEqual(str(processed.date_required), '2026-12-01')
        # el residente abre su requerimiento procesado (solo lectura)
        Form(processed.with_user(self.requester))
