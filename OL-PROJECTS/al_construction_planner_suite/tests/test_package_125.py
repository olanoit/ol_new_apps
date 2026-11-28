# -*- coding: utf-8 -*-
"""Paquete 1.25: requerimiento de fabricación como documento (M125-01 a
M125-04) y la obra en el nombre del plan de recursos (M125-05).

Piso 05 con dos departamentos: la cocina del Dpto 501 es la tipología 01 y la
del Dpto 502, la 02. «Una OF por: Piso» da un requerimiento con dos órdenes."""
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import PlannerCommon
from .test_stage_chain_v110 import TestStageChainV110

REVIEW = 'al_construction_planner_mrp.mail_activity_manufacturing_request_review'
DATE_REVIEW = 'al_construction_planner_mrp.mail_activity_production_date_review'


@tagged('post_install', '-at_install')
class TestPackage125(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Usuarios sin permisos de administrador: la jefatura de proyectos
        # crea el requerimiento; el jefe de producción solo tiene Fabricación.
        cls.project_head = new_test_user(
            cls.env, 'm125_jefatura', name='Jefatura de proyectos (test)',
            groups='al_construction_planner.group_planner_project_head')
        cls.production_head = new_test_user(
            cls.env, 'm125_jefe_produccion', name='Jefe de producción (test)',
            groups='mrp.group_mrp_user')
        cls.company.write({'construction_production_date_review': True,
                           'construction_production_head_id': cls.production_head.id})
        kitchen_02 = cls.env['product.template'].create({
            'name': 'Cocina tipo 02 (test)', 'type': 'consu'})
        bom_02 = cls.bom.copy({'product_tmpl_id': kitchen_02.id})
        cls.typology_02 = cls.env['construction.typology'].create({
            'project_id': cls.project.id, 'code': '02', 'name': 'Cocina 02',
            'family': 'kitchen', 'product_tmpl_id': kitchen_02.id, 'bom_id': bom_02.id})
        cls.space_502.construction_typology_id = cls.typology_02

    def setUp(self):
        super().setUp()
        self._generate_and_approve()

    def _production_wizard(self, user=None, **vals):
        return self.env['construction.plan.production.wizard'].with_user(
            user or self.project_head).with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create(vals)

    def _request(self, user=None, **vals):
        action = self._production_wizard(user, **vals).action_create()
        self.assertEqual(action['res_model'], 'construction.manufacturing.request')
        self.assertEqual(action['view_mode'], 'form')
        return self.env['construction.manufacturing.request'].browse(action['res_id'])

    def _review_activities(self, records, xmlid=REVIEW):
        return records.activity_ids.filtered(
            lambda a: a.activity_type_id == self.env.ref(xmlid))

    # ------------------------------------------------------------------
    # M125-01
    # ------------------------------------------------------------------
    def test_request_with_its_orders(self):
        request = self._request()
        productions = request.production_ids
        self.assertEqual(len(productions), 2, 'una orden por tipología del piso')
        self.assertEqual(set(productions.mapped('state')), {'draft'})
        self.assertEqual(productions.construction_mrp_request_id, request)
        self.assertEqual(request.state, 'draft')
        self.assertTrue(request.name.startswith(
            'RQF/%s/' % fields.Date.context_today(request).year))
        self.assertEqual(request.project_id, self.project)
        self.assertEqual(request.plan_id, self.plan)
        self.assertEqual(request.user_id, self.project_head)
        self.assertEqual(request.production_head_ids, self.production_head)
        self.assertEqual(request.group_by, 'floor')
        # «Ambientes» son los que suman las órdenes.
        self.assertEqual(request.space_task_ids, productions.construction_space_task_ids)
        self.assertEqual(request.space_task_ids, self.space_501 | self.space_502)
        self.assertIn('Piso 05 / Dpto 501 / Cocina · 01', request.space_labels)
        self.assertIn('Piso 05 / Dpto 502 / Cocina · 02', request.space_labels)
        # «Documento origen»: número · agrupador · tipología.
        production_01 = productions.filtered(lambda p: p.construction_typology_id == self.typology)
        self.assertEqual(production_01.origin, '%s · %s · 01' % (
            request.name, self.floor.display_name))
        self.assertEqual(production_01.construction_group_task_id, self.floor)
        # Lo que lleva cada orden no cambia.
        self.assertEqual(production_01.construction_plan_id, self.plan)
        self.assertEqual(production_01.construction_space_task_ids, self.space_501)
        self.assertEqual(production_01.project_id, self.project)
        self.assertTrue(production_01.construction_allocation_ids)
        # El mensaje del plan nombra el requerimiento con enlace.
        message = self.plan.message_ids.filtered(lambda m: request.name in (m.body or ''))
        self.assertTrue(message)
        self.assertIn('construction.manufacturing.request', message.body)
        self.assertEqual(self.plan.state, 'in_progress')

    def test_selection_and_busy_spaces(self):
        """Un ambiente que ya está en una orden no entra en «Ambientes»."""
        wizard = self.env['construction.plan.production.wizard'].with_user(
            self.project_head).with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.apt_501.ids,
        ).create({'group_by': 'selection'})
        first = self.env['construction.manufacturing.request'].browse(
            wizard.action_create()['res_id'])
        self.assertEqual(first.space_task_ids, self.space_501)
        wizard = self.env['construction.plan.production.wizard'].with_user(
            self.project_head).with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create(
            {'group_by': 'selection'})
        self.assertIn('Ya en una OF', wizard.note)
        second = self.env['construction.manufacturing.request'].browse(
            wizard.action_create()['res_id'])
        self.assertEqual(second.space_task_ids, self.space_502)
        self.assertEqual(second.group_by, 'selection')
        self.assertFalse(second.production_ids.construction_group_task_id)

    def test_sequence_by_company(self):
        Request = self.env['construction.manufacturing.request']
        first = Request._construction_next_number(self.company)
        second = Request._construction_next_number(self.company)
        self.assertEqual(int(second[-5:]), int(first[-5:]) + 1)
        other = self.env['res.company'].create({'name': 'Otra compañía (test M125)'})
        self.assertTrue(Request._construction_next_number(other).endswith('/00001'))

    def test_state_follows_the_orders(self):
        request = self._request()
        first, second = request.production_ids
        first.with_user(self.production_head).action_confirm()
        self.assertEqual(request.state, 'partial')
        second.with_user(self.production_head).action_confirm()
        self.assertEqual(request.state, 'confirmed')
        for production in request.production_ids:
            production.qty_producing = production.product_qty
            for move in production.move_raw_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            production.button_mark_done()
        self.assertEqual(request.state, 'done')

    def test_header_is_written_by_the_wizard_only(self):
        request = self._request()
        with self.assertRaises(UserError):
            request.with_user(self.project_head).project_id = self.env['project.project'].create(
                {'name': 'Otra obra (test)'})
        with self.assertRaises(AccessError):
            request.with_user(self.production_head).note = 'Cambio (test)'
        request.with_user(self.project_head).note = 'Piso completo (test)'
        with self.assertRaises(UserError):
            request.copy()

    def test_production_head_opens_the_request(self):
        request = self._request().with_user(self.production_head)
        self.assertTrue(request.name)
        self.assertTrue(request.space_labels)
        for method in ('action_view_productions', 'action_view_cut_productions',
                       'action_view_pickings'):
            action = getattr(request, method)()
            self.env[action['res_model']].with_user(self.production_head).search(
                action['domain'])
        self.assertEqual(len(request.production_ids), 2)
        Request = self.env['construction.manufacturing.request']
        for user in (self.production_head, self.project_head):
            Request.with_user(user).get_views([(False, 'form'), (False, 'list'),
                                               (False, 'search'), (False, 'activity')])
            self.env['mrp.production'].with_user(user).get_views(
                [(False, 'form'), (False, 'list'), (False, 'search')])
        self.assertEqual(Request.with_user(self.production_head).search_count(
            [('id', '=', request.id)]), 1)

    def test_project_button_and_menus(self):
        request = self._request()
        project = self.project.with_user(self.project_head)
        self.assertEqual(project.construction_mrp_request_count, 1)
        action = project.action_view_construction_mrp_requests()
        self.assertEqual(self.env[action['res_model']].with_user(self.project_head).search(
            action['domain']), request)
        for xmlid in ('al_construction_planner_mrp.menu_planner_manufacturing_requests',
                      'al_construction_planner_mrp.menu_mrp_manufacturing_requests',
                      'al_construction_planner_mrp.menu_planner_productions'):
            menu = self.env.ref(xmlid)
            self.assertTrue(menu.action)
        # M125-02, punto 4: el del planificador abre en borrador y agrupado;
        # el de Manufactura, como siempre.
        planner = self.env.ref('al_construction_planner_mrp.menu_planner_productions').action
        self.assertIn('search_default_group_construction_request', planner.context)
        self.assertIn('search_default_filter_draft', planner.context)
        native = self.env.ref('mrp.menu_mrp_production_action').action
        self.assertEqual(native, self.env.ref('mrp.mrp_production_action'))
        self.assertNotIn('construction_request', native.context or '')

    # ------------------------------------------------------------------
    # M125-02
    # ------------------------------------------------------------------
    def test_order_shows_its_request(self):
        request = self._request()
        production = request.production_ids[:1]
        action = production.with_user(self.production_head).action_view_construction_request()
        self.assertEqual(action['res_id'], request.id)
        # La referencia del requerimiento se suma a la propia de la orden.
        self.assertIn(production.name, production.reference_ids.mapped('name'))
        self.assertIn(request.name, production.reference_ids.mapped('name'))
        self.assertIn(request.reference_id, production.move_raw_ids.reference_ids)
        # Duplicar no copia el requerimiento; una orden a mano no lo tiene.
        self.assertFalse(production.copy().construction_mrp_request_id)
        manual = self.env['mrp.production'].create({
            'product_id': self.kitchen.product_variant_id.id, 'bom_id': self.bom.id})
        self.assertFalse(manual.construction_mrp_request_id)
        self.assertEqual(manual.reference_ids.mapped('name'), [manual.name])
        # Agrupar la lista por requerimiento: un grupo con sus órdenes.
        groups = self.env['mrp.production'].with_context(
            construction_request_long_name=True)._read_group(
            [('construction_mrp_request_id', '=', request.id)], ['construction_mrp_request_id'],
            ['__count'])
        self.assertEqual(groups[0][1], 2)
        self.assertIn(self.project.name, groups[0][0].with_context(
            construction_request_long_name=True).display_name)
        self.assertEqual(request.display_name, request.name)

    # ------------------------------------------------------------------
    # M125-03
    # ------------------------------------------------------------------
    def test_one_activity_per_request(self):
        request = self._request()
        first, second = request.production_ids
        activity = self._review_activities(request)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.production_head)
        self.assertEqual(activity.summary, 'Revisar y confirmar las órdenes del requerimiento')
        self.assertIn(first.name, activity.note)
        self.assertIn(second.name, activity.note)
        self.assertFalse(self._review_activities(request.production_ids, DATE_REVIEW))
        first.with_user(self.production_head).construction_date_confirmed = \
            fields.Date.context_today(first)
        first.with_user(self.production_head).action_confirm()
        self.assertTrue(self._review_activities(request))
        second.with_user(self.production_head).action_confirm()
        self.assertFalse(self._review_activities(request))
        done = request.message_ids.filtered(lambda m: second.name in (m.body or '')
                                            and first.name in (m.body or ''))
        self.assertTrue(done, 'el cierre lista las dos órdenes')
        self.assertIn(str(first.construction_date_confirmed), done[0].body)

    def test_activity_switch_off(self):
        self.company.construction_production_date_review = False
        request = self._request()
        self.assertFalse(request.activity_ids)
        self.assertFalse(request.production_ids.activity_ids)

    def test_activity_without_production_head(self):
        """Sin jefe de producción, los responsables de Fabricación."""
        manager = new_test_user(self.env, 'm125_resp_fab', name='Responsable (test)',
                                groups='mrp.group_mrp_manager')
        self.company.construction_production_head_id = False
        request = self._request()
        self.assertIn(manager, request.production_head_ids)
        self.assertIn(manager, self._review_activities(request).user_id)

    # ------------------------------------------------------------------
    # M125-04
    # ------------------------------------------------------------------
    def _cancel_wizard(self, request, user):
        action = request.with_user(user).action_cancel()
        self.assertEqual(action['name'], 'Cancelar %s' % request.name)
        return self.env[action['res_model']].with_user(user).browse(action['res_id'])

    def test_cancel_all_in_draft(self):
        request = self._request()
        wizard = self._cancel_wizard(request, self.production_head)
        self.assertFalse(wizard.started_production_ids)
        self.assertEqual(wizard.draft_production_ids, request.production_ids)
        wizard.action_cancel_drafts()
        self.assertEqual(set(request.production_ids.mapped('state')), {'cancel'})
        self.assertEqual(request.state, 'cancel')
        self.assertTrue(request.message_ids.filtered(
            lambda m: self.production_head.name in (m.body or '')))
        self.assertFalse(self._review_activities(request))
        # Los ambientes vuelven a la vista previa del asistente.
        again = self._production_wizard()
        self.assertEqual(again.line_ids.space_task_ids, self.space_501 | self.space_502)
        with self.assertRaises(UserError):
            request.with_user(self.production_head).action_cancel()

    def test_cancel_with_an_order_in_production(self):
        request = self._request()
        confirmed, draft = request.production_ids
        confirmed.with_user(self.production_head).action_confirm()
        wizard = self._cancel_wizard(request, self.project_head)
        self.assertEqual(wizard.started_production_ids, confirmed)
        self.assertEqual(wizard.draft_production_ids, draft)
        wizard.action_cancel_drafts()
        self.assertEqual(confirmed.state, 'confirmed')
        self.assertEqual(draft.state, 'cancel')
        self.assertEqual(request.state, 'confirmed')
        # Sin órdenes en borrador, el diálogo solo informa.
        info = self._cancel_wizard(request, self.project_head)
        self.assertFalse(info.draft_production_ids)
        with self.assertRaises(UserError):
            info.action_cancel_drafts()
        again = self._production_wizard()
        self.assertEqual(again.line_ids.space_task_ids, draft.construction_space_task_ids)

    # ------------------------------------------------------------------
    # M125-05
    # ------------------------------------------------------------------
    def test_plan_name_with_its_site(self):
        self.assertEqual(self.plan.display_name, '%s · v%s · %s' % (
            self.plan.name, self.plan.version, self.project.display_name))
        self.assertEqual(self.plan.with_context(construction_plan_short_name=True).display_name,
                         '%s · v%s' % (self.plan.name, self.plan.version))
        Plan = self.env['construction.resource.plan'].with_user(self.project_head)
        found = Plan.name_search('MOMEN')
        self.assertIn(self.plan.id, [plan_id for plan_id, _name in found])
        request = self._request()
        production = request.production_ids[:1].with_user(self.production_head)
        self.assertIn(self.project.name, production.construction_plan_id.display_name)
        # Los selectores que ya muestran la obra usan el nombre corto.
        short = Plan.with_context(construction_plan_short_name=True).search_read(
            [('id', '=', self.plan.id)], ['display_name'])
        self.assertEqual(short[0]['display_name'], '%s · v%s' % (
            self.plan.name, self.plan.version))
        groups = Plan.get_schedule_plans(self.plan.id)['groups']
        self.assertEqual(groups[0]['plans'][0]['display_name'], short[0]['display_name'])


