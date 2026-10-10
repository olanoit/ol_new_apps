# -*- coding: utf-8 -*-
from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from .common import load_demo

# PNG de 1 × 1 píxel: la foto del avance.
PHOTO = (b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         b'hQGAhKmMIQAAAABJRU5ErkJggg==')

@tagged('post_install', '-at_install')
class TestContracts(TransactionCase):
    """Fases 5 y 6: asignar contrata (W-05), avance por driver (W-07, P-07),
    avance de los nodos (P-09), liquidación semanal (P-08) con la acción
    programada, aprobación, recepción en la OC y factura. Criterios de
    aceptación 4 a 8 de la especificación sobre el piso 05 del demo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False
        demo = load_demo(cls.env, 'TEST PLAN')
        cls.plan = demo['plan']
        cls.project = demo['project']
        cls.floor = demo['floor']
        cls.leandro = demo['leandro']
        cls.gonza = demo['gonza']
        cls.act = demo['act']
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state

        grp = 'al_construction_planner.group_planner_'
        cls.planner = new_test_user(
            cls.env, 'plan_supervisor_f5', name='Supervisor (test)', groups=f'{grp}planner')
        cls.reporter = new_test_user(
            cls.env, 'plan_capataz_f5', name='Capataz de la contrata (test)',
            groups=f'{grp}progress')
        cls.manager = new_test_user(
            cls.env, 'plan_jefatura_f6', name='Jefatura (test)', groups=f'{grp}manager')
        # Solo la regla de liquidaciones del módulo (jefatura).
        cls.tier_settlement = cls.env.ref(
            'al_construction_planner.tier_contract_settlement_manager')
        cls.env['tier.definition'].search([
            ('model', '=', 'construction.contract.settlement'),
            ('id', '!=', cls.tier_settlement.id)]).active = False
        cls.tier_settlement.active = True

        Task = cls.env['project.task']
        cls.apartments = {
            apt.name: apt for apt in Task.search([
                ('parent_id', '=', cls.floor.id), ('construction_level', '=', 'apartment')])}
        cls.spaces = {name: Task.search([('parent_id', '=', apt.id)])
                      for name, apt in cls.apartments.items()}

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _assign_installation(self, partner=None, user=None):
        wizard = self.env['construction.plan.contract.wizard'].with_user(
            user or self.planner).with_context(
            default_plan_id=self.plan.id,
            construction_selection_task_ids=self.floor.ids,
        ).create({'stage': 'installation', 'partner_id': (partner or self.leandro).id,
                  'date_start': date(2026, 10, 26)})
        return wizard, wizard.action_assign()

    def _line(self, apartment, code):
        return self.plan.line_ids.filtered(
            lambda l: l.task_id == self.spaces[apartment] and l.activity_id == self.act[code])

    def _report(self, apartment, code, qty, day, user=None):
        line = self._line(apartment, code)
        return self.env['construction.task.progress'].with_user(user or self.reporter).create({
            'task_id': line.task_id.id,
            'activity_id': line.activity_id.id,
            'date': day,
            'qty': qty,
            'attachment_ids': [Command.create({'name': 'foto.jpg', 'datas': PHOTO})],
        })

    def _confirm_order(self):
        order = self.env['purchase.order'].search([
            ('construction_is_service_order', '=', True),
            ('partner_id', '=', self.leandro.id),
            ('construction_project_id', '=', self.project.id)])
        order.button_confirm()
        return order

    # Avance del ejemplo de P-08 (bruto 380.88): drivers de la semana
    # repartidos entre los Dpto 501 a 504 sin pasar lo presupuestado.
    EXAMPLE = [
        ('INB', [('Dpto 501', 2.12), ('Dpto 502', 2.55), ('Dpto 503', 2.80), ('Dpto 504', 2.67)]),
        ('RGB', [('Dpto 501', 1.60), ('Dpto 502', 2.00), ('Dpto 503', 2.20), ('Dpto 504', 0.22)]),
        ('INA', [('Dpto 501', 2.10), ('Dpto 502', 2.45), ('Dpto 503', 2.72), ('Dpto 504', 0.09)]),
        ('RGA', [('Dpto 501', 1.60), ('Dpto 502', 1.70), ('Dpto 503', 1.80), ('Dpto 504', 0.23)]),
        ('TAP', [('Dpto 501', 4), ('Dpto 502', 3), ('Dpto 503', 2)]),
        ('REC', [('Dpto 501', 2), ('Dpto 502', 1)]),
        ('PIN', [('Dpto 501', 2), ('Dpto 502', 2), ('Dpto 503', 2)]),
        ('PUS', [('Dpto 501', 2), ('Dpto 502', 2), ('Dpto 503', 2)]),
    ]

    def _report_example(self, day=date(2026, 11, 3)):
        progresses = self.env['construction.task.progress']
        for code, rows in self.EXAMPLE:
            for apartment, qty in rows:
                progresses |= self._report(apartment, code, qty, day)
        return progresses

    # ------------------------------------------------------------------
    # W-05 · Asignar contrata (criterio 4)
    # ------------------------------------------------------------------
    def test_assign_contract(self):
        wizard, _action = self._assign_installation()
        self.assertEqual(len(wizard.line_ids), 8)
        self.assertAlmostEqual(wizard.amount_total, 941.17)
        self.assertAlmostEqual(wizard.retention_total, 94.12)
        self.assertAlmostEqual(wizard.amount_net, 847.05)
        low = wizard.line_ids.filtered(lambda r: r.activity_id == self.act['INB'])
        self.assertAlmostEqual(low.qty, 21.27)
        self.assertEqual(low.price_unit, 18.0)  # tarifa de la obra, no la base (16)
        lines = self.plan.line_ids.filtered(
            lambda l: l.stage == 'installation' and l.resource_type == 'contract')
        # El demo tiene las 8 actividades en los 8 ambientes (64 líneas; el
        # maestro de MOMEN, 59).
        self.assertEqual(wizard.plan_line_count, len(lines))
        self.assertEqual(len(lines), 64)
        self.assertEqual(lines.partner_id, self.leandro)
        order = self.env['purchase.order'].search([
            ('partner_id', '=', self.leandro.id),
            ('construction_project_id', '=', self.project.id)])
        self.assertTrue(order.construction_is_service_order)
        self.assertEqual(order.state, 'draft')
        self.assertEqual(len(order.order_line), 8)
        self.assertAlmostEqual(order.amount_untaxed, 941.17)
        self.assertEqual(set(order.order_line.mapped('construction_retention_pct')), {10.0})
        self.assertEqual(self.plan.state, 'in_progress')
        self.assertTrue(all(lines.mapped(lambda l: l.qty_requested == l.qty_planned)))
        # Sin saldo por asignar: la misma selección ya no propone nada y una
        # segunda asignación no duplica la OC.
        wizard2 = self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.floor.ids,
        ).create({'stage': 'installation', 'partner_id': self.leandro.id})
        self.assertFalse(wizard2.line_ids)
        self.assertEqual(wizard2.purchase_order_id, order)
        with self.assertRaises(UserError):
            wizard2.action_assign()

    def test_assign_other_contract_keeps_first(self):
        self._assign_installation()
        # Las líneas de otra contrata no se reasignan (ni tienen saldo).
        wizard = self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.floor.ids,
        ).create({'stage': 'assembly', 'partner_id': self.gonza.id})
        self.assertTrue(wizard.line_ids)
        wizard.action_assign()
        assembly = self.plan.line_ids.filtered(
            lambda l: l.stage == 'assembly' and l.resource_type == 'contract')
        self.assertEqual(assembly.partner_id, self.gonza)
        orders = self.env['purchase.order'].search([
            ('construction_project_id', '=', self.project.id)])
        self.assertEqual(orders.partner_id, self.leandro | self.gonza)

    # ------------------------------------------------------------------
    # W-07 y avance por driver (criterio 5)
    # ------------------------------------------------------------------
    def test_progress_and_node_percentage(self):
        self._assign_installation()
        line = self._line('Dpto 504', 'INB')
        self.assertAlmostEqual(line.qty_planned, 2.70)
        progress = self._report('Dpto 504', 'INB', 2.70, date(2026, 11, 3))
        self.assertTrue(progress.name.startswith('AVN/'))
        self.assertEqual(progress.plan_line_id, line)
        self.assertEqual(progress.partner_id, self.leandro)
        # Reportado no suma: solo lo validado.
        self.assertEqual(line.qty_executed, 0.0)
        with self.assertRaises(UserError):
            progress.with_user(self.reporter).action_validate()
        progress.with_user(self.planner).action_validate()
        self.assertEqual(progress.state, 'validated')
        self.assertAlmostEqual(line.qty_executed, 2.70)
        self.assertEqual(line.progress_pct, 1.0)
        self.assertEqual(line.line_state, 'done')
        # Cocina del Dpto 504 (tipología 04): instalación 115.10, mueble bajo
        # 2.70 × 18 = 48.60 → 42.2 % (en el maestro, 49.68 ÷ 131.06 = 37.9 %).
        space = self.spaces['Dpto 504']
        domain = space._construction_plan_domain() + [('stage', '=', 'installation')]
        executed, planned = self.plan._progress_amounts(domain)[False]
        self.assertAlmostEqual(planned, 115.10)
        self.assertAlmostEqual(executed, 48.60)
        node = next(n for n in self.plan.get_tree_nodes(
            str(self.apartments['Dpto 504'].id), {'stages': ['installation']}))
        self.assertAlmostEqual(node['progress'], 0.4222)
        self.assertGreater(space.construction_progress_pct, 0.0)
        self.assertIn(line, space.construction_current_line_ids)
        # Periodo de liquidación: jueves 29/10 a miércoles 04/11, se liquida
        # el jueves 05/11.
        self.assertEqual(progress.period_start, date(2026, 10, 29))
        self.assertEqual(progress.settlement_date_planned, date(2026, 11, 5))

    def test_progress_wizard_balance_and_tolerance(self):
        self._assign_installation()
        attachment = self.env['ir.attachment'].with_user(self.reporter).create(
            {'name': 'cocina.jpg', 'datas': PHOTO})
        wizard = self.env['construction.plan.progress.wizard'].with_user(self.reporter) \
            .with_context(default_plan_id=self.plan.id,
                          construction_selection_task_ids=self.apartments['Dpto 501'].ids) \
            .create({'activity_id': self.act['INB'].id, 'date': date(2026, 11, 2),
                     'attachment_ids': [Command.set(attachment.ids)]})
        self.assertIn(self.act['INB'], wizard.available_activity_ids)
        self.assertEqual(len(wizard.line_ids), 1)
        row = wizard.line_ids
        # Por defecto el saldo (P-06).
        self.assertAlmostEqual(row.qty_report, 2.12)
        row.qty_report = 2.50
        with self.assertRaises(UserError):
            wizard.action_register()
        row.qty_report = 1.00
        action = wizard.action_register()
        progress = self.env['construction.task.progress'].browse(action['domain'][0][2])
        self.assertEqual(progress.qty, 1.0)
        self.assertEqual(len(progress.attachment_ids), 1)
        self.assertNotEqual(progress.attachment_ids, attachment)
        self.assertEqual(progress.attachment_ids.res_id, progress.id)
        # Lo reportado sin validar ya cuenta para el saldo.
        line = progress.plan_line_id
        with self.assertRaises(ValidationError):
            self._report('Dpto 501', 'INB', 1.20, date(2026, 11, 2))
        # Con 10 % de tolerancia en el plan se admite hasta 2.12 × 1.1 = 2.33.
        self.plan.exceed_tolerance = 10.0
        self._report('Dpto 501', 'INB', 1.20, date(2026, 11, 2))
        with self.assertRaises(ValidationError):
            self._report('Dpto 501', 'INB', 0.20, date(2026, 11, 2))
        self.assertAlmostEqual(line._get_reported_qty(), 2.20)

    def test_photos_required(self):
        self._assign_installation()
        line = self._line('Dpto 501', 'INB')
        with self.assertRaises(ValidationError):
            self.env['construction.task.progress'].create({
                'task_id': line.task_id.id, 'activity_id': line.activity_id.id, 'qty': 1.0})
        wizard = self.env['construction.plan.progress.wizard'].with_context(
            default_plan_id=self.plan.id,
            construction_selection_task_ids=self.apartments['Dpto 501'].ids,
        ).create({'activity_id': self.act['INB'].id})
        with self.assertRaises(UserError):
            wizard.action_register()

    def test_reject_and_reset(self):
        self._assign_installation()
        progress = self._report('Dpto 502', 'INA', 1.0, date(2026, 11, 2))
        action = progress.with_user(self.planner).action_open_reject_wizard()
        reason = self.env['construction.reason.wizard'].with_user(self.planner).with_context(
            action['context']).create({'reason': 'La foto no muestra el mueble.'})
        reason.action_confirm()
        self.assertEqual(progress.state, 'rejected')
        self.assertEqual(progress.reject_reason, 'La foto no muestra el mueble.')
        # Rechazado no cuenta para el saldo; la contrata corrige y vuelve a
        # reportado.
        progress.with_user(self.planner).action_reset()
        self.assertEqual(progress.state, 'draft')
        progress.with_user(self.reporter).qty = 2.0
        progress.with_user(self.planner).action_validate()
        with self.assertRaises(UserError):
            progress.with_user(self.reporter).qty = 1.0
        # Validado y no liquidado: se revierte.
        progress.with_user(self.planner).action_reset()
        self.assertEqual(progress.state, 'draft')
        self.assertEqual(self._line('Dpto 502', 'INA').qty_executed, 0.0)

    def test_unit_state_from_progress(self):
        """Toda la instalación del ambiente validada: sus módulos quedan
        Instalados; todo el armado de un módulo: Producido."""
        self._assign_installation()
        space = self.spaces['Dpto 508']
        modules = self.env['project.task'].search([('parent_id', '=', space.id)])
        self.assertTrue(modules)
        module = modules[0]
        assembly = self.plan.line_ids.filtered(
            lambda l: l.task_id == module and l.stage == 'assembly'
            and l.resource_type == 'contract')
        self.assertTrue(assembly)
        for line in assembly:
            self.env['construction.task.progress'].create({
                'task_id': module.id, 'activity_id': line.activity_id.id,
                'date': date(2026, 11, 2), 'qty': line.qty_planned,
                'attachment_ids': [Command.create({'name': 'm.jpg', 'datas': PHOTO})],
            }).with_user(self.planner).action_validate()
        self.assertEqual(module.construction_unit_state, 'produced')
        self.assertEqual(modules[1].construction_unit_state, 'planned')
        progresses = self.env['construction.task.progress']
        for line in self.plan.line_ids.filtered(
                lambda l: l.task_id == space and l.stage == 'installation'
                and l.resource_type == 'contract'):
            progresses |= self._report('Dpto 508', line.activity_id.code.split('-')[1],
                                       line.qty_planned, date(2026, 11, 2))
        progresses.with_user(self.planner).action_validate()
        self.assertEqual(set(modules.mapped('construction_unit_state')), {'installed'})

    # ------------------------------------------------------------------
    # Liquidación semanal (criterios 6 a 8)
    # ------------------------------------------------------------------
    def test_weekly_settlement(self):
        self._assign_installation()
        order = self._confirm_order()
        example = self._report_example()
        example.with_user(self.planner).action_validate()
        # Reportado el jueves 05/11 (siguiente periodo) y uno sin validar.
        late = self._report('Dpto 505', 'INB', 1.0, date(2026, 11, 5))
        late.with_user(self.planner).action_validate()
        pending = self._report('Dpto 506', 'INB', 1.0, date(2026, 11, 4))

        Settlement = self.env['construction.contract.settlement']
        # El miércoles aún no hay liquidación.
        self.assertFalse(Settlement._prepare_settlements(date(2026, 11, 4), self.project))
        settlement = Settlement._prepare_settlements(date(2026, 11, 5), self.project)
        self.assertEqual(len(settlement), 1)
        self.assertTrue(settlement.name.startswith('LIQ/'))
        self.assertEqual(settlement.partner_id, self.leandro)
        self.assertEqual(settlement.purchase_order_id, order)
        self.assertEqual(settlement.period_start, date(2026, 10, 29))
        self.assertEqual(settlement.period_end, date(2026, 11, 4))
        self.assertEqual(settlement.settlement_date, date(2026, 11, 5))
        self.assertEqual(settlement.payment_date, date(2026, 11, 7))
        self.assertEqual(settlement.progress_ids, example)
        self.assertNotIn(late, settlement.progress_ids)
        self.assertNotIn(pending, settlement.progress_ids)
        self.assertEqual(len(settlement.line_ids), 8)
        self.assertAlmostEqual(settlement.amount_gross, 380.88)
        self.assertAlmostEqual(settlement.retention_amount, 38.09)
        self.assertAlmostEqual(settlement.amount_net, 342.79)
        low = settlement.line_ids.filtered(lambda l: l.activity_id == self.act['INB'])
        self.assertAlmostEqual(low.qty_period, 10.14)
        self.assertAlmostEqual(low.amount, 182.52)
        # Acumulado y avance informativos: todo lo validado de la contrata
        # (también el 1.00 ML del 05/11, que se liquida la semana siguiente).
        self.assertAlmostEqual(low.qty_planned, 21.27)
        self.assertAlmostEqual(low.qty_cumulative, 11.14)
        self.assertAlmostEqual(low.progress_pct, 11.14 / 21.27)
        self.assertAlmostEqual(settlement.amount_planned, 941.17)
        self.assertAlmostEqual(settlement.progress_pct, (380.88 + 18.0) / 941.17, places=3)
        # Idempotente: otra pasada el mismo día no duplica.
        self.assertFalse(Settlement._prepare_settlements(date(2026, 11, 5), self.project))
        self.assertEqual(Settlement.search_count([('project_id', '=', self.project.id)]), 1)

        # Flujo: presentar, devolver con motivo, validar y aprobar (jefatura).
        settlement.with_user(self.planner).action_submit()
        action = settlement.with_user(self.planner).action_open_return_wizard()
        self.env['construction.reason.wizard'].with_user(self.planner).with_context(
            action['context']).create({'reason': 'Faltan fotos del Dpto 503.'}).action_confirm()
        self.assertEqual(settlement.state, 'draft')
        settlement.with_user(self.planner).action_submit()
        settlement.with_user(self.planner).action_validate()
        self.assertEqual(settlement.state, 'validated')
        self.assertTrue(settlement.review_ids)
        # El avance en una liquidación validada no se revierte.
        with self.assertRaises(UserError):
            example[:1].with_user(self.planner).action_reset()
        settlement.with_user(self.manager).validate_tier()
        self.assertEqual(settlement.state, 'approved')
        # Recepción en la OC de lo de la semana y factura con vencimiento el
        # sábado.
        po_low = low.purchase_line_id
        self.assertAlmostEqual(po_low.qty_received, 10.14)
        invoice = settlement.invoice_id
        self.assertEqual(invoice.move_type, 'in_invoice')
        self.assertEqual(invoice.invoice_date_due, date(2026, 11, 7))
        self.assertAlmostEqual(invoice.amount_untaxed, 380.88)
        self.assertIn(invoice, order.invoice_ids)
        self.assertTrue(all(example.mapped('settled')))
        self.assertAlmostEqual(self._line('Dpto 501', 'INB').qty_settled, 2.12)
        with self.assertRaises(UserError):
            example[:1].with_user(self.planner).action_reset()

        # El avance del 05/11 entra a la liquidación del 12/11, con el
        # validado tarde (rezagado) del 04/11.
        pending.with_user(self.planner).action_validate()
        next_week = Settlement._prepare_settlements(date(2026, 11, 12), self.project)
        self.assertEqual(next_week.period_start, date(2026, 11, 5))
        self.assertEqual(next_week.payment_date, date(2026, 11, 14))
        self.assertEqual(next_week.progress_ids, late | pending)

        # Pagada al quedar pagada la factura.
        invoice.invoice_date = date(2026, 11, 5)
        if invoice.l10n_latam_use_documents if 'l10n_latam_use_documents' in invoice else False:
            # Localización con documentos (Perú): número del comprobante de la
            # contrata.
            invoice.l10n_latam_document_number = 'E001-77'
        invoice.action_post()
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({})._create_payments()
        expected = 'paid' if invoice.payment_state == 'paid' else 'approved'
        self.assertEqual(settlement.state, expected)

    def test_settlement_cannot_receive_more_than_ordered(self):
        self._assign_installation()
        order = self._confirm_order()
        progress = self._report('Dpto 501', 'INB', 2.12, date(2026, 11, 2))
        progress.with_user(self.planner).action_validate()
        settlement = self.env['construction.contract.settlement']._prepare_settlements(
            date(2026, 11, 5), self.project)
        settlement.action_submit()
        po_line = settlement.line_ids.purchase_line_id
        po_line.product_qty = 1.0
        self.tier_settlement.active = False
        with self.assertRaises(UserError):
            settlement.action_validate()
        self.assertEqual(po_line.qty_received, 0.0)
        self.assertEqual(settlement.state, 'submitted')
        # Con la OC sin confirmar tampoco se aprueba.
        po_line.product_qty = 21.27
        order.button_cancel()
        order.button_draft()
        with self.assertRaises(UserError):
            settlement.action_validate()

    def test_settlement_period_and_holidays(self):
        Settlement = self.env['construction.contract.settlement']
        with self.assertRaises(ValidationError):
            Settlement.create({'partner_id': self.leandro.id, 'project_id': self.project.id,
                               'period_start': date(2026, 10, 30)})
        # Jueves 05/11 feriado: la liquidación se corre al miércoles 04/11; el
        # sábado 07/11 feriado: el pago, al viernes 06/11.
        calendar = self.env.company.resource_calendar_id
        calendar.tz = 'America/Lima'
        self.env['resource.calendar.leaves'].create([
            {'name': 'Feriado (test)', 'calendar_id': calendar.id,
             'date_from': '2026-11-05 13:00:00', 'date_to': '2026-11-05 18:00:00'},
            {'name': 'Feriado (test)', 'calendar_id': calendar.id,
             'date_from': '2026-11-07 13:00:00', 'date_to': '2026-11-07 18:00:00'},
        ])
        settlement = Settlement.create({'partner_id': self.leandro.id,
                                        'project_id': self.project.id,
                                        'period_start': date(2026, 10, 29)})
        self.assertEqual(settlement.settlement_date, date(2026, 11, 4))
        self.assertEqual(settlement.payment_date, date(2026, 11, 6))
        # Semana configurada por obra: lunes a domingo, liquidación martes.
        self.project.write({'construction_week_start_day': '0',
                            'construction_settlement_day': '1',
                            'construction_payment_day': '4'})
        self.assertEqual(self.project._construction_period(date(2026, 11, 4)),
                         (date(2026, 11, 2), date(2026, 11, 8)))
        self.assertEqual(self.project._construction_settlement_dates(date(2026, 11, 2)),
                         (date(2026, 11, 10), date(2026, 11, 13)))

    def test_close_blocked_and_replan_transfer(self):
        self._assign_installation()
        progress = self._report('Dpto 501', 'INB', 1.0, date(2026, 11, 2))
        progress.with_user(self.planner).action_validate()
        with self.assertRaises(UserError):
            self.plan.action_close()
        # Nueva versión: el avance no liquidado pasa a la línea que continúa.
        wizard = self.env['construction.plan.replan.wizard'].create({
            'plan_id': self.plan.id, 'mode': 'all', 'reason': 'Cambio de alcance (test).'})
        new_plan = self.env['construction.resource.plan'].browse(
            wizard.action_create_version()['res_id'])
        new_plan.action_request_approval()
        self.assertEqual(new_plan.state, 'approved')
        self.assertEqual(progress.plan_id, new_plan)
        self.assertEqual(progress.plan_line_id.previous_line_id, self._line('Dpto 501', 'INB'))

    def test_security_and_multicompany(self):
        self._assign_installation()
        progress = self._report('Dpto 501', 'INB', 1.0, date(2026, 11, 2))
        outsider = new_test_user(self.env, 'plan_ajeno_f5', groups='base.group_user')
        with self.assertRaises(AccessError):
            progress.with_user(outsider).read(['qty'])
        with self.assertRaises(AccessError):
            self.env['construction.contract.settlement'].with_user(self.reporter).create({
                'partner_id': self.leandro.id, 'project_id': self.project.id,
                'period_start': date(2026, 10, 29)})
        other = self.env['res.company'].create({'name': 'Otra constructora (test)'})
        user_other = new_test_user(
            self.env, 'plan_otra_f5', company_id=other.id, company_ids=[Command.set(other.ids)],
            groups='al_construction_planner.group_planner_manager')
        Progress = self.env['construction.task.progress'].with_user(user_other)
        self.assertFalse(Progress.search([('id', '=', progress.id)]))
        self.assertFalse(self.env['construction.contract.settlement'].with_user(user_other).search(
            [('project_id', '=', self.project.id)]))
