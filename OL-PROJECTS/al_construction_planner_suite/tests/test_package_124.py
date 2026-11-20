# -*- coding: utf-8 -*-
from unittest.mock import patch

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, HttpCase, new_test_user, tagged

from .common import PlannerCommon


class Package124Common(PlannerCommon):
    """Obra de dos pisos con ambientes de dos familias (cocina y closet) y uno
    sin tipología, plan vigente y un usuario que pide material y no es
    administrador."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.requester = new_test_user(
            cls.env, 'rq124_jefatura', name='Jefatura de proyectos (test)',
            groups='al_construction_material_request.group_construction_requester,'
                   'project.group_project_user')
        tier_exceed = cls.env.ref('al_construction_planner_purchase.tier_material_request_exceed')
        cls.env['tier.definition'].search([
            ('model', '=', 'construction.material.request'),
            ('id', '!=', tier_exceed.id)]).active = False
        cls.company._al_construction_ensure_setup()
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        cls.project.message_subscribe(partner_ids=cls.requester.partner_id.ids)
        # Cuentas Rubro de las dos familias: van a la línea del plan.
        rubro_plan = cls.env['account.analytic.plan'].create({'name': 'Rubro (test 1.24)'})
        cls.rubro = {}
        for family, name in (('kitchen', 'Cocina'), ('closet', 'Closet')):
            cls.rubro[family] = cls.env['account.analytic.account'].create({
                'name': 'Rubro %s (test)' % name, 'plan_id': rubro_plan.id,
                'company_id': cls.company.id})
            cls.env['construction.rubro.account'].search([
                ('company_id', '=', cls.company.id), ('family', '=', family)]).unlink()
            cls.env['construction.rubro.account'].create({
                'company_id': cls.company.id, 'family': family,
                'account_id': cls.rubro[family].id})
        # Dos pisos y ambientes de dos familias, más uno sin tipología.
        cls.closet_typology = cls.typology.copy({
            'code': 'CL-09', 'name': 'Closet 09', 'family': 'closet'})
        cls.closet_501 = cls.task('Closet 2', 'space', cls.apt_501,
                                  construction_typology_id=cls.closet_typology.id)
        cls.store_502 = cls.task('Depósito', 'space', cls.apt_502)
        cls.floor_6 = cls.task('Piso 06', 'floor')
        cls.apt_601 = cls.task('Dpto 601', 'apartment', cls.floor_6)
        cls.space_601 = cls.task('Cocina', 'space', cls.apt_601,
                                 construction_typology_id=cls.typology.id)
        cls.closet_601 = cls.task('Closet 1', 'space', cls.apt_601,
                                  construction_typology_id=cls.closet_typology.id)
        wizard = cls.env['construction.plan.generate.wizard'].create({'plan_id': cls.plan.id})
        wizard.action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state
        cls.stage_assembly = cls.env['construction.stage'].search([('code', '=', 'assembly')])

    def _new_request(self):
        return self.env['construction.material.request'].with_user(self.requester).create({
            'project_id': self.project.id})

    def _hinge_qty(self, spaces):
        return sum(line._qty_to_product_uom(line.qty_planned) for line in self.plan.line_ids
                   if line.product_id == self.p_hinge and line.stage == 'assembly'
                   and line.space_task_id in spaces)

    def _hinges(self, request):
        return request.line_ids.filtered(lambda l: l.product_id == self.p_hinge)

    def _accounts(self, line):
        self.assertEqual(len(line.analytic_distribution or {}), 1, line.analytic_distribution)
        return {int(i) for i in next(iter(line.analytic_distribution)).split(',')}


@tagged('post_install', '-at_install')
class TestPackage124(Package124Common):
    """Paquete 1.24: tipo de ambiente en el alcance del requerimiento de obra
    (M124-01), ambiente con su camino (M124-02), orientación «?» por nivel
    (M124-03) y cabecera sin la pestaña «Otra información» (M124-04)."""

    # ------------------------------------------------------------------
    # M124-01 · tipo de ambiente
    # ------------------------------------------------------------------
    def test_type_options_follow_scope(self):
        request = self._new_request()
        self.assertEqual(request.construction_scope_type_label, 'Tipo de ambiente')
        # El tipo va antes del selector del ambiente (el tercero).
        self.assertEqual(request.construction_scope_type_depth, 3)
        self.assertEqual(
            [(o['label'], o['count']) for o in request.construction_scope_type_options],
            [('Closet', 2), ('Cocina', 3), ('Sin tipo', 1)])
        self.assertIn('Cocina, Closet', request.construction_scope_type_hint)
        request.construction_scope_1_ids = self.floor_6
        self.assertEqual(
            [(o['label'], o['count']) for o in request.construction_scope_type_options],
            [('Closet', 1), ('Cocina', 1)])
        # «Ambiente» ofrece solo los de los tipos elegidos.
        request.construction_scope_1_ids = self.floor
        request.construction_scope_type_keys = ['closet']
        self.assertEqual(request.construction_scope_3_allowed_ids, self.closet_501)
        request.construction_scope_type_keys = ['_none']
        self.assertEqual(request.construction_scope_3_allowed_ids, self.store_502)
        request.construction_scope_type_keys = False
        self.assertEqual(request.construction_scope_3_allowed_ids,
                         self.space_501 | self.space_502 | self.closet_501 | self.store_502)

    def test_type_onchange_drops_what_no_longer_fits(self):
        request = self._new_request()
        request.write({'construction_scope_1_ids': [Command.set(self.floor.ids)],
                       'construction_scope_3_ids': [Command.set(self.space_501.ids)]})
        with Form(request.with_user(self.requester)) as form:
            form.construction_scope_type_keys = ['closet']
        # La cocina elegida ya no es de los tipos elegidos.
        self.assertFalse(request.construction_scope_3_ids)
        # Un tipo que el piso elegido no tiene sale de la elección.
        request.construction_scope_type_keys = ['closet', '_none']
        with Form(request.with_user(self.requester)) as form:
            form.construction_scope_1_ids.clear()
            form.construction_scope_1_ids.add(self.floor_6)
        self.assertEqual(request.construction_scope_type_keys, ['closet'])

    def test_fetch_one_type(self):
        request = self._new_request()
        request.write({'construction_scope_1_ids': [Command.set(self.floor.ids)],
                       'construction_stage_ids': [Command.set(self.stage_assembly.ids)],
                       'construction_scope_type_keys': ['kitchen']})
        self.assertEqual(
            request.construction_fetch_summary,
            'Se traerá el saldo del plan de 2 ambientes de Piso 05: 2 cocinas, etapa %s.'
            % self.stage_assembly.name)
        request.action_construction_fetch_plan()
        hinge = self._hinges(request)
        self.assertEqual(len(hinge), 1)
        self.assertEqual(hinge.task_id, self.floor)
        self.assertEqual(hinge.construction_space_type, 'Cocina')
        self.assertEqual(hinge.product_qty, self._hinge_qty(self.space_501 | self.space_502))
        self.assertEqual(set(request.line_ids.mapped('construction_space_type')), {'Cocina'})
        # Analítica: la obra y el Rubro de su tipo.
        accounts = self._accounts(hinge)
        self.assertIn(self.rubro['kitchen'].id, accounts)
        self.assertIn(self.project.account_id.id, accounts)
        self.assertNotIn(self.rubro['closet'].id, accounts)
        self.assertEqual(set(hinge.construction_allocation_ids.plan_line_id.space_task_id.ids),
                         {self.space_501.id, self.space_502.id})

    def test_fetch_two_types_and_no_repeat(self):
        request = self._new_request()
        request.write({'construction_scope_1_ids': [Command.set(self.floor.ids)],
                       'construction_stage_ids': [Command.set(self.stage_assembly.ids)],
                       'construction_scope_type_keys': ['kitchen', 'closet']})
        self.assertIn('3 ambientes de Piso 05: 1 closet y 2 cocinas',
                      request.construction_fetch_summary)
        request.action_construction_fetch_plan()
        hinges = self._hinges(request).sorted('construction_space_type')
        self.assertEqual(hinges.mapped('construction_space_type'), ['Closet', 'Cocina'])
        self.assertEqual(hinges.mapped('product_qty'), [
            self._hinge_qty(self.closet_501), self._hinge_qty(self.space_501 | self.space_502)])
        self.assertIn(self.rubro['closet'].id, self._accounts(hinges[0]))
        self.assertIn(self.rubro['kitchen'].id, self._accounts(hinges[1]))
        # Pulsar otra vez no repite líneas.
        count = len(request.line_ids)
        with self.assertRaises(UserError):
            request.action_construction_fetch_plan()
        self.assertEqual(len(request.line_ids), count)
        # Una línea borrada vuelve sola, con su tipo.
        hinges[0].unlink()
        request.action_construction_fetch_plan()
        self.assertEqual(len(request.line_ids), count)

    def test_fetch_one_line_per_floor_and_type(self):
        """Decisión del 20-nov-2026: con varios pisos, una línea por material,
        etapa, tipo y piso."""
        request = self._new_request()
        request.write({
            'construction_scope_1_ids': [Command.set((self.floor | self.floor_6).ids)],
            'construction_stage_ids': [Command.set(self.stage_assembly.ids)],
            'construction_scope_type_keys': ['kitchen']})
        request.action_construction_fetch_plan()
        hinges = self._hinges(request).sorted(lambda l: l.task_id.name)
        self.assertEqual(hinges.task_id, self.floor | self.floor_6)
        self.assertEqual(hinges.mapped('product_qty'), [
            self._hinge_qty(self.space_501 | self.space_502), self._hinge_qty(self.space_601)])

    def test_fetch_without_types_as_before(self):
        request = self._new_request()
        request.write({'construction_scope_1_ids': [Command.set(self.floor.ids)],
                       'construction_stage_ids': [Command.set(self.stage_assembly.ids)]})
        request.action_construction_fetch_plan()
        hinge = self._hinges(request)
        self.assertEqual(len(hinge), 1)
        self.assertFalse(hinge.construction_space_type)
        self.assertEqual(hinge.task_id, self.floor)
        self.assertEqual(hinge.product_qty, self._hinge_qty(
            self.space_501 | self.space_502 | self.closet_501))

    def test_no_selector_without_vertical_types(self):
        """Sin puente que dé tipos (construcción por partidas), el selector no
        aparece y el formulario funciona como antes."""
        Task = type(self.env['project.task'])
        with patch.object(Task, '_construction_space_types', lambda tasks: {}):
            request = self._new_request()
            self.assertFalse(request.construction_scope_type_depth)
            self.assertFalse(request.construction_scope_type_options)
            self.assertFalse(request.construction_scope_type_label)
            request.write({'construction_scope_1_ids': [Command.set(self.floor.ids)],
                           'construction_stage_ids': [Command.set(self.stage_assembly.ids)]})
            self.assertEqual(
                request.construction_fetch_summary,
                'Se traerá el saldo del plan de 4 ambientes de Piso 05, etapa %s.'
                % self.stage_assembly.name)
            request.action_construction_fetch_plan()
            self.assertEqual(len(self._hinges(request)), 1)

    # ------------------------------------------------------------------
    # M124-02 · ambiente con su camino
    # ------------------------------------------------------------------
    def test_scope_names_and_search(self):
        Task = self.env['project.task'].with_user(self.requester)
        scope = Task.with_context(construction_scope_path=True)
        self.assertEqual(scope.browse(self.closet_501.id).display_name,
                         'Piso 05 · Dpto 501 · Closet 2 · CL-09')
        self.assertEqual(scope.browse(self.apt_501.id).display_name, 'Piso 05 · Dpto 501')
        self.assertEqual(scope.browse(self.store_502.id).display_name,
                         'Piso 05 · Dpto 502 · Depósito')
        self.assertEqual(Task.browse(self.closet_501.id).construction_scope_short_name,
                         'Dpto 501 · Closet 2')
        # El nombre de la tarea no cambia fuera de los selectores.
        self.assertNotIn('·', Task.browse(self.closet_501.id).display_name)
        spaces = [('project_id', '=', self.project.id), ('construction_level', '=', 'space')]
        found = dict(scope.name_search('501', spaces))
        self.assertEqual(set(found), {self.space_501.id, self.closet_501.id})
        found = dict(scope.name_search('CL-09', spaces))
        self.assertEqual(set(found), {self.closet_501.id, self.closet_601.id})
        # Ninguna opción se repite con el mismo texto.
        names = [name for _id, name in scope.name_search('', spaces, limit=100)]
        self.assertEqual(len(names), len(set(names)))

    # ------------------------------------------------------------------
    # M124-03 · orientación por nivel
    # ------------------------------------------------------------------
    def test_hint_without_and_with_template(self):
        request = self._new_request()
        self.assertEqual(request.construction_scope_1_label, 'Piso')
        self.assertIn('Puede elegir varios', request.construction_scope_1_hint)
        self.assertIn('Departamentos de lo elegido arriba', request.construction_scope_2_hint)
        self.assertIn('Ambientes puntuales', request.construction_scope_3_hint)
        template = self.env['construction.level.template'].create({
            'name': 'Edificio (test 1.24)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Piso', 'role': 'group',
                        'request_hint': 'Pisos de la torre. Vacío: todos.'}),
                (0, 0, {'sequence': 2, 'name': 'Departamento', 'role': 'unit'}),
                (0, 0, {'sequence': 3, 'name': 'Ambiente', 'role': 'space'})]})
        self.assertIn('Departamentos', template.line_ids[1].request_hint_default)
        self.project.construction_level_template_id = template
        request = self._new_request()
        self.assertEqual(request.construction_scope_1_hint, 'Pisos de la torre. Vacío: todos.')
        self.assertIn('Departamentos de lo elegido arriba', request.construction_scope_2_hint)
        # Cambiar la orientación en la plantilla cambia el texto del requerimiento.
        template.line_ids[0].request_hint = 'Otro texto.'
        request.invalidate_recordset()
        self.assertEqual(request.construction_scope_1_hint, 'Otro texto.')

    # ------------------------------------------------------------------
    # M124-04 · cabecera
    # ------------------------------------------------------------------
    def test_header_without_other_tab(self):
        self.requester.group_ids = [
            Command.link(self.env.ref('stock.group_stock_multi_locations').id),
            Command.link(self.env.ref('analytic.group_analytic_accounting').id)]
        Request = self.env['construction.material.request'].with_user(self.requester)
        arch = etree.fromstring(Request.get_view(view_type='form')['arch'])
        self.assertFalse(arch.xpath("//page[@name='other']"))
        self.assertFalse(arch.xpath('//notebook'))
        site = arch.xpath("//group[@name='site']")[0]
        for name in ('location_src_id', 'analytic_distribution'):
            self.assertTrue(site.xpath("field[@name='%s']" % name), name)
        manager = arch.xpath("//group[@name='dates']/field[@name='project_manager_id']")[0]
        self.assertEqual(manager.get('invisible'), "request_type == 'internal'")
        self.assertTrue(arch.xpath("//field[@name='note']"))
        # Quien pide ve el almacén y no lo puede cambiar.
        request = self._new_request()
        other = self.env['stock.location'].create({
            'name': 'Otro almacén (test)', 'usage': 'internal',
            'location_id': request.location_src_id.location_id.id})
        with self.assertRaises(AssertionError):
            with Form(request) as form:
                form.location_src_id = other
        with Form(request) as form:
            form.note = '<p>Ingreso por la puerta de servicio</p>'
        self.assertIn('puerta de servicio', request.note)


@tagged('post_install', '-at_install')
class TestPackage124Screen(Package124Common, HttpCase):
    """Prueba de pantalla: el recorrido del formulario, clic a clic, con un
    usuario que pide material (no administrador)."""

    def test_request_scope_tour(self):
        self.requester.write({
            'company_ids': [Command.link(self.env.company.id)],
            'company_id': self.env.company.id})
        self.start_tour(
            '/odoo/action-al_construction_material_request.action_construction_material_request',
            'al_construction_request_scope_124', login='rq124_jefatura')
        request = self.env['construction.material.request'].search(
            [('project_id', '=', self.project.id)], order='id desc', limit=1)
        self.assertEqual(request.construction_scope_type_keys, ['kitchen'])
        hinge = request.line_ids.filtered(lambda l: l.product_id == self.p_hinge)
        self.assertEqual(hinge.construction_space_type, 'Cocina')
        self.assertEqual(hinge.task_id, self.floor)
