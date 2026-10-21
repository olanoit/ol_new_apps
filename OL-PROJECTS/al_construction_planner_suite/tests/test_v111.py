# -*- coding: utf-8 -*-
"""Correcciones de la prueba Montecarmelo (paquete 1.11, M111-02 a M111-06):
asistente de rechazo que abre en el navegador, operación por etapa en las
listas del importador, plan y lista sin exceso por redondeo, el % de exceso
del documento en Aprobaciones y las cifras de la solicitud con líneas del
plan ya asignadas."""
import ast

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged

from .common import PlannerCommon
from .test_approvals_v19 import TestApprovalsPlan, TestApprovalsRequest
from .test_production_excess_v19 import TestProductionExcess
from .test_request_scope import TestRequestScope
from .test_stage_chain_v110 import TestStageChainV110

# Funciones que el evaluador de expresiones del navegador sí tiene
# (web/static/src/core/py_js/py_builtin.js).
CLIENT_FUNCTIONS = {'bool', 'set', 'max', 'min', 'context_today', 'relativedelta'}
MODIFIERS = ('invisible', 'readonly', 'required', 'column_invisible')


@tagged('post_install', '-at_install')
class TestViewExpressionsV111(TransactionCase):
    """M111-02: ninguna vista del planificador usa en sus modificadores una
    función que el navegador no conoce (``len`` rompía el asistente)."""

    def test_modifiers_only_use_client_functions(self):
        data = self.env['ir.model.data'].search([
            ('model', '=', 'ir.ui.view'), ('module', '=like', 'al_construction%')])
        views = self.env['ir.ui.view'].browse(data.mapped('res_id')).exists()
        self.assertTrue(views)
        wrong = []
        for view in views:
            if view.type == 'qweb':
                continue
            for node in etree.fromstring(view.arch_db.encode()).iter():
                for attribute in MODIFIERS:
                    expression = node.get(attribute)
                    if not expression or expression in ('1', '0', 'True', 'False'):
                        continue
                    for item in ast.walk(ast.parse(expression.strip(), mode='eval')):
                        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) \
                                and item.func.id not in CLIENT_FUNCTIONS:
                            wrong.append('%s: %s="%s"' % (view.xml_id, attribute, expression))
        self.assertFalse(wrong, '\n'.join(wrong))


@tagged('post_install', '-at_install')
class TestApprovalsV111(TestApprovalsRequest):

    def _quantity_change(self, extra=2, space=None):
        request = self._fetched(space)
        self._hinge(request).product_qty += extra
        return self._submit(request)

    def _refuse_form(self, approvals):
        return Form(self.env['construction.approval.refuse.wizard'].with_user(
            self.technical).with_context(active_model='approval.request',
                                         active_ids=approvals.ids))

    def test_refuse_wizard_opens_with_one_and_two(self):
        """M111-02: desde el formulario (una) y desde la lista (dos)."""
        first = self._quantity_change()
        second = self._quantity_change(space=self.space_502)
        one = first.construction_approval_id
        action = one.with_user(self.technical).action_construction_refuse()
        wizard = self.env[action['res_model']].with_user(self.technical).with_context(
            action['context']).create({'reason': 'Sin motivo de exceso (test)'})
        self.assertEqual(wizard.approval_count, 1)
        both = one | second.construction_approval_id
        with self._refuse_form(both) as form:
            self.assertEqual(form.approval_count, 2)
            form.reason = 'Use las bisagras del plan (test v111)'
        form.record.action_refuse()
        self.assertEqual(set(both.mapped('request_status')), {'refused'})

    def test_figures_with_assigned_plan_lines(self):
        """M111-06: el segundo pedido del mismo material ya tiene asignada una
        parte del plan; sus cifras siguen siendo las de todo el nivel."""
        planned = self._hinge_qty(self.floor)
        first = self._new_request()
        self._scope(first, floors=self.floor, stages=self.stage_assembly)
        first.action_construction_fetch_plan()
        self._hinge(first).product_qty += 24
        self._submit(first)
        first.with_user(self.head).action_construction_approve()
        self.assertEqual(first.state, 'approved')
        second = self._new_request()
        self._scope(second, floors=self.floor, stages=self.stage_assembly)
        second.write({'line_ids': [Command.create({
            'product_id': self.p_hinge.id, 'product_qty': 20,
            'task_id': self.floor.id, 'construction_stage': 'assembly'})]})
        self._submit(second)
        hinge = second.line_ids.sudo()
        assigned = hinge.construction_allocation_ids.plan_line_id
        scope = hinge._construction_scope_plan_lines(self.plan.sudo())
        self.assertLess(len(assigned), len(scope), 'solo una parte del plan asignada')
        line = second.construction_approval_id.product_line_ids
        self.assertEqual(line.construction_qty_planned, planned)
        self.assertEqual(line.construction_qty_requested_before, planned + 24)
        self.assertEqual(line.construction_qty_budget, -24)
        self.assertEqual(line.quantity, 20)
        self.assertEqual(line.construction_qty_diff, 20)
        self.assertAlmostEqual(line.construction_diff_pct, 20 / planned * 100)


