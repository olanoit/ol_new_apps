# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 2 · bloque 2a: requerimiento sin plan y asignación.

- M116-03 / M114-02: sin plan, con «Material fuera del plan», el requerimiento
  de obra pasa por aprobación con los dos motores; la regla 7.4 («jefe de la
  obra») también funciona con la aplicación Aprobaciones.
- M114-01: al aprobar el plan se regularizan los pedidos hechos sin él.
- M114-03 / M116-04: el módulo como último selector y la ruta del nivel desde
  un nivel configurable.
- M114-04: la línea agregada a mano lleva las cuentas de las reglas.
- CR-21: el Cronograma abre con el último plan del usuario.
- CR-24 con M116-06: «Asignar contrata» avisa lo ya asignado y la modalidad
  escrita en la partida."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage116Stage2a(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company._al_construction_ensure_setup()
        cls.requester = new_test_user(
            env, 'rq116_supervisor', name='Supervisor 1.16 (test)',
            groups='al_construction_material_request.group_construction_requester,'
                   'project.group_project_user')
        cls.site_manager = new_test_user(
            env, 'rq116_jefe_obra', name='Jefe de obra 1.16 (test)',
            groups='al_construction_material_request.group_construction_requester,'
                   'project.group_project_user')
        cls.exec_approver = new_test_user(
            env, 'rq116_jefatura', name='Jefatura 1.16 (test)',
            groups='al_construction_planner.group_planner_exec_approver')
        # Solo las reglas que crea cada prueba con el ajuste de la compañía.
        env['tier.definition'].search([('model', '=', 'construction.material.request')]).active = False
        cls.site = env['project.project'].create({
            'name': 'Obra sin plan (test 1.16)', 'is_construction_site': True,
            'user_id': cls.site_manager.id})
        if not cls.site.account_id:
            cls.site._create_analytic_account()
        cls.site.message_subscribe(partner_ids=cls.requester.partner_id.ids)
        cls.site_task = env['project.task'].create({
            'name': 'Partida 1.16 (test)', 'project_id': cls.site.id})
        cls.p_anchor = env['product.product'].create({
            'name': 'Anclaje 1.16 (test)', 'type': 'consu', 'standard_price': 4.0})

    def _request(self, product, qty, project=None, task=None, stage='installation', user=None):
        project = project or self.site
        request = self.env['construction.material.request'].with_user(
            user or self.requester).create({'project_id': project.id})
        request.write({'line_ids': [Command.create({
            'product_id': product.id, 'product_qty': qty,
            'task_id': (task or self.site_task).id, 'construction_stage': stage})]})
        return request

    def _setting(self, value, engine='tier'):
        self.company.write({'construction_approval_engine': engine,
                            'construction_site_request_without_rule': value})

    # ------------------------------------------------------------------
    # M116-03 / M114-02
    # ------------------------------------------------------------------
    def test_no_plan_out_of_plan_with_tiers(self):
        self._setting('out_of_plan')
        rule = self.env['tier.definition'].search([
            ('construction_no_plan', '=', True), ('company_id', '=', self.company.id)])
        self.assertTrue(rule.active)
        request = self._request(self.p_screw, 10)
        request.with_user(self.requester).action_request_approval()
        self.assertEqual(request.construction_exceed_state, 'no_plan')
        self.assertEqual(request.state, 'to_approve')
        self.assertEqual(request.review_ids.definition_id, rule)
        request.with_user(self.exec_approver).validate_tier()
        self.assertEqual(request.state, 'approved')
        # Volver a «Aprobar al enviar» archiva la regla.
        self._setting('approve')
        self.assertFalse(rule.active)

    def test_no_plan_out_of_plan_with_approvals(self):
        self._setting('out_of_plan', engine='approvals')
        Route = self.env['construction.approval.route']
        Route.search([('company_id', '=', self.company.id)]).active = False
        Route.create({
            'name': 'Material fuera del plan: jefatura (test 1.16)', 'company_id': self.company.id,
            'document_type': 'material_request', 'change_type': 'material',
            'approver_ids': [Command.create({'user_id': self.exec_approver.id})]})
        request = self._request(self.p_screw, 10)
        request.with_user(self.requester).action_request_approval()
        self.assertEqual(request.state, 'to_approve')
        approval = request.construction_approval_id
        self.assertTrue(approval.construction_no_plan)
        self.assertEqual(approval.construction_change_summary, 'no_plan')
        self.assertEqual(approval.product_line_ids.construction_change_type, 'material')
        self.assertEqual(approval.approver_ids.user_id, self.exec_approver)

    def test_site_manager_rule_with_approvals(self):
        """La regla 7.4 da el mismo resultado con la aplicación Aprobaciones."""
        self._setting('manager', engine='approvals')
        request = self._request(self.p_screw, 10)
        request.with_user(self.requester).action_request_approval()
        self.assertEqual(request.state, 'to_approve')
        self.assertEqual(request.construction_approval_id.approver_ids.user_id, self.site_manager)

    def test_approve_on_send_keeps_today(self):
        self._setting('approve', engine='approvals')
        request = self._request(self.p_screw, 10)
        request.with_user(self.requester).action_request_approval()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.construction_exceed_state, 'no_plan')

    # ------------------------------------------------------------------
    # M114-01
    # ------------------------------------------------------------------
    def _approve_plan_with(self, qty_planned):
        plan = self.env['construction.resource.plan'].create({'project_id': self.site.id})
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'task_id': self.site_task.id, 'resource_type': 'material',
            'product_id': self.p_screw.id, 'product_uom_id': self.unit.id,
            'qty_planned': qty_planned, 'price_unit_planned': 2.0, 'stage': 'installation'})
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        return plan, line

    def test_regularize_requests_without_plan(self):
        self._setting('approve')
        fits = self._request(self.p_screw, 10)
        fits.with_user(self.requester).action_request_approval()
        unplanned = self._request(self.p_anchor, 5)
        unplanned.with_user(self.requester).action_request_approval()
        self.assertEqual((fits | unplanned).mapped('state'), ['approved', 'approved'])
        self.assertTrue(fits.construction_unplanned)
        plan, line = self._approve_plan_with(60)
        self.assertEqual(fits.construction_plan_id, plan)
        self.assertEqual(line.qty_requested, 10)
        self.assertFalse(fits.construction_unplanned)
        self.assertTrue(unplanned.construction_unplanned, 'el material que el plan no tiene')
        self.assertIn('2 requerimiento(s) revisado(s), 1 línea(s) asignada(s) y 1 fuera de plan',
                      ''.join(plan.message_ids.mapped('body')))
        # Otra versión no duplica las asignaciones.
        wizard = self.env['construction.plan.replan.wizard'].create({
            'plan_id': plan.id, 'mode': 'all', 'reason': 'Cambio de alcance (test 1.16).'})
        new_plan = self.env['construction.resource.plan'].browse(
            wizard.action_create_version()['res_id'])
        new_plan.action_request_approval()
        self.assertEqual(new_plan.state, 'approved')
        # Odoo 20: el one2many se filtra por los permisos de quien lo lee.
        allocations = fits.line_ids.sudo().construction_allocation_ids
        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations.plan_line_id.plan_id, new_plan)

    def test_regularize_excess_is_logged(self):
        self._setting('approve')
        request = self._request(self.p_screw, 80)
        request.with_user(self.requester).action_request_approval()
        plan, line = self._approve_plan_with(60)
        self.assertEqual(line.qty_requested, 80)
        log = self.env['construction.exceed.log'].search([('plan_id', '=', plan.id)])
        self.assertEqual(log.qty, 20)
        self.assertEqual(log.reason, 'Regularización de pedido sin plan')

    # ------------------------------------------------------------------
    # M114-03 / M116-04
    # ------------------------------------------------------------------
    def _template_project(self, start=None):
        template = self.env['construction.level.template'].create({
            'name': 'Mobiliario con unidad (test 1.16)', 'line_ids': [
                Command.create({'sequence': 10, 'name': 'Piso', 'role': 'group'}),
                Command.create({'sequence': 20, 'name': 'Departamento', 'role': 'unit'}),
                Command.create({'sequence': 30, 'name': 'Ambiente', 'role': 'space'}),
                Command.create({'sequence': 40, 'name': 'Mueble', 'role': 'furniture'}),
                Command.create({'sequence': 50, 'name': 'Módulo', 'role': 'module'})]})
        levels = template.line_ids.sorted('sequence')
        if start:
            template.path_start_line_id = levels[start - 1]
        project = self.env['project.project'].create({
            'name': 'Obra con plantilla (test 1.16)', 'is_construction_site': True,
            'construction_level_template_id': template.id})
        Task = self.env['project.task']
        nodes, parent = [], Task
        for level, name in zip(levels, ('Piso 01', 'Dpto 101', 'Cocina', 'Mueble bajo', 'Bajo')):
            parent = Task.create({'name': name, 'project_id': project.id,
                                  'construction_level_line_id': level.id,
                                  'parent_id': parent.id})
            nodes.append(parent)
        return project, nodes

    def test_level_path_from_delivery_unit(self):
        project, nodes = self._template_project()
        request = self._request(self.p_screw, 1, project=project, task=nodes[-1])
        self.assertEqual(request.line_ids.construction_level_label,
                         'Dpto 101 / Cocina / Mueble bajo / Bajo')
        # El módulo es el último selector.
        labels = [request['construction_scope_%s_label' % depth] for depth in range(1, 6)]
        self.assertEqual(labels, ['Piso', 'Departamento', 'Ambiente', 'Mueble', 'Módulo'])

    def test_level_path_from_configured_level(self):
        project, nodes = self._template_project(start=1)
        request = self._request(self.p_screw, 1, project=project, task=nodes[2])
        self.assertEqual(request.line_ids.construction_level_label, 'Piso 01 / Dpto 101 / Cocina')

    # ------------------------------------------------------------------
    # M114-04
    # ------------------------------------------------------------------
    def test_manual_line_takes_rule_accounts(self):
        Plan = self.env['account.analytic.plan']
        Account = self.env['account.analytic.account']
        stage_plan = Plan.create({'name': 'Etapa (test 1.16)'})
        cost_plan = Plan.create({'name': 'Tipo de costo (test 1.16)'})
        install = Account.create({'name': '2.1 Instalación (test)', 'plan_id': stage_plan.id})
        accessories = Account.create({'name': 'Accesorios (test)', 'plan_id': cost_plan.id})
        self.env['construction.analytic.rule'].create([
            {'sequence': 10, 'stage': 'installation', 'stage_account_id': install.id},
            {'sequence': 20, 'resource_type': 'material', 'cost_account_id': accessories.id}])
        request = self._request(self.p_screw, 10)
        line = request.line_ids
        expected = self.site.account_id | install | accessories
        self.assertEqual(list(line.analytic_distribution),
                         [','.join(str(i) for i in sorted(expected.ids))])
        # Lo escrito a mano manda.
        line.analytic_distribution = {str(self.site.account_id.id): 100.0}
        line.product_qty = 12
        self.assertEqual(line.analytic_distribution, {str(self.site.account_id.id): 100.0})

    # ------------------------------------------------------------------
    # CR-21
    # ------------------------------------------------------------------
    def test_schedule_opens_last_plan_of_user(self):
        Plan = self.env['construction.resource.plan']
        plan, _line = self._approve_plan_with(10)
        result = Plan.get_schedule_plans(plan.id)
        self.assertEqual(result['plan_id'], plan.id)
        self.assertEqual(result['groups'][0]['project'], self.site.display_name)
        self.assertIn('· v1 ·', result['groups'][0]['plans'][0]['label'])
        Plan.remember_schedule_plan(self.plan.id)
        self.assertEqual(Plan.get_schedule_plans()['plan_id'], self.plan.id)
        self.assertEqual(Plan.get_schedule_plans()['groups'][0]['project'],
                         self.project.display_name, 'primero la obra del plan abierto')
        # Un plan reemplazado se abre igual desde su botón (su historia), no
        # el último plan del usuario de otra obra.
        plan.state = 'replaced'
        result = Plan.get_schedule_plans(plan.id)
        self.assertEqual(result['plan_id'], plan.id)
        self.assertEqual(result['groups'][0]['project'], self.site.display_name)