@tagged('post_install', '-at_install')
class TestPackage125Chain(TestStageChainV110):
    """M125-02 con dos plantas: la orden de corte hija y las transferencias
    llevan el número del requerimiento."""

    def test_request_travels_with_the_chain(self):
        # Entrega a producción en las dos plantas: los componentes salen del
        # almacén en una transferencia antes de cada orden.
        (self.wh_cut | self.wh_asm).manufacture_steps = 'pbm'
        self._import()
        plan = self._site_plan()
        productions = self._productions(plan)
        request = productions.construction_mrp_request_id
        self.assertEqual(len(request), 1)
        c07 = self._typology('C07')
        kitchens = productions.filtered(lambda p: p.bom_id == c07.production_bom_id)
        kitchens.action_confirm()
        children = self.env['mrp.production'].search(
            [('construction_parent_id', 'in', kitchens.ids)])
        self.assertTrue(children)
        self.assertEqual(children.construction_mrp_request_id, request)
        self.assertEqual(request.cut_production_ids, children)
        self.assertFalse(children & request.production_ids)
        self.assertEqual(request.cut_production_count, len(children))
        for child in children:
            self.assertIn(request.reference_id, child.reference_ids)
        pickings = request._construction_pickings()
        self.assertTrue(pickings)
        for picking in pickings:
            self.assertEqual(picking.construction_mrp_request_id, request)
        self.assertEqual(self.env['stock.picking'].search(
            [('construction_mrp_request_id', 'ilike', request.name)]), pickings)
        # Las hijas no cuentan en el estado del requerimiento.
        self.assertIn(request.state, ('partial', 'confirmed'))