@tagged('post_install', '-at_install')
class TestPlanPctV111(TestApprovalsPlan):
    """La solicitud de una versión nueva del plan muestra 0 %: lo que sube
    frente a la versión vigente solo elige los tramos."""

    def test_new_version_shows_zero_pct(self):
        self._generate()
        lines = self.plan.line_ids
        lines.filtered(lambda l: not l.stage).stage = 'production'
        for line in lines.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        self.plan.action_request_approval()
        self.plan.with_user(self.head).action_construction_approve()
        wizard = self.env['construction.plan.replan.wizard'].create(
            {'plan_id': self.plan.id, 'reason': 'Más costo (test v111)'})
        new = self.env['construction.resource.plan'].browse(
            wizard.action_create_version()['res_id'])
        new.line_ids[:1].price_unit_planned += 1000.0
        self.assertGreater(new._construction_approval_info()['values']['all']['percent'], 0.0)
        new.action_request_approval()
        approval = new.construction_approval_id
        self.assertTrue(approval)
        self.assertEqual(approval.construction_excess_pct, 0.0)


@tagged('post_install', '-at_install')
class TestProductionPctV111(TestProductionExcess):
    """M111-05: la solicitud muestra el % de la orden, con la base del margen
    de la compañía."""

    def _requested(self):
        production = self._production()
        self._move(production, self.p_hinge).product_uom_qty += 10
        production.action_confirm()
        production.with_user(self.head).action_construction_request_excess_approval()
        return production, production.construction_approval_id

    def test_pct_by_order(self):
        production, approval = self._requested()
        hinge = approval.product_line_ids.filtered(lambda l: l.product_id == self.p_hinge)
        self.assertAlmostEqual(hinge.construction_diff_pct, 50.0)
        self.assertLess(production.construction_excess_pct, 50.0)
        self.assertAlmostEqual(approval.construction_excess_pct,
                               production.construction_excess_pct, places=2)

    def test_pct_by_material(self):
        self.company.construction_production_margin_basis = 'material'
        production, approval = self._requested()
        self.assertAlmostEqual(production.construction_excess_pct, 50.0)
        self.assertAlmostEqual(approval.construction_excess_pct, 50.0)


