# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon

# PNG de 1 × 1 píxel: la foto del avance.
PHOTO = (b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         b'hQGAhKmMIQAAAABJRU5ErkJggg==')


@tagged('post_install', '-at_install')
class TestControl(PlannerCommon):
    """Fase 7, control y personal propio: control de la OC con analítica de
    la obra contra el presupuesto analítico (W-10), análisis de control
    (P-13) con el estado y los montos almacenados, cuadrilla (W-06) con
    turnos y hojas de horas, cambio de fechas (W-08) con aviso a Logística,
    reversión del estado del módulo y multicompañía."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        grp = 'al_construction_planner.group_planner_'
        cls.manager = new_test_user(
            cls.env, 'plan_jefatura_f7', name='Jefatura (test)', groups=f'{grp}manager')
        cls.buyer = new_test_user(
            cls.env, 'plan_compras_f7', name='Comprador (test)',
            groups='purchase.group_purchase_user')
        cls.logistics = new_test_user(
            cls.env, 'plan_logistica_f7', name='Logística (test)',
            groups='al_construction_material_request.group_construction_logistics')
        cls.company._al_construction_ensure_setup()
        if not cls.project.account_id:
            cls.project._create_analytic_account()

        # Personal propio: actividad en horas con rol, en el ambiente del
        # Dpto 501 (la cuadrilla trabaja por ambiente o superior).
        cls.hour = cls.env.ref('uom.product_uom_hour')
        cls.role = cls.env['planning.role'].create({'name': 'Instalador propio (test)'})
        cls.act_crew = cls.env['construction.labor.activity'].create({
            'code': 'PP-INS', 'name': 'Instalación con personal propio', 'stage': 'installation',
            'uom_id': cls.hour.id, 'default_price': 12.0, 'role_id': cls.role.id})
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Obrero propio (test)', 'hourly_cost': 10.0,
            'company_id': cls.company.id})

        wizard = cls.env['construction.plan.generate.wizard'].create({'plan_id': cls.plan.id})
        wizard.action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.labor_line = cls.env['construction.resource.plan.line'].create({
            'plan_id': cls.plan.id, 'task_id': cls.space_501.id, 'resource_type': 'labor',
            'stage': 'installation', 'activity_id': cls.act_crew.id, 'role_id': cls.role.id,
            'product_uom_id': cls.hour.id, 'qty_planned': 40.0, 'price_unit_planned': 12.0,
        })
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state

    def _set_policy(self, policy, tolerance=0.0):
        self.plan.write({'exceed_policy': policy, 'exceed_tolerance': tolerance})

    # ------------------------------------------------------------------
    # OC con analítica de la obra (control de saldo)
    # ------------------------------------------------------------------
    def _order(self, amount):
        partner = self.env['res.partner'].create({'name': 'Proveedor (test)'})
        return self.env['purchase.order'].with_user(self.buyer).create({
            'partner_id': partner.id,
            'date_order': datetime.combine(self.plan.date_start, datetime.min.time())
            + timedelta(hours=12),
            'order_line': [Command.create({
                'product_id': self.p_white.id, 'product_qty': 1, 'price_unit': amount,
                'tax_ids': [Command.clear()],
                'analytic_distribution': {str(self.project.account_id.id): 100.0}})],
        })

    def test_purchase_order_within_budget(self):
        budget_line = self.plan.budget_analytic_id.budget_line_ids
        self.assertEqual(len(budget_line), 1)
        self.assertAlmostEqual(budget_line.budget_amount, self.plan.amount_total)
        order = self._order(100.0)
        order.with_user(self.buyer).button_confirm()
        self.assertEqual(order.state, 'purchase')
        self.assertEqual(order.construction_exceed_state, 'ok')
        # La OC confirmada ya cuenta como comprometido del presupuesto: una
        # segunda que lo pase se controla.
        rest = self.plan.amount_total - 100.0
        self._set_policy('block')
        with self.assertRaises(UserError):
            self._order(rest + 1.0).with_user(self.buyer).button_confirm()
        # Con 10 % de tolerancia cabe.
        self._set_policy('block', 10.0)
        order = self._order(rest + 1.0)
        order.with_user(self.buyer).button_confirm()
        self.assertEqual(order.state, 'purchase')

    def test_purchase_order_policies(self):
        too_much = self.plan.amount_total + 50.0
        # Bloquear.
        self._set_policy('block')
        order = self._order(too_much)
        with self.assertRaises(UserError):
            order.with_user(self.buyer).button_confirm()
        self.assertEqual(order.state, 'draft')
        # Avisar: basta confirmar el aviso.
        self._set_policy('warn')
        action = order.with_user(self.buyer).button_confirm()
        self.assertEqual(action['res_model'], 'construction.plan.exceed.wizard')
        wizard = self.env['construction.plan.exceed.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.policy, 'warn')
        self.assertAlmostEqual(wizard.line_ids.qty_excess, 50.0)
        self.assertAlmostEqual(wizard.line_ids.qty_requested, too_much)
        self.assertIn(self.plan.budget_analytic_id.name, wizard.line_ids.name)
        wizard.with_user(self.buyer).action_confirm()
        self.assertEqual(order.state, 'purchase')
        self.assertEqual(order.construction_exceed_state, 'exceeded')
        # Pedir aprobación: justificación obligatoria y la confirma la jefatura.
        self._set_policy('approval')
        order = self._order(10.0)
        action = order.with_user(self.buyer).button_confirm()
        wizard = self.env['construction.plan.exceed.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.policy, 'approval')
        with self.assertRaises(UserError):
            wizard.with_user(self.buyer).action_confirm()
        wizard.reason = 'Melamina adicional por cambio de diseño'
        with self.assertRaises(UserError):
            wizard.with_user(self.buyer).action_confirm()
        wizard.with_user(self.manager).action_confirm()
        self.assertEqual(order.state, 'purchase')
        self.assertEqual(order.construction_exceed_state, 'approved')
        self.assertEqual(order.construction_exceed_reason,
                         'Melamina adicional por cambio de diseño')

    def test_purchase_order_without_project_analytic(self):
        """Una OC sin la analítica de la obra no se controla."""
        self._set_policy('block')
        order = self._order(self.plan.amount_total * 3)
        order.order_line.analytic_distribution = False
        order.with_user(self.buyer).button_confirm()
        self.assertEqual(order.state, 'purchase')

    # ------------------------------------------------------------------
    # P-13 y estado almacenado
    # ------------------------------------------------------------------
    def test_control_matches_lines_and_state_filter(self):
        wizard = self.env['construction.plan.request.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.floor.id],
        ).create({'group_by': 'floor'})
        wizard.action_create()
        screws = self.plan.line_ids.filtered(lambda l: l.product_id == self.p_screw)
        Line = self.env['construction.resource.plan.line']
        # Estado almacenado: se filtra y agrupa.
        partial = Line.search([('plan_id', '=', self.plan.id), ('line_state', '=', 'partial')])
        self.assertTrue(screws <= partial)
        groups = dict(Line._read_group(
            [('plan_id', '=', self.plan.id)], ['line_state'], ['__count']))
        self.assertEqual(sum(groups.values()), len(self.plan.line_ids))
        self.assertIn('planned', groups)
        # Comprometido de los tornillos: lo pedido al costo del plan.
        self.assertAlmostEqual(sum(screws.mapped('amount_committed')), 242 * 10.0)
        # P-13 cuadra con las líneas y con el cálculo en vivo.
        data = self.plan._get_control_data()
        live = self.plan.line_ids._get_line_execution()
        self.assertAlmostEqual(sum(v['planned'] for v in data.values()), self.plan.amount_total)
        self.assertAlmostEqual(sum(v['committed'] for v in data.values()),
                               sum(c for c, _a in live.values()))
        self.assertAlmostEqual(sum(v['actual'] for v in data.values()),
                               sum(a for _c, a in live.values()))
        installation = data[('installation', 'material')]
        self.assertAlmostEqual(installation['committed'], 2420.0)
        html = self.plan.control_html
        self.assertIn('Total obra', html)
        self.assertIn('% ejecutado', html)
        action = self.plan.action_open_control_analysis()
        self.assertEqual(action['domain'], [('plan_id', '=', self.plan.id)])
        # Cancelar el requerimiento devuelve las líneas a planificadas.
        request = screws.allocation_ids.material_request_line_id.request_id
        request.action_cancel()
        self.assertEqual(set(screws.mapped('line_state')), {'planned'})
        self.assertEqual(sum(screws.mapped('amount_committed')), 0.0)

    # ------------------------------------------------------------------
    # W-06 · Asignar cuadrilla
    # ------------------------------------------------------------------
    def test_crew_shifts_and_timesheets(self):
        resource = self.employee.resource_id
        wizard = self.env['construction.plan.crew.wizard'].with_user(self.planner).with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.apt_501.id],
        ).create({'role_id': self.role.id, 'resource_ids': [Command.set(resource.ids)],
                  'date_start': date(2026, 10, 15), 'weeks': 2, 'hours_per_week': 10.0})
        self.assertEqual(wizard.plan_line_count, 1)
        self.assertEqual(len(wizard.line_ids), 2)
        self.assertEqual(wizard.hours_total, 20.0)
        # Semana de la obra (jueves por defecto).
        self.assertEqual(wizard.line_ids.mapped('week_start'),
                         [date(2026, 10, 15), date(2026, 10, 22)])
        wizard.with_user(self.planner).action_assign()
        line = self.labor_line
        slots = self.env['planning.slot'].search([('construction_plan_line_id', '=', line.id)])
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots.construction_task_id, self.space_501)
        self.assertEqual(slots.resource_id, resource)
        self.assertEqual(set(slots.mapped('allocated_hours')), {10.0})
        self.assertEqual(slots.project_id, self.project)
        self.assertIn(self.role, resource.role_ids)
        self.assertEqual(set(line.allocation_ids.mapped('kind')), {'planning_slot'})
        self.assertEqual(line.qty_requested, 20.0)
        self.assertEqual(self.plan.state, 'in_progress')
        # Comprometido: horas de turnos sin registrar por el costo hora.
        self.assertAlmostEqual(line.amount_committed, 200.0)
        self.assertAlmostEqual(line.amount_actual, 0.0)
        # El capataz registra 5 h en un módulo del ambiente.
        module = self.env['project.task'].search([('parent_id', '=', self.space_501.id)],
                                                 limit=1)
        self.env['account.analytic.line'].create({
            'name': 'Instalación (test)', 'project_id': self.project.id,
            'task_id': module.id, 'employee_id': self.employee.id, 'unit_amount': 5.0,
            'date': date(2026, 10, 16)})
        self.assertAlmostEqual(line.qty_executed, 5.0)
        self.assertAlmostEqual(line.amount_actual, 50.0)
        self.assertAlmostEqual(line.amount_committed, 150.0)
        self.assertAlmostEqual(line.amount_remaining, 480.0 - 200.0)
        self.assertEqual(line.line_state, 'partial')
        # Menos horas en un turno: baja lo pedido y el comprometido.
        slots[0].allocated_hours = 8.0
        self.assertEqual(line.qty_requested, 18.0)
        self.assertAlmostEqual(line.amount_committed, 130.0)
        slots[0].allocated_hours = 10.0
        # Borrar un turno baja el comprometido.
        slots[1].unlink()
        self.assertAlmostEqual(line.amount_committed, 50.0)
        self.assertEqual(line.qty_requested, 10.0)

    def test_tree_buttons(self):
        """Los botones «Asignar cuadrilla» y «Cambiar fechas» del árbol."""
        actions = self.env['construction.resource.plan'].with_user(
            self.planner).get_tree_actions()
        xmlids = [action['xmlid'] for action in actions]
        self.assertIn('al_construction_planner.action_plan_crew_wizard', xmlids)
        self.assertIn('al_construction_planner.action_plan_reschedule_wizard', xmlids)

    def test_crew_needs_labor_lines(self):
        other_role = self.env['planning.role'].create({'name': 'Electricista (test)'})
        wizard = self.env['construction.plan.crew.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.apt_502.id],
        ).create({'role_id': other_role.id,
                  'resource_ids': [Command.set(self.employee.resource_id.ids)]})
        self.assertFalse(wizard.line_ids)
        self.assertIn('personal propio', wizard.note)
        with self.assertRaises(UserError):
            wizard.action_assign()

    # ------------------------------------------------------------------
    # W-08 · Cambiar fechas
    # ------------------------------------------------------------------
    def test_reschedule_moves_dates_and_warns_logistics(self):
        wizard = self.env['construction.plan.request.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.floor.id],
        ).create({'group_by': 'floor'})
        request = self.env['construction.material.request'].browse(
            wizard.action_create()['res_id'])
        screws = self.plan.line_ids.filtered(lambda l: l.product_id == self.p_screw)
        old = dict(zip(screws.ids, screws.mapped('date_needed')))
        request.date_required = min(old.values())
        other_lines = self.plan.line_ids.filtered(lambda l: l.stage == 'production')
        old_other = dict(zip(other_lines.ids, other_lines.mapped('date_needed')))

        # Solo la instalación: las tareas no se mueven.
        wizard = self.env['construction.plan.reschedule.wizard'].with_user(
            self.planner).with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.floor.id],
        ).create({'mode': 'shift', 'days': 14, 'stage_production': False,
                  'stage_assembly': False, 'stage_finishing': False})
        self.assertFalse(wizard.move_tasks)
        self.assertEqual(wizard.delta_days, 14)
        self.assertEqual(set(wizard.line_ids.mapped('stage')), {'installation'})
        self.assertTrue(set(screws.ids) <= set(wizard.line_ids.plan_line_id.ids))
        wizard.with_user(self.planner).action_apply()
        for line in screws:
            self.assertEqual(line.date_needed, old[line.id] + timedelta(days=14))
        for line in other_lines:
            self.assertEqual(line.date_needed, old_other[line.id])
        # El requerimiento quedó con fecha anterior a la nueva necesidad:
        # actividad para Logística.
        activity = request.activity_ids
        self.assertEqual(len(activity), 1)
        self.assertTrue(activity.user_id.has_group(
            'al_construction_material_request.group_construction_logistics'))
        self.assertIn('postergó 14 días', activity.note)

    def test_reschedule_new_date_moves_tasks(self):
        start_field = self.env['al.gantt.field.map'].get_map().get('date_start')
        end_field = self.env['al.gantt.field.map'].get_map().get('date_end')
        self.assertTrue(start_field)
        tasks = self.env['project.task'].search([('id', 'child_of', self.apt_501.id)])
        start = datetime(2026, 11, 2, 13, 0)
        for task in tasks:
            values = {start_field: start}
            if end_field:
                values[end_field] = start + timedelta(days=5)
            task.write(values)
        lines = self.plan.line_ids.filtered(lambda l: l.apartment_task_id == self.apt_501)
        lines.with_context(construction_plan_force=True)._compute_date_needed()
        before = {line.id: line.date_needed for line in lines}
        wizard = self.env['construction.plan.reschedule.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.apt_501.id],
        ).create({'mode': 'date', 'date_new': date(2026, 11, 9)})
        self.assertTrue(wizard.move_tasks)
        self.assertEqual(wizard.date_current, date(2026, 11, 2))
        self.assertEqual(wizard.delta_days, 7)
        wizard.action_apply()
        self.assertEqual(set(tasks.mapped(start_field)), {start + timedelta(days=7)})
        for line in lines:
            self.assertEqual(line.date_needed, before[line.id] + timedelta(days=7))
        with self.assertRaises(UserError):
            self.env['construction.plan.reschedule.wizard'].with_context(
                default_plan_id=self.plan.id).create({'mode': 'shift', 'days': 0}).action_apply()

    # ------------------------------------------------------------------
    # Estado del módulo al revertir un avance
    # ------------------------------------------------------------------
    def test_revert_progress_lowers_unit_state(self):
        module = self.env['project.task'].search([('parent_id', '=', self.space_501.id)],
                                                 limit=1)
        module.construction_unit_state = 'production'
        assembly = self.plan.line_ids.filtered(
            lambda l: l.task_id == module and l.stage == 'assembly'
            and l.resource_type == 'contract')
        self.assertTrue(assembly)
        progresses = self.env['construction.task.progress']
        for line in assembly:
            progresses |= self.env['construction.task.progress'].create({
                'task_id': module.id, 'activity_id': line.activity_id.id,
                'date': date(2026, 11, 2), 'qty': line.qty_planned,
                'attachment_ids': [Command.create({'name': 'm.jpg', 'datas': PHOTO})],
            })
        progresses.with_user(self.planner).action_validate()
        self.assertEqual(module.construction_unit_state, 'produced')
        self.assertEqual(module.construction_unit_state_base, 'production')
        self.assertEqual(set(assembly.mapped('line_state')), {'done'})
        progresses[0].with_user(self.planner).action_reset()
        # Vuelve al estado que tenía antes del avance.
        self.assertEqual(module.construction_unit_state, 'production')
        self.assertNotEqual(assembly[0].line_state, 'done')
        # Validado de nuevo, sube otra vez.
        progresses[0].with_user(self.planner).action_validate()
        self.assertEqual(module.construction_unit_state, 'produced')

    # ------------------------------------------------------------------
    # Multicompañía
    # ------------------------------------------------------------------
    def test_multicompany(self):
        other = self.env['res.company'].create({'name': 'Otra constructora (test)'})
        self.env.user.company_ids |= other
        foreign = self.env['hr.employee'].create({
            'name': 'Obrero de otra compañía (test)', 'company_id': other.id})
        with self.assertRaises(UserError):  # check_company
            self.env['construction.plan.crew.wizard'].with_context(
                default_plan_id=self.plan.id,
                construction_selection_task_ids=[self.apt_501.id],
            ).create({'role_id': self.role.id,
                      'resource_ids': [Command.set(foreign.resource_id.ids)]})
        outsider = new_test_user(
            self.env, 'plan_otra_cia_f7', groups='al_construction_planner.group_planner_planner',
            company_id=other.id, company_ids=[(6, 0, [other.id])], name='Otra compañía (test)')
        Line = self.env['construction.resource.plan.line'].with_user(outsider)
        self.assertFalse(Line.search([('line_state', '=', 'planned')]).filtered(
            lambda l: l.plan_id == self.plan))
        # Una OC de la otra compañía no se controla contra el plan de esta.
        self._set_policy('block')
        partner = self.env['res.partner'].create({'name': 'Proveedor B (test)'})
        order = self.env['purchase.order'].with_company(other).create({
            'partner_id': partner.id, 'company_id': other.id,
            'order_line': [Command.create({
                'product_id': self.p_white.id, 'product_qty': 1,
                'price_unit': self.plan.amount_total * 3, 'tax_ids': [Command.clear()],
                'analytic_distribution': {str(self.project.account_id.id): 100.0}})],
        })
        self.assertFalse(order.sudo()._construction_budget_amounts())
