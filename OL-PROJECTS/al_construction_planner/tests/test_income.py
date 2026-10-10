# -*- coding: utf-8 -*-
from datetime import date, datetime

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged
from odoo.tests.common import TransactionCase

# PNG de 1 × 1 píxel: la foto del avance.
PHOTO = (b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         b'hQGAhKmMIQAAAABJRU5ErkJggg==')
PRICE = 159231.23


@tagged('post_install', '-at_install')
class TestIncome(TransactionCase):
    """Fase 10, ruta del ingreso: calendario e ingresos de la obra (P-21),
    entrega semanal (P-19) y valorización con el cliente (P-20) con W-13 y
    W-14. Criterios de aceptación 16 y 17 de la especificación.

    La partida «Cocinas» (S/ 159,231.23) reúne un plan de S/ 170,764.10:
    contrata 13,000 × 4.00, material 1,200 × 98.93 y un servicio de 48.10.
    Hasta el 28/10 hay S/ 47,984.71 ejecutados (28.10 %); en la semana del
    29/10 al 04/11 se suman 5,552.96 de contrata y 19,786.00 de material
    consumido (42.94 %)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False
        cls.company = cls.env.company
        # Calendario de lunes a viernes y feriado del 25/12 (P-21, nota 2).
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Lunes a viernes (test)', 'company_id': cls.company.id, 'tz': 'America/Lima',
            'attendance_ids': [Command.clear()] + [Command.create({
                'name': 'Día %s' % day, 'dayofweek': str(day), 'hour_from': 8, 'hour_to': 17,
                'day_period': 'full_day'}) for day in range(5)]})
        cls.company.construction_income_calendar_id = cls.calendar
        cls.env['resource.calendar.leaves'].create({
            'name': 'Navidad (test)', 'calendar_id': cls.calendar.id,
            'company_id': cls.company.id,
            'date_from': datetime(2026, 12, 25, 5, 0), 'date_to': datetime(2026, 12, 26, 4, 59)})

        grp = 'al_construction_planner.group_planner_'
        cls.planner = new_test_user(
            cls.env, 'ing_supervisor', name='Supervisor (test)', groups=f'{grp}planner')
        cls.manager = new_test_user(
            cls.env, 'ing_jefatura', name='Jefatura (test)', groups=f'{grp}manager')
        cls.projects_user = new_test_user(
            cls.env, 'ing_proyectos', name='Proyectos (test)', groups=f'{grp}user')
        cls.finance = new_test_user(
            cls.env, 'ing_finanzas', name='Finanzas (test)',
            groups=f'{grp}revenue,account.group_account_invoice,'
                   'sales_team.group_sale_salesman_all_leads')

        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.project = cls.env['project.project'].create({
            'name': 'Obra MOMEN ingresos (test)', 'is_construction_site': True,
            'company_id': cls.company.id, 'date_start': date(2026, 10, 12), 'date': date(2026, 12, 18)})
        cls.project._create_analytic_account()
        cls.project.construction_collection_days = 30
        Task = cls.env['project.task']
        cls.floor = Task.create({'name': 'Piso 05', 'project_id': cls.project.id,
                                 'construction_level': 'floor'})
        cls.apartment = Task.create({'name': 'Dpto 501', 'project_id': cls.project.id,
                                     'construction_level': 'apartment',
                                     'parent_id': cls.floor.id})
        cls.typology = cls.env['construction.typology'].create({
            'project_id': cls.project.id, 'code': 'ING01', 'name': 'Cocina ingresos',
            'family': 'kitchen'})
        cls.space = Task.create({'name': 'Cocina', 'project_id': cls.project.id,
                                 'construction_level': 'space', 'parent_id': cls.apartment.id,
                                 'construction_typology_id': cls.typology.id})
        cls.activity = cls.env['construction.labor.activity'].create({
            'code': 'ING-INS', 'name': 'Instalación (test ingresos)', 'stage': 'installation',
            'default_price': 4.0, 'uom_id': cls.unit.id})
        Product = cls.env['product.product']
        cls.material = Product.create({'name': 'Melamina (test ingresos)', 'type': 'consu'})
        cls.service = Product.create({'name': 'Flete (test ingresos)', 'type': 'service'})
        cls.kitchen = Product.create({'name': 'Cocina fabricada (test ingresos)', 'type': 'consu'})
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.kitchen.product_tmpl_id.id, 'product_qty': 1.0,
            'bom_line_ids': [Command.create({'product_id': cls.material.id, 'product_qty': 1})]})

        cls.plan = cls.env['construction.resource.plan'].create({'project_id': cls.project.id})
        Line = cls.env['construction.resource.plan.line']
        base = {'plan_id': cls.plan.id, 'task_id': cls.space.id, 'product_uom_id': cls.unit.id}
        cls.contract_line = Line.create(dict(base, resource_type='contract', stage='installation',
                                             activity_id=cls.activity.id, qty_planned=13000,
                                             price_unit_planned=4.0))
        cls.material_line = Line.create(dict(base, resource_type='material', stage='production',
                                             product_id=cls.material.id, qty_planned=1200,
                                             price_unit_planned=98.93))
        cls.service_line = Line.create(dict(base, resource_type='service', stage='finishing',
                                            product_id=cls.service.id, qty_planned=1,
                                            price_unit_planned=48.10))
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state

        # Contrato: una línea de la OV por partida, cantidad 1 (D23).
        customer_vals = {'name': 'Inmobiliaria MOMEN (test)', 'vat': '20557912879',
                         'is_company': True}
        ruc = cls.env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
        if ruc:
            # Localización peruana: la factura exige el RUC del cliente.
            customer_vals['l10n_latam_identification_type_id'] = ruc.id
        cls.customer = cls.env['res.partner'].create(customer_vals)
        cls.tax = cls.env['account.tax'].search([
            *cls.env['account.tax']._check_company_domain(cls.company),
            ('type_tax_use', '=', 'sale'), ('amount_type', '=', 'percent'),
            ('amount', '=', 18.0), ('price_include', '=', False)], limit=1)
        cls.partida_product = cls.env['product.product'].create({
            'name': 'Cocinas (test)', 'type': 'service', 'invoice_policy': 'delivery'})
        if 'service_type' in cls.partida_product._fields:
            # Entregado a mano (sin hoja de horas de sale_timesheet).
            cls.partida_product.service_type = 'manual'
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.customer.id,
            'order_line': [Command.create({
                'product_id': cls.partida_product.id, 'name': 'Cocinas',
                'product_uom_qty': 1, 'price_unit': PRICE,
                'tax_ids': [Command.set(cls.tax.ids)]})],
        })
        cls.order.action_confirm()
        cls.partida = cls.order.order_line
        cls.project.construction_sale_order_id = cls.order

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _progress(self, qty, day):
        progress = self.env['construction.task.progress'].create({
            'task_id': self.space.id, 'activity_id': self.activity.id, 'date': day, 'qty': qty,
            'attachment_ids': [Command.create({'name': 'foto.jpg', 'datas': PHOTO})]})
        progress.with_user(self.planner).action_validate()
        return progress

    def _consume(self, qty, day):
        """OF terminada con ``qty`` de material, consumido en ``day``."""
        production = self.env['mrp.production'].create({
            'product_id': self.kitchen.id, 'product_qty': qty, 'bom_id': self.bom.id})
        production.action_confirm()
        production.qty_producing = qty
        for move in production.move_raw_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        production.button_mark_done()
        production.move_raw_ids.write({'date': datetime.combine(day, datetime.min.time())})
        self.env['construction.resource.plan.allocation'].create({
            'plan_line_id': self.material_line.id, 'kind': 'production',
            'production_id': production.id, 'qty_allocated': qty})
        return production

    def _execute_until_week(self):
        """Ejecutado hasta el 28/10 (S/ 47,984.71 = 28.10 %) y la semana del
        29/10 al 04/11 (contrata 5,552.96 y material 19,786.00)."""
        self._progress(4502.23, date(2026, 10, 22))
        self._consume(303, date(2026, 10, 20))
        first = self.env['construction.weekly.delivery']._prepare_deliveries(
            today=date(2026, 10, 29), projects=self.project)
        self._progress(1388.24, date(2026, 11, 2))
        self._consume(200, date(2026, 11, 1))
        return first

    def _confirm(self, deliveries):
        deliveries.with_user(self.manager).action_confirm()

    def _prepare_valuation(self, cutoff):
        wizard = self.env['construction.valuation.prepare.wizard'].with_user(
            self.projects_user).create({'project_id': self.project.id, 'cutoff_date': cutoff})
        action = wizard.action_create()
        return self.env['construction.valuation'].browse(action['res_id'])

    def _confirm_valuation(self, valuation, amounts=None, **vals):
        wizard = self.env['construction.valuation.confirm.wizard'].with_user(
            self.projects_user).with_context(default_valuation_id=valuation.id).create(dict({
                'confirm_date': date(2026, 11, 18), 'confirm_name': 'Ing. Rosa Quispe',
                'confirm_role': 'Residente de obra',
                'attachment_ids': [Command.create({'name': 'conformidad.pdf', 'datas': PHOTO})],
            }, **vals))
        for line in wizard.line_ids:
            if amounts and line.sale_line_id in amounts:
                line.amount_confirmed = amounts[line.sale_line_id]
        wizard.action_confirm()

    # ------------------------------------------------------------------
    # P-19 · Entrega semanal (criterio 16)
    # ------------------------------------------------------------------
    def test_weekly_delivery_accrues_revenue(self):
        first = self._execute_until_week()
        self.assertEqual(first.period_start, date(2026, 10, 22))
        self.assertAlmostEqual(first.line_ids.progress_end, 0.2810, places=4)
        self.assertAlmostEqual(first.line_ids.amount_planned, 170764.10)
        self._confirm(first)
        Delivery = self.env['construction.weekly.delivery']
        # Antes del día de liquidación (jueves 05/11) no se prepara.
        self.assertFalse(Delivery._prepare_deliveries(today=date(2026, 11, 4),
                                                      projects=self.project))
        delivery = Delivery._prepare_deliveries(today=date(2026, 11, 5), projects=self.project)
        self.assertEqual(delivery.period_start, date(2026, 10, 29))
        self.assertEqual(delivery.period_end, date(2026, 11, 4))
        self.assertTrue(delivery.name.startswith('ENT/'))
        line = delivery.line_ids
        self.assertEqual(line.sale_line_id, self.partida)
        self.assertAlmostEqual(line.price, PRICE)
        self.assertAlmostEqual(line.progress_prev, 0.2810, places=4)
        self.assertAlmostEqual(line.progress_end, 0.4294, places=4)
        # 159,231.23 × (42.94 % − 28.10 %) con el avance sin redondear.
        self.assertAlmostEqual(delivery.revenue_amount, 23627.65)
        self.assertAlmostEqual(delivery.cost_contract, 5552.96)
        self.assertAlmostEqual(delivery.cost_material, 19786.00)
        self.assertAlmostEqual(delivery.cost_labor, 0.0)
        self.assertAlmostEqual(delivery.cost_amount, 25338.96)
        self.assertAlmostEqual(delivery.margin_amount, -1711.31)
        self.assertEqual(len(delivery.progress_ids), 1)

        # La confirma la Jefatura; el supervisor no.
        with self.assertRaises(UserError):
            delivery.with_user(self.planner).action_confirm()
        self._confirm(delivery)
        self.assertEqual(delivery.state, 'confirmed')
        # Un avance validado después de confirmar cae en la entrega siguiente.
        late = self._progress(100, date(2026, 11, 3))
        following = Delivery._prepare_deliveries(today=date(2026, 11, 12), projects=self.project)
        self.assertEqual(following.period_start, date(2026, 11, 5))
        self.assertIn(late, following.progress_ids)
        self.assertNotIn(late, delivery.progress_ids)
        self.assertAlmostEqual(following.cost_contract, 400.0)
        self.assertAlmostEqual(following.revenue_amount,
                               round(PRICE * 400.0 / 170764.10, 2))
        # Con una entrega posterior confirmada no se reabre la anterior.
        self._confirm(following)
        with self.assertRaises(UserError):
            delivery.with_user(self.manager).action_draft()

    def test_delivery_confirm_in_order(self):
        first = self._execute_until_week()
        second = self.env['construction.weekly.delivery']._prepare_deliveries(
            today=date(2026, 11, 5), projects=self.project)
        with self.assertRaises(UserError):
            self._confirm(second)
        self._confirm(first | second)
        self.assertEqual(set((first | second).mapped('state')), {'confirmed'})
        second.with_user(self.manager).action_draft()
        self.assertEqual(second.state, 'draft')

    # ------------------------------------------------------------------
    # P-20 · Valorización (criterio 17)
    # ------------------------------------------------------------------
    def test_valuation_flow_and_invoice(self):
        first = self._execute_until_week()
        second = self.env['construction.weekly.delivery']._prepare_deliveries(
            today=date(2026, 11, 5), projects=self.project)
        self._confirm(first | second)

        # W-13: entregas confirmadas no valorizadas hasta el corte.
        wizard = self.env['construction.valuation.prepare.wizard'].with_user(
            self.projects_user).create({'project_id': self.project.id,
                                        'cutoff_date': date(2026, 11, 11)})
        self.assertEqual(wizard.delivery_ids, first | second)
        delivered = round(PRICE * second.line_ids.progress_end, 2)
        self.assertAlmostEqual(wizard.amount_delivered, delivered)
        valuation = self._prepare_valuation(date(2026, 11, 11))
        self.assertEqual(valuation.sequence_number, 1)
        self.assertEqual(valuation.state, 'draft')
        self.assertEqual(valuation.delivery_ids, first | second)
        self.assertAlmostEqual(valuation.amount_delivered, delivered)
        self.assertAlmostEqual(valuation.line_ids.progress_cumulative,
                               second.line_ids.progress_end, places=6)
        # Fechas previstas desde el corte del 11/11: 13/11, 18/11, 20/11 y 21/12.
        self.assertEqual(valuation.planned_submit_date, date(2026, 11, 13))
        self.assertEqual(valuation.planned_confirm_date, date(2026, 11, 18))
        self.assertEqual(valuation.planned_invoice_date, date(2026, 11, 20))
        self.assertEqual(valuation.planned_collection_date, date(2026, 12, 21))
        self.assertAlmostEqual(valuation.amount_guarantee, round(delivered * 0.05, 2))
        # Ya en una valorización: no se prepara otra con las mismas entregas.
        with self.assertRaises(UserError):
            self._prepare_valuation(date(2026, 11, 11))

        # Enviar (con el PDF en el historial), observar y reenviar.
        valuation.with_user(self.projects_user).action_send()
        self.assertEqual(valuation.state, 'sent')
        self.assertTrue(valuation.submit_date)
        self.assertTrue(valuation.message_ids.attachment_ids.filtered(
            lambda a: a.name.endswith('.pdf')))
        self.env['construction.reason.wizard'].with_user(self.projects_user).with_context(
            active_model='construction.valuation', active_ids=valuation.ids,
            construction_reason_action='observe').create({
                'reason': 'Dos cocinas del piso 06 con puertas por regular.'}).action_confirm()
        self.assertEqual(valuation.state, 'observed')
        self.assertEqual(len(valuation.observation_ids), 1)
        self.assertEqual(valuation.observation_ids.author_id, self.projects_user.partner_id)
        valuation.with_user(self.projects_user).action_send()
        self.assertEqual(valuation.state, 'sent')

        # Sin fecha, nombre, cargo y documento no pasa a Confirmada.
        with self.assertRaises(UserError):
            self._confirm_valuation(valuation, attachment_ids=[])
        with self.assertRaises(ValidationError):
            valuation._action_confirm({
                'confirm_date': date(2026, 11, 18), 'confirm_name': 'Ing. Rosa Quispe',
                'confirm_role': False, 'confirm_attachment_ids': [Command.create({
                    'name': 'conformidad.pdf', 'datas': PHOTO})]}, {})
        with self.assertRaises(ValidationError):
            valuation.state = 'confirmed'
        self.assertEqual(valuation.state, 'sent')
        # Sin Confirmada no se factura.
        with self.assertRaises(UserError):
            valuation.with_user(self.finance).action_create_invoice()

        # El cliente confirma 1,000.00 menos: queda por valorizar.
        confirmed = delivered - 1000.0
        self._confirm_valuation(valuation, amounts={self.partida: confirmed})
        self.assertEqual(valuation.state, 'confirmed')
        self.assertEqual(valuation.confirm_name, 'Ing. Rosa Quispe')
        self.assertTrue(valuation.confirm_attachment_ids)
        self.assertEqual(valuation.confirm_attachment_ids.res_id, valuation.id)
        self.assertAlmostEqual(valuation.amount_confirmed, confirmed)
        self.assertAlmostEqual(valuation.amount_pending, 1000.0)
        self.assertEqual(set((first | second).mapped('state')), {'valued'})

        # Factura de Administración y Finanzas: cantidad entregada de la OV al
        # % acumulado confirmado y no más que lo confirmado.
        with self.assertRaises(UserError):
            valuation.with_user(self.projects_user).action_create_invoice()
        valuation.with_user(self.finance).action_create_invoice()
        invoice = valuation.invoice_id
        self.assertEqual(invoice.construction_valuation_id, valuation)
        invoice_line = invoice.invoice_line_ids.filtered('sale_line_ids')
        self.assertEqual(invoice_line.sale_line_ids, self.partida)
        cumulative = round(confirmed / PRICE, 2)
        self.assertAlmostEqual(invoice_line.quantity, cumulative)
        self.assertAlmostEqual(self.partida.qty_delivered, cumulative)
        self.assertAlmostEqual(invoice.amount_untaxed, confirmed, delta=0.01)
        self.assertLessEqual(invoice_line.price_subtotal, confirmed)
        self.assertIn(valuation.line_ids, self.partida.construction_valuation_line_ids)
        # Subir el precio en la factura la deja por encima de lo confirmado.
        invoice_line.price_unit += 100
        with self.assertRaises(UserError):
            invoice.action_post()
        invoice_line.price_unit -= 100
        invoice.action_post()
        self.assertEqual(valuation.state, 'invoiced')
        invoice.button_draft()
        self.assertEqual(valuation.state, 'confirmed')
        invoice.action_post()
        self.assertEqual(valuation.state, 'invoiced')

        # La siguiente valorización recoge lo no confirmado.
        self._progress(1000, date(2026, 11, 9))
        third = self.env['construction.weekly.delivery']._prepare_deliveries(
            today=date(2026, 11, 12), projects=self.project)
        self._confirm(third)
        following = self._prepare_valuation(date(2026, 11, 25))
        self.assertEqual(following.sequence_number, 2)
        self.assertAlmostEqual(following.line_ids.confirmed_before, confirmed)
        self.assertAlmostEqual(following.line_ids.progress_prev, confirmed / PRICE, places=6)
        expected = round(PRICE * third.line_ids.progress_end - confirmed, 2)
        self.assertAlmostEqual(following.amount_delivered, expected)
        self.assertGreater(following.amount_delivered, third.revenue_amount + 999.0)

    def test_invoice_guarantee_line(self):
        """Con cuenta del fondo de garantía en Ajustes, la factura lleva el
        fondo como línea negativa sin impuestos y su total es el neto."""
        account = self.env['account.account'].search([
            *self.env['account.account']._check_company_domain(self.company),
            ('account_type', '=', 'asset_current')], limit=1)
        self.company.construction_guarantee_account_id = account
        first = self._execute_until_week()
        self._confirm(first)
        valuation = self._prepare_valuation(date(2026, 10, 28))
        valuation.with_user(self.projects_user).action_send()
        self._confirm_valuation(valuation)
        valuation.with_user(self.finance).action_create_invoice()
        invoice = valuation.invoice_id
        guarantee = invoice.invoice_line_ids.filtered(lambda l: l.account_id == account)
        self.assertAlmostEqual(guarantee.price_subtotal, -valuation.amount_guarantee)
        self.assertFalse(guarantee.tax_ids)
        self.assertAlmostEqual(invoice.amount_untaxed, valuation.amount_net, delta=0.01)
        # No se publica: la factura electrónica peruana no admite líneas
        # negativas ni sin impuestos (la opción es para otras localizaciones).

    def test_valuation_cancel_returns_deliveries(self):
        first = self._execute_until_week()
        self._confirm(first)
        valuation = self._prepare_valuation(date(2026, 10, 28))
        self.assertEqual(first.valuation_id, valuation)
        with self.assertRaises(UserError):
            valuation.with_user(self.projects_user).action_cancel()
        valuation.with_user(self.manager).action_cancel()
        self.assertEqual(valuation.state, 'cancel')
        self.assertFalse(first.valuation_id)
        self.assertEqual(first.state, 'confirmed')
        # La acción programada la vuelve a preparar después del corte.
        prepared = self.env['construction.valuation']._prepare_valuations(
            today=date(2026, 10, 30), projects=self.project)
        self.assertEqual(prepared.delivery_ids, first)
        self.assertEqual(prepared.sequence_number, 1)

    # ------------------------------------------------------------------
    # P-21 · Calendario e ingresos
    # ------------------------------------------------------------------
    def test_income_calendar(self):
        project = self.project
        self.assertEqual(project.construction_valuation_every, 2)
        self.assertEqual(project.construction_valuation_unit, 'week')
        self.assertEqual(project._construction_valuation_cutoffs(), [
            date(2026, 10, 28), date(2026, 11, 11), date(2026, 11, 25), date(2026, 12, 9),
            date(2026, 12, 23)])
        forecast = project._construction_get_valuation_forecast()
        rows = forecast['rows']
        expected = [
            (date(2026, 10, 30), date(2026, 11, 4), date(2026, 11, 6), date(2026, 12, 7)),
            (date(2026, 11, 13), date(2026, 11, 18), date(2026, 11, 20), date(2026, 12, 21)),
            (date(2026, 11, 27), date(2026, 12, 2), date(2026, 12, 4), date(2027, 1, 4)),
            (date(2026, 12, 11), date(2026, 12, 16), date(2026, 12, 18), date(2027, 1, 18)),
            # La presentación caería el viernes 25/12 (feriado) y pasa al lunes 28/12.
            (date(2026, 12, 28), date(2027, 1, 4), date(2027, 1, 6), date(2027, 2, 5)),
        ]
        self.assertEqual([(r['submit'], r['confirm'], r['invoice'], r['collection'])
                          for r in rows], expected)
        # El monto previsto cierra en el precio y el fondo es el 5 %.
        self.assertAlmostEqual(forecast['total']['amount'], PRICE)
        for row in rows:
            self.assertAlmostEqual(row['guarantee'], round(row['amount'] * 0.05, 2))
            self.assertAlmostEqual(row['net'], row['amount'] - row['guarantee'])
        self.assertIn('28/12/2026', project.construction_valuation_forecast_html)

        # Fechas fijas de corte y adelanto con amortización.
        project.write({
            'construction_valuation_unit': 'dates',
            'construction_valuation_cutoff_ids': [Command.create({'date': date(2026, 11, 30)}),
                                                  Command.create({'date': date(2026, 12, 31)})],
            'construction_advance_pct': 10.0,
            'construction_advance_amortization_pct': 10.0,
        })
        forecast = project._construction_get_valuation_forecast()
        self.assertEqual([r['cutoff'] for r in forecast['rows']],
                         [date(2026, 11, 30), date(2026, 12, 31)])
        self.assertAlmostEqual(forecast['total']['amount'], PRICE)
        self.assertAlmostEqual(forecast['total']['amortization'], round(PRICE * 0.10, 2),
                               delta=0.02)

    def test_company_defaults(self):
        self.company.write({'construction_valuation_every': 4,
                            'construction_guarantee_pct': 3.0})
        project = self.env['project.project'].create({
            'name': 'Obra nueva (test ingresos)', 'is_construction_site': True})
        self.assertEqual(project.construction_valuation_every, 4)
        self.assertEqual(project.construction_guarantee_pct, 3.0)
        settings = Form(self.env['res.config.settings'])
        self.assertEqual(settings.construction_valuation_every, 4)

    def test_partidas_by_family(self):
        """Partida con familia: las líneas de los ambientes de esa familia;
        dos partidas sin familia no se admiten."""
        closet = self.env['product.product'].create({'name': 'Closets (test)', 'type': 'service'})
        self.order.write({'order_line': [Command.create({
            'product_id': closet.id, 'product_uom_qty': 1, 'price_unit': 1000.0})]})
        with self.assertRaises(UserError):
            self.project._construction_lines_by_partida()
        self.partida.construction_family = 'kitchen'
        by_partida = self.project._construction_lines_by_partida()
        self.assertEqual(by_partida[self.partida], self.plan.line_ids)
        self.assertFalse(by_partida[self.order.order_line - self.partida])

    # ------------------------------------------------------------------
    # Multicompañía
    # ------------------------------------------------------------------
    def test_multicompany(self):
        first = self._execute_until_week()
        self._confirm(first)
        valuation = self._prepare_valuation(date(2026, 10, 28))
        other = self.env['res.company'].create({'name': 'Otra constructora (test ingresos)'})
        outsider = new_test_user(
            self.env, 'ing_otra', name='Otra compañía (test)', company_id=other.id,
            company_ids=[Command.set(other.ids)],
            groups='al_construction_planner.group_planner_manager')
        Delivery = self.env['construction.weekly.delivery'].with_user(outsider)
        Valuation = self.env['construction.valuation'].with_user(outsider)
        self.assertFalse(Delivery.search([('id', '=', first.id)]))
        self.assertFalse(Valuation.search([('id', '=', valuation.id)]))
        with self.assertRaises(AccessError):
            valuation.with_user(outsider).read(['name'])
        # La OV del contrato debe ser de la compañía de la obra.
        foreign = self.env['sale.order'].with_company(other).create({
            'partner_id': self.customer.id, 'company_id': other.id})
        with self.assertRaises(UserError):
            self.project.construction_sale_order_id = foreign