@tagged('post_install', '-at_install')
class TestPackage116Stage2aContract(PlannerCommon):
    """CR-24 con M116-06 sobre una obra con dos partidas de contrata."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['construction.stage'].with_context(active_test=False).search(
            [('code', '=', 'installation')]).default_execution_mode = 'own'
        cls.site = env['project.project'].create({
            'name': 'Obra de contratas (test 1.16)', 'is_construction_site': True})
        if not cls.site.account_id:
            cls.site._create_analytic_account()
        Task = env['project.task']
        cls.partida_own = Task.create({'name': '5.0101 Salida de data (test)',
                                       'project_id': cls.site.id})
        cls.partida_free = Task.create({'name': '5.0102 Salida de voz (test)',
                                        'project_id': cls.site.id})
        cls.partida_own.with_context(construction_plan_force=True).construction_execution_mode = 'own'
        cls.other = env['res.partner'].create({'name': 'Otra contrata (test 1.16)'})
        cls.plan_116 = env['construction.resource.plan'].create({'project_id': cls.site.id})
        cls.line_own, cls.line_free = env['construction.resource.plan.line'].create([
            {'plan_id': cls.plan_116.id, 'task_id': task.id, 'resource_type': 'contract',
             'activity_id': cls.act_inst_low.id, 'stage': 'installation', 'qty_planned': 10.0,
             'price_unit_planned': 18.0, 'product_uom_id': cls.meter.id}
            for task in (cls.partida_own, cls.partida_free)])
        cls.plan_116.action_request_approval()
        assert cls.plan_116.state == 'approved', cls.plan_116.state

    def _wizard(self, tasks, partner=None):
        return self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan_116.id, construction_selection_task_ids=tasks.ids,
        ).create({'stage': 'installation', 'partner_id': (partner or self.contractor).id})

    def test_mode_warning_only_when_written_on_partida(self):
        wizard = self._wizard(self.partida_own | self.partida_free)
        self.assertEqual(wizard.mode_task_ids, self.partida_own,
                         'la modalidad de la etapa no cuenta, solo la escrita en la partida')
        self.assertEqual(wizard.execution_mode, 'full_contract')
        wizard.action_assign()
        # Plan aprobado: el cambio queda para la nueva versión.
        self.assertEqual(self.partida_own.construction_execution_mode, 'own')
        self.assertIn('nueva versión', ''.join(self.plan_116.message_ids.mapped('body')))

    def test_everything_assigned_does_not_open(self):
        self._wizard(self.partida_own | self.partida_free).action_assign()
        with self.assertRaisesRegex(UserError, 'ya tienen contrata'):
            self._wizard(self.partida_own | self.partida_free, partner=self.other)

    def test_no_balance_lines_are_listed(self):
        self._wizard(self.partida_free).action_assign()
        wizard = self._wizard(self.partida_own | self.partida_free, partner=self.other)
        self.assertEqual(wizard.line_ids.plan_line_ids, self.line_own)
        self.assertIn('sin saldo ya están asignadas a %s' % self.contractor.display_name,
                      wizard.note)