@tagged('post_install', '-at_install')
class TestScreens125(HttpCase, PlannerCommon):
    """Prueba de pantalla del paquete 1.25: el asistente, el formulario del
    requerimiento, sus botones inteligentes, la marca en la orden, el
    agrupador de la lista y el diálogo de cancelación; falla si un clic da
    error. Cada parte la recorre su usuario, sin administrador."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_head = new_test_user(
            cls.env, 'm125_tour_jefatura', password='m125_tour_jefatura',
            name='Jefatura de proyectos (tour)',
            groups='al_construction_planner.group_planner_project_head')
        cls.production_head = new_test_user(
            cls.env, 'm125_tour_produccion', password='m125_tour_produccion',
            name='Jefe de producción (tour)', groups='mrp.group_mrp_user')
        cls.company.construction_production_head_id = cls.production_head
        kitchen_02 = cls.env['product.template'].create({
            'name': 'Cocina tipo 02 (tour)', 'type': 'consu'})
        typology_02 = cls.env['construction.typology'].create({
            'project_id': cls.project.id, 'code': '02', 'name': 'Cocina 02',
            'family': 'kitchen', 'product_tmpl_id': kitchen_02.id,
            'bom_id': cls.bom.copy({'product_tmpl_id': kitchen_02.id}).id})
        cls.space_502.construction_typology_id = typology_02
        cls.env['construction.plan.generate.wizard'].create(
            {'plan_id': cls.plan.id}).action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.plan.action_request_approval()
        cls.plan.name = 'PLR-M125'

    def test_tour_request(self):
        self.start_tour('/odoo', 'al_construction_package125_create', login='m125_tour_jefatura')
        request = self.env['construction.manufacturing.request'].search(
            [('plan_id', '=', self.plan.id)])
        self.assertEqual(len(request.production_ids), 2)
        self.start_tour('/odoo', 'al_construction_package125_cancel',
                        login='m125_tour_produccion')
        self.assertEqual(request.state, 'cancel')


# Las pruebas heredadas ya corren en su clase.
for _cls, _base in ((TestPackage125, PlannerCommon), (TestPackage125Chain, TestStageChainV110),
                    (TestScreens125, PlannerCommon)):
    for _name in dir(_base):
        if _name.startswith('test_') and callable(getattr(_base, _name)) \
                and _name not in vars(_cls):
            setattr(_cls, _name, None)