@tagged('post_install', '-at_install')
class TestRequestDispatchApartmentV111(TestRequestScope):
    """El despacho a obra por unidad de un requerimiento toma el departamento
    de sus líneas (21-oct-2026): el almacenero no lo escribe en cada despacho
    de material."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.construction_dispatch_type_id.construction_site_dispatch = True
        cls.p_hinge.is_storable = True
        cls.env['stock.quant']._update_available_quantity(
            cls.p_hinge, cls.company.construction_src_location_id, 100)

    def _dispatch(self, tasks):
        request = self._new_request()
        request.write({'line_ids': [Command.create({
            'product_id': self.p_hinge.id, 'product_qty': 1, 'task_id': task.id,
            'construction_stage': 'assembly'}) for task in tasks]})
        request.with_user(self.requester).action_request_approval()
        self.assertEqual(request.state, 'approved')
        # El almacén procesa y valida, no el solicitante.
        request = request.with_env(self.env)
        request.action_process()
        picking = request.picking_ids.filtered(lambda p: p.state != 'cancel')
        self.assertEqual(len(picking), 1)
        self.assertTrue(picking.construction_site_dispatch)
        picking.move_ids.picked = True
        return request, picking

    def test_one_apartment_is_taken_from_the_lines(self):
        request, picking = self._dispatch(self.space_501)
        self.assertEqual(picking.construction_apartment_task_id, self.apt_501)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(request.line_ids.qty_dispatched, 1)

    def test_material_without_apartment_does_not_ask(self):
        """Material de dos departamentos o de todo el piso: sin productos de
        módulo, se valida sin departamento."""
        for tasks in (self.space_501 | self.space_502, self.floor):
            _request, picking = self._dispatch(tasks)
            self.assertFalse(picking.construction_apartment_task_id)
            picking.button_validate()
            self.assertEqual(picking.state, 'done')

    def test_module_products_still_ask(self):
        _request, picking = self._dispatch(self.space_501 | self.space_502)
        self.p_hinge.product_tmpl_id.construction_project_id = self.project
        with self.assertRaises(UserError):
            picking.button_validate()
        picking.construction_apartment_task_id = self.apt_502
        picking.button_validate()
        self.assertEqual(picking.state, 'done')


@tagged('post_install', '-at_install')
class TestStageChainV111(TestStageChainV110):
    """M111-03 y M111-04 sobre la obra de prueba del paquete 1.10, con un canto
    de 0.024 por módulo en el corte: el plan guarda 0.02 por módulo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.edge = cls.env['product.product'].create({
            'name': 'Canto delgado (test v111)', 'type': 'consu', 'default_code': 'V111-CAN',
            'standard_price': 10.0})
        Workcenter = cls.env['mrp.workcenter']
        cls.wc_cut = Workcenter.create({'name': 'Corte (test v111)',
                                        'company_id': cls.company.id})
        cls.wc_asm = Workcenter.create({'name': 'Armado (test v111)',
                                        'company_id': cls.company.id})

    @staticmethod
    def _rows():
        rows = TestStageChainV110._rows()
        rows['BOM'] += [
            {'typology': 'C07', 'module': module, 'product_code': 'V111-CAN', 'qty': 0.024,
             'stage': 'Producción'} for module in ('MB1', 'MB2')]
        return rows

    def _set_workcenters(self, cut=True, asm=True):
        self.stage_cut.with_company(self.company).write({
            'production_workcenter_id': self.wc_cut.id if cut else False,
            'production_time_cycle': 12.0})
        self.stage_asm.with_company(self.company).write({
            'production_workcenter_id': self.wc_asm.id if asm else False,
            'production_time_cycle': 30.0})

    def _cut_bom(self, typology):
        package = typology.production_bom_id.bom_line_ids.filtered(
            'construction_intermediate').product_id
        return self.env['mrp.bom']._bom_find(package)[package]

    def test_import_adds_stage_operation(self):
        self._set_workcenters()
        self._import()
        c07 = self._typology('C07')
        final, cut = c07.production_bom_id, self._cut_bom(c07)
        self.assertEqual(final.operation_ids.workcenter_id, self.wc_asm)
        self.assertEqual(final.operation_ids.name, self.stage_asm.name)
        self.assertEqual(final.operation_ids.time_cycle_manual, 30.0)
        self.assertEqual(cut.operation_ids.workcenter_id, self.wc_cut)
        # Volver a importar no duplica ni cambia una operación puesta a mano.
        final.operation_ids.name = 'Armado a mano (test v111)'
        self._import()
        self.assertEqual(final.operation_ids.mapped('name'), ['Armado a mano (test v111)'])
        self.assertEqual(len(cut.operation_ids), 1)
        # Las órdenes pasan por la estación de su etapa.
        plan = self._site_plan()
        kitchens = self._productions(plan).filtered(lambda p: p.bom_id == final)
        kitchens.action_confirm()
        children = self.env['mrp.production'].search(
            [('construction_parent_id', 'in', kitchens.ids)])
        self.assertTrue(children)
        self.assertEqual(kitchens.workorder_ids.workcenter_id, self.wc_asm)
        self.assertEqual(children.workorder_ids.workcenter_id, self.wc_cut)

    def test_stage_without_workcenter_keeps_bom_without_operations(self):
        self._set_workcenters(cut=False)
        self._import()
        c07 = self._typology('C07')
        self.assertTrue(c07.production_bom_id.operation_ids)
        self.assertFalse(self._cut_bom(c07).operation_ids)

    def test_complete_operations_on_imported_site(self):
        self._import()
        c07 = self._typology('C07')
        self.assertFalse(c07.production_bom_id.operation_ids)
        self._set_workcenters()
        result = self.site.with_user(self.planner).action_construction_complete_operations()
        self.assertEqual(result['params']['type'], 'success')
        self.assertEqual(c07.production_bom_id.operation_ids.workcenter_id, self.wc_asm)
        self.assertEqual(self._cut_bom(c07).operation_ids.workcenter_id, self.wc_cut)
        result = self.site.action_construction_complete_operations()
        self.assertEqual(result['params']['type'], 'warning')
        self.assertEqual(len(c07.production_bom_id.operation_ids), 1)

    def test_rounding_matches_plan(self):
        self._import()
        c07 = self._typology('C07')
        edge = self._cut_bom(c07).bom_line_ids.filtered(lambda l: l.product_id == self.edge)
        self.assertAlmostEqual(edge.product_qty, 0.04, msg='0.02 + 0.02, como el plan')
        plan = self._site_plan()
        planned = sum(plan.line_ids.filtered(
            lambda l: l.product_id == self.edge
            and l.space_task_id == self._space('Dpto 301')).mapped('qty_planned'))
        self.assertAlmostEqual(planned, 0.04)
        kitchens = self._productions(plan).filtered(
            lambda p: p.bom_id == c07.production_bom_id)
        kitchens.action_confirm()
        for child in self.env['mrp.production'].search(
                [('construction_parent_id', 'in', kitchens.ids)]):
            row = [v for v in child._construction_versus_values()
                   if v['product_id'] == self.edge.id][0]
            self.assertAlmostEqual(row['qty_budget'], row['qty_required'])
            self.assertFalse(row['change_type'])
            self.assertEqual(child.construction_exceed_state, 'ok')
        # Un exceso real de una unidad se sigue marcando.
        child = self.env['mrp.production'].search(
            [('construction_parent_id', 'in', kitchens.ids)], limit=1)
        child.move_raw_ids.filtered(lambda m: m.product_id == self.edge).product_uom_qty += 1
        row = [v for v in child._construction_versus_values()
               if v['product_id'] == self.edge.id][0]
        self.assertEqual(row['change_type'], 'quantity')


# Las pruebas heredadas ya corren en sus clases.
for _class, _bases in (
        (TestApprovalsV111, (TestApprovalsRequest, TestRequestScope, PlannerCommon)),
        (TestPlanPctV111, (TestApprovalsPlan, PlannerCommon)),
        (TestRequestDispatchApartmentV111, (TestRequestScope, PlannerCommon)),
        (TestProductionPctV111, (TestProductionExcess, PlannerCommon)),
        (TestStageChainV111, (TestStageChainV110, PlannerCommon))):
    for _base in _bases:
        for _name in dir(_base):
            if _name.startswith('test_') and callable(getattr(_base, _name)) \
                    and _name not in vars(_class):
                setattr(_class, _name, None)
