# -*- coding: utf-8 -*-
from datetime import date

from freezegun import freeze_time

from odoo import Command
from odoo.tests import new_test_user, tagged

from .test_income import PHOTO, PRICE, IncomeCommon

PLAN_TOTAL = 170764.10


@tagged('post_install', '-at_install')
class TestScheduleReport(IncomeCommon):
    """Fase 11: cronograma valorizado (P-22) e inicio de la aplicación
    (P-01). Criterios de aceptación 18 y 19 de la especificación (adaptados
    al demo: la obra de la fase 10 con semana de jueves a miércoles)."""

    def _rows(self, scenario, concept, guarantee=None):
        domain = [('project_id', '=', self.project.id), ('scenario', '=', scenario),
                  ('concept', '=', concept)]
        if guarantee is not None:
            domain.append(('is_guarantee', '=', guarantee))
        records = self.env['construction.schedule.report'].search(domain)
        weekly = {}
        for record in records:
            weekly[record.week_start] = weekly.get(record.week_start, 0.0) + record.amount
        return weekly

    def _post_invoice(self, valuation, invoice_date):
        valuation.with_user(self.finance).action_create_invoice()
        invoice = valuation.invoice_id
        invoice.invoice_date = invoice_date
        invoice.action_post()
        return invoice

    def _collect(self, invoice, day):
        """Cobro conciliado: asiento de banco contra la cuenta por cobrar de
        la factura (como la conciliación del extracto)."""
        receivable = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable')
        journal = self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.company),
            ('type', '=', 'bank')], limit=1)
        entry = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': journal.id, 'date': day,
            'line_ids': [
                Command.create({'account_id': journal.default_account_id.id,
                                'debit': invoice.amount_total, 'partner_id': self.customer.id,
                                'name': 'Cobro'}),
                Command.create({'account_id': receivable.account_id.id,
                                'credit': invoice.amount_total, 'partner_id': self.customer.id,
                                'name': 'Cobro'}),
            ]})
        entry.action_post()
        (receivable | entry.line_ids.filtered(
            lambda l: l.account_id == receivable.account_id)).reconcile()
        return entry

    # ------------------------------------------------------------------
    # Plan (criterio 18)
    # ------------------------------------------------------------------
    def test_plan_schedule(self):
        """La valorización 2 se confirma en la semana 12/11–18/11, se factura
        en la 19/11–25/11 y se cobra en la 17/12–23/12; el cobrado acumulado
        cierra en el precio al sumar el fondo de garantía."""
        # Etapas del ambiente a lo largo de la obra (P-15): producción,
        # instalación y acabado.
        Stage = self.env['construction.space.stage']
        for stage, start, end in (('production', date(2026, 10, 12), date(2026, 10, 30)),
                                  ('installation', date(2026, 11, 2), date(2026, 11, 27)),
                                  ('finishing', date(2026, 11, 30), date(2026, 12, 18))):
            Stage.create({'space_task_id': self.space.id, 'stage': stage,
                          'date_start': start, 'date_end': end})
        Report = self.env['construction.schedule.report']
        Report._construction_refresh(self.project)
        forecast = self.project._construction_get_valuation_forecast()
        second = forecast['rows'][1]
        valuation = self._rows('plan', 'valuation')
        invoice = self._rows('plan', 'invoice')
        collection = self._rows('plan', 'collection', guarantee=False)
        self.assertGreater(second['amount'], 0)
        self.assertAlmostEqual(valuation[date(2026, 11, 12)], second['amount'])
        self.assertAlmostEqual(invoice[date(2026, 11, 19)], second['amount'])
        self.assertAlmostEqual(collection[date(2026, 12, 17)], second['net'])
        # Todo cierra: costo en el plan, ingreso, valorización y factura en el
        # precio, cobrado con el fondo en el precio.
        self.assertAlmostEqual(sum(self._rows('plan', 'cost').values()), PLAN_TOTAL, places=2)
        self.assertAlmostEqual(sum(self._rows('plan', 'revenue').values()), PRICE, places=2)
        self.assertAlmostEqual(sum(valuation.values()), PRICE, places=2)
        self.assertAlmostEqual(sum(invoice.values()), PRICE, places=2)
        guarantee = self._rows('plan', 'collection', guarantee=True)
        self.assertAlmostEqual(sum(guarantee.values()), forecast['total']['guarantee'])
        self.assertAlmostEqual(sum(collection.values()) + sum(guarantee.values()), PRICE,
                               places=2)

        data = Report.with_user(self.finance).get_schedule(self.project.id)
        totals = data['totals']['plan']
        self.assertAlmostEqual(totals['collection_total'], PRICE, places=2)
        self.assertAlmostEqual(totals['margin'], round(PRICE - PLAN_TOTAL, 2), places=2)
        row = next(r for r in data['rows'] if r['week_start'] == '2026-11-12')
        self.assertAlmostEqual(row['plan']['valuation'], second['amount'])
        # Semanas seguidas, de jueves a miércoles.
        weeks = [r['week_start'] for r in data['rows']]
        self.assertEqual(weeks, sorted(weeks))
        self.assertEqual(data['rows'][0]['label'][:5], data['rows'][0]['week_start'][8:10] + '/' +
                         data['rows'][0]['week_start'][5:7])
        # El último acumulado de la tabla es el total.
        self.assertAlmostEqual(data['rows'][-1]['plan']['cost_cum'], PLAN_TOTAL, places=2)

        # Excel: un libro con las hojas Plan y Real.
        action = Report.with_user(self.finance).action_export_xlsx(self.project.id)
        self.assertEqual(action['type'], 'ir.actions.act_url')
        attachment = self.env['ir.attachment'].browse(int(action['url'].split('/')[3].split('?')[0]))
        self.assertTrue(attachment.name.endswith('.xlsx'))
        self.assertGreater(attachment.file_size, 1000)

    def test_plan_cost_by_working_days(self):
        """La línea se reparte en partes iguales entre los días hábiles de la
        etapa de su ambiente (lunes a viernes) y se agrupa por semana de la
        obra; la última semana absorbe el redondeo."""
        self.env['construction.space.stage'].create({
            'space_task_id': self.space.id, 'stage': 'installation',
            'date_start': date(2026, 10, 20), 'date_end': date(2026, 10, 26)})
        by_day = self.project._construction_planned_by_day({False: self.contract_line})[False]
        # Martes 20 a lunes 26: 5 días hábiles (sin sábado ni domingo).
        self.assertEqual(sorted(by_day), [date(2026, 10, 20), date(2026, 10, 21),
                                          date(2026, 10, 22), date(2026, 10, 23),
                                          date(2026, 10, 26)])
        for amount in by_day.values():
            self.assertAlmostEqual(amount, 52000.0 / 5)
        Report = self.env['construction.schedule.report']
        weekly = Report._construction_weekly(self.project, by_day)
        # Jueves 15/10 a miércoles 21/10: martes y miércoles; el resto, la
        # semana del 22/10.
        self.assertEqual(weekly, {date(2026, 10, 15): 20800.0, date(2026, 10, 22): 31200.0})

        thirds = {date(2026, 10, 15): 100 / 3, date(2026, 10, 22): 100 / 3,
                  date(2026, 10, 29): 100 / 3}
        weekly = Report._construction_weekly(self.project, thirds)
        self.assertEqual(weekly[date(2026, 10, 15)], 33.33)
        self.assertEqual(weekly[date(2026, 10, 22)], 33.33)
        self.assertEqual(weekly[date(2026, 10, 29)], 33.34)
        self.assertAlmostEqual(sum(weekly.values()), 100.0)

    # ------------------------------------------------------------------
    # Real
    # ------------------------------------------------------------------
    def test_real_schedule(self):
        """Real: costo ejecutado por semana, entregas confirmadas,
        valorización confirmada, factura publicada y cobro conciliado en sus
        semanas."""
        first = self._execute_until_week()
        second = self.env['construction.weekly.delivery']._prepare_deliveries(
            today=date(2026, 11, 5), projects=self.project)
        self._confirm(first | second)
        valuation = self._prepare_valuation(date(2026, 11, 11))
        valuation.with_user(self.projects_user).action_send()
        self._confirm_valuation(valuation)
        invoice = self._post_invoice(valuation, date(2026, 11, 20))
        self._collect(invoice, date(2026, 12, 21))

        with freeze_time('2026-12-31'):
            self.env['construction.schedule.report']._construction_refresh(self.project)
        cost = self._rows('real', 'cost')
        # Consumo del 20/10 (semana del 15/10) y avance del 22/10 (semana del
        # 22/10); la semana del 29/10, 5,552.96 de contrata y 19,786.00 de
        # material.
        self.assertAlmostEqual(cost[date(2026, 10, 15)], 303 * 98.93, places=2)
        self.assertAlmostEqual(cost[date(2026, 10, 22)], 4502.23 * 4.0, places=2)
        self.assertAlmostEqual(cost[date(2026, 10, 29)], 25338.96, places=2)
        revenue = self._rows('real', 'revenue')
        self.assertAlmostEqual(revenue[date(2026, 10, 22)], first.revenue_amount)
        self.assertAlmostEqual(revenue[date(2026, 10, 29)], second.revenue_amount)
        self.assertEqual(self._rows('real', 'valuation'),
                         {date(2026, 11, 12): valuation.amount_confirmed})
        self.assertEqual(self._rows('real', 'invoice'),
                         {date(2026, 11, 19): invoice.amount_untaxed})
        collection = self._rows('real', 'collection')
        self.assertEqual(list(collection), [date(2026, 12, 17)])
        self.assertAlmostEqual(collection[date(2026, 12, 17)], invoice.amount_untaxed, places=2)
        # Un usuario sin ingresos lee la tabla pero no la escribe.
        with self.assertRaises(Exception):
            self.env['construction.schedule.report'].with_user(self.projects_user).search(
                [], limit=1).write({'amount': 1})

    def test_multicompany(self):
        company_b = self.env['res.company'].create({'name': 'Compañía B cronograma (test)'})
        project_b = self.env['project.project'].with_company(company_b).create({
            'name': 'Obra B cronograma (test)', 'company_id': company_b.id,
            'is_construction_site': True, 'date_start': date(2026, 10, 12),
            'date': date(2026, 12, 18)})
        self.env['construction.resource.plan'].with_company(company_b).create({
            'project_id': project_b.id})
        Report = self.env['construction.schedule.report']
        Report.with_company(company_b)._construction_refresh(project_b)
        Report._construction_refresh(self.project)
        rows_a = Report.with_user(self.finance).search([])
        self.assertTrue(rows_a)
        self.assertFalse(rows_a.filtered(lambda r: r.company_id == company_b))
        # La pantalla no recalcula una obra de otra compañía.
        with self.assertRaises(Exception):
            Report.with_user(self.finance).get_schedule(project_b.id)

    # ------------------------------------------------------------------
    # P-01 · Inicio (criterio 19)
    # ------------------------------------------------------------------
    def test_home_supervisor_sees_own_works(self):
        """El supervisor ve solo los avances por validar de sus obras y la
        fila abre esa lista filtrada; la Jefatura ve todos."""
        Progress = self.env['construction.task.progress']
        mine = Progress.create({
            'task_id': self.space.id, 'activity_id': self.activity.id,
            'date': date(2026, 10, 22), 'qty': 10,
            'attachment_ids': [Command.create({'name': 'foto.jpg', 'datas': PHOTO})]})
        # Otra obra con su plan y un avance reportado.
        other = self.env['project.project'].create({
            'name': 'Otra obra (test inicio)', 'is_construction_site': True,
            'date_start': date(2026, 10, 12), 'date': date(2026, 12, 18)})
        Task = self.env['project.task']
        floor = Task.create({'name': 'Piso 01', 'project_id': other.id,
                             'construction_level': 'floor'})
        apartment = Task.create({'name': 'Dpto 101', 'project_id': other.id,
                                 'construction_level': 'apartment', 'parent_id': floor.id})
        space = Task.create({'name': 'Cocina otra', 'project_id': other.id,
                             'construction_level': 'space', 'parent_id': apartment.id})
        plan = self.env['construction.resource.plan'].create({'project_id': other.id})
        self.env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'task_id': space.id, 'product_uom_id': self.unit.id,
            'resource_type': 'contract', 'stage': 'installation', 'activity_id': self.activity.id,
            'qty_planned': 100, 'price_unit_planned': 4.0})
        plan.action_request_approval()
        theirs = Progress.create({
            'task_id': space.id, 'activity_id': self.activity.id, 'date': date(2026, 10, 22),
            'qty': 5, 'attachment_ids': [Command.create({'name': 'foto.jpg', 'datas': PHOTO})]})

        supervisor = new_test_user(
            self.env, 'inicio_supervisor', name='Supervisor de obra (test)',
            groups='al_construction_planner.group_planner_planner')
        self.project.construction_supervisor_ids = supervisor
        Home = self.env['construction.planner.home']
        data = Home.with_user(supervisor).get_home_data()
        item = next(p for p in data['pending'] if p['key'] == 'progress_to_validate')
        self.assertEqual(item['count'], 1)
        records = Progress.with_user(supervisor).search(item['action']['domain'])
        self.assertEqual(records, mine)
        self.assertEqual(item['action']['res_model'], 'construction.task.progress')
        self.assertFalse([k for k in item['action']['context'] if k.startswith('search_default')])
        # Solo los pendientes de sus grupos: no confirma entregas ni factura.
        keys = {p['key'] for p in data['pending']}
        self.assertNotIn('deliveries_to_confirm', keys)
        self.assertNotIn('valuations_to_invoice', keys)
        self.assertIn('lines_without_cost', keys)

        # La Jefatura ve los avances de todas las obras.
        data = Home.with_user(self.manager).get_home_data()
        item = next(p for p in data['pending'] if p['key'] == 'progress_to_validate')
        self.assertIn(theirs, Progress.search(item['action']['domain']))
        self.assertIn(mine, Progress.search(item['action']['domain']))
        self.assertIn('deliveries_to_confirm', {p['key'] for p in data['pending']})

        # Finanzas atiende las valorizaciones por facturar.
        keys = {p['key'] for p in Home.with_user(self.finance).get_home_data()['pending']}
        self.assertIn('valuations_to_invoice', keys)

    def test_home_works_and_milestone(self):
        Home = self.env['construction.planner.home']
        with freeze_time('2026-11-05'):
            data = Home.with_user(self.manager).get_home_data()
        work = next(w for w in data['works'] if w['project_id'] == self.project.id)
        self.assertAlmostEqual(work['amount_total'], PLAN_TOTAL)
        self.assertEqual(work['state'], 'approved')
        # El hito más cercano desde el jueves 05/11: la factura de la
        # valorización 1 (viernes 06/11).
        self.assertEqual(work['milestone_date'], '2026-11-06')
        self.assertIn('Valorización 1', work['milestone'])
        # Un plan en borrador tiene como hito aprobarlo.
        draft = self.env['project.project'].create({
            'name': 'Obra en borrador (test inicio)', 'is_construction_site': True})
        self.env['construction.resource.plan'].create({'project_id': draft.id})
        data = Home.with_user(self.manager).get_home_data()
        work = next(w for w in data['works'] if w['project_id'] == draft.id)
        self.assertEqual(work['milestone'], 'Aprobar el plan')
        self.assertFalse(work['amount_total'])

    def test_home_stage_without_contract(self):
        """Etapa con contrata en el plan, sin contrata asignada, que empieza
        en las próximas 2 semanas."""
        stage = self.env['construction.space.stage'].create({
            'space_task_id': self.space.id, 'stage': 'installation',
            'date_start': date(2026, 11, 10), 'date_end': date(2026, 11, 20)})
        Home = self.env['construction.planner.home']
        with freeze_time('2026-11-05'):
            data = Home.with_user(self.planner).get_home_data()
        item = next(p for p in data['pending'] if p['key'] == 'stages_without_contract')
        self.assertEqual(item['count'], 1)
        self.assertEqual(self.env['construction.space.stage'].search(item['action']['domain']),
                         stage)
