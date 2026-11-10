# -*- coding: utf-8 -*-
"""Paquete 7 de CREVAL, entrega 1: costo ejecutado e ingreso desde la
analítica de la obra (CR-62) y avance físico por partida (CR-61). Datos
ficticios."""
from datetime import date
from unittest.mock import patch

from odoo import Command

from odoo.tests import HttpCase, tagged

from .test_income import PRICE, IncomeCommon


@tagged('post_install', '-at_install')
class TestCrevalPackage7Sources(IncomeCommon):

    def _account(self, code, kind):
        return self.env['account.account'].create({
            'name': 'Cuenta %s (test)' % code, 'code': code, 'account_type': kind})

    def _analytic(self, account, amount):
        if not self.project.account_id:
            self.project._create_analytic_account()
        return self.env['account.analytic.line'].create({
            'name': 'Apunte (test)', 'account_id': self.project.account_id.id,
            'general_account_id': account.id, 'amount': amount,
            'date': date(2026, 10, 20), 'company_id': self.project.company_id.id})

    def test_cost_and_income_from_accounting(self):
        self.project.company_id.construction_excluded_account_prefixes = '9,79'
        expense = self._account('6399001', 'expense')
        income = self._account('7099001', 'income')
        destination = self._account('9399001', 'expense')
        advance = self._account('1229001', 'asset_current')
        self._analytic(expense, -1000.0)
        self._analytic(income, 1500.0)
        self._analytic(destination, -700.0)
        self._analytic(advance, -300.0)
        self.project.invalidate_recordset(['construction_cost_executed',
                                           'construction_income_accounting'])
        self.assertAlmostEqual(self.project.construction_cost_executed, 1000.0)
        self.assertAlmostEqual(self.project.construction_income_accounting, 1500.0)
        action = self.project.action_construction_cost_entries()
        self.assertEqual(action['res_model'], 'account.analytic.line')

    def test_physical_progress_uses_the_valuation_rule(self):
        self.project.construction_valuation_basis = 'progress'
        self.project.construction_progress_source = 'valued'
        self._progress(4502.23, date(2026, 10, 22))
        self._consume(303, date(2026, 10, 20))
        values = self.project._construction_physical_values(date(2026, 10, 28))
        ratio = 47984.71 / 170764.10
        self.assertAlmostEqual(values['progress'], ratio, places=6)
        progress, price, _target = values['lines'][self.partida]
        self.assertAlmostEqual(price, PRICE, places=2)
        self.assertAlmostEqual(progress, ratio, places=6)
        self.assertGreater(values['earned_value'], 0.0)

    def test_new_sites_default_to_valued_progress(self):
        site = self.env['project.project'].create({'name': 'Obra nueva (test 7)',
                                                   'is_construction_site': True})
        self.assertEqual(site.construction_progress_source, 'valued')

    # ------------------------------------------------------------------
    # Entrega 2: CR-64 y CR-63
    # ------------------------------------------------------------------
    def _change(self, kind='additional', sale_price=80.0):
        product = self.env['product.product'].create({'name': 'Material del cambio (test)',
                                                      'type': 'consu'})
        return self.env['construction.change.order'].create({
            'project_id': self.project.id, 'kind': kind, 'reason': 'Pedido del cliente (test)',
            'line_ids': [(0, 0, {
                'task_id': self.space.id, 'resource_type': 'material', 'product_id': product.id,
                'qty': 2, 'price_unit': 50.0, 'sale_price_unit': sale_price})],
        })

    def test_billable_change_goes_to_the_sale(self):
        self.project.company_id.construction_change_product_id = self.env[
            'product.product'].create({'name': 'Adicional de obra (test)', 'type': 'service'})
        change = self._change()
        self.assertEqual(change.billing, 'pending')
        before = self.order.amount_untaxed
        change.with_user(self.manager).action_approve()
        self.assertEqual(change.billing, 'billable')
        self.assertTrue(change.sale_line_id)
        self.assertEqual(change.sale_line_id.order_id, self.order)
        self.assertAlmostEqual(self.order.amount_untaxed - before, change.amount_sale, places=2)
        self.assertAlmostEqual(change.amount_margin, change.amount_sale - change.amount_cost)

    def test_rework_is_not_billable(self):
        change = self._change(kind='rework')
        before = self.order.amount_untaxed
        change.with_user(self.manager).action_approve()
        self.assertEqual(change.billing, 'not_billable')
        self.assertFalse(change.sale_line_id)
        self.assertAlmostEqual(self.order.amount_untaxed, before)

    def test_month_targets_close_on_the_sale(self):
        self.project.construction_valuation_basis = 'progress'
        action = self.project.action_construction_valuation_targets()
        targets = self.env['construction.valuation.target'].search(action['domain'])
        self.assertTrue(targets)
        total = sum(line._construction_price() for line in self.project._construction_partida_lines()) \
            + sum(line._construction_price() for line in self.project._construction_proportional_lines())
        forecast_months = {row['cutoff'].replace(day=1) for row in
                           self.project._construction_get_valuation_forecast()['rows']}
        self.assertAlmostEqual(
            sum(t.amount_computed for t in targets if t.month in forecast_months), total, places=0)

    def test_target_approval_by_the_project_head(self):
        target = self.env['construction.valuation.target'].create({
            'project_id': self.project.id, 'month': date(2026, 11, 1), 'amount_proposed': 1000.0})
        target.action_propose()
        self.assertEqual(target.state, 'proposed')
        self.assertFalse(target.amount_approved)
        self.assertEqual(self.project._construction_valuation_target(date(2026, 11, 15))[1], False)
        target.with_user(self.manager).validate_tier()
        self.assertEqual(target.state, 'approved')
        self.assertEqual(target.amount_approved, 1000.0)
        # Cambiar la meta aprobada: vuelve a «Propuesta» y vale la anterior.
        target.amount_proposed = 800.0
        target.action_propose()
        self.assertEqual(target.state, 'proposed')
        self.assertEqual(self.project._construction_valuation_target(date(2026, 11, 1)),
                         (1000.0, True))

    # ------------------------------------------------------------------
    # Entrega 3: CR-60, ficha de indicadores
    # ------------------------------------------------------------------
    def _indicators_ready(self):
        self.project.construction_valuation_basis = 'progress'
        self.project.construction_progress_source = 'valued'
        self._progress(4502.23, date(2026, 10, 22))
        self._consume(303, date(2026, 10, 20))
        expense = self._account('6399002', 'expense')
        income = self._account('7099002', 'income')
        self._analytic(expense, -40000.0)
        self._analytic(income, 45000.0)

    def test_indicators_budget_and_executed(self):
        self._indicators_ready()
        today = date(2026, 10, 28)
        data = self.project._construction_indicators(today, today)
        budget, executed = data['budget'], data['executed']
        sale = self.order.amount_untaxed
        self.assertAlmostEqual(budget['close_sale'], sale, places=2)
        self.assertEqual(executed['close_sale'], budget['close_sale'])
        # Ejecutado a hoy: la contabilidad analítica.
        self.assertAlmostEqual(executed['sale'], 45000.0)
        self.assertAlmostEqual(executed['cost'], 40000.0)
        self.assertAlmostEqual(executed['margin_pct'], 5000.0 / 45000.0)
        # Avance físico: el de CR-61 a la misma fecha.
        physical = self.project._construction_physical_values(today)
        self.assertAlmostEqual(executed['physical'], physical['progress'], places=6)
        self.assertAlmostEqual(executed['to_value'],
                               round((executed['physical'] - executed['valued']) * sale, 2),
                               places=1)
        # Índices y costo final estimado (PMBOK).
        self.assertAlmostEqual(data['cpi'], physical['earned_value'] / 40000.0, places=6)
        self.assertAlmostEqual(data['spi'], physical['earned_value'] / data['pv'], places=4)
        bac = sum(l.amount_budgeted or l.amount_planned for l in self.plan.line_ids)
        self.assertAlmostEqual(data['eac'], round(40000.0 + (bac - physical['earned_value'])
                                                  / data['cpi'], 2), places=1)
        self.assertAlmostEqual(budget['close_margin_pct'], (sale - bac) / sale, places=6)
        self.assertIn(data['light'], ('green', 'amber', 'red'))

    def test_estimated_end_from_the_schedule_index(self):
        # Inicio 13/07, fin del contrato 28/11 (138 días) e índice de plazo 0.84.
        end = self.env['project.project']._construction_estimated_end(
            date(2026, 7, 13), date(2026, 11, 28), 0.84)
        self.assertEqual(end, date(2026, 12, 25))
        self.assertFalse(self.env['project.project']._construction_estimated_end(
            date(2026, 7, 13), date(2026, 11, 28), False))

    def test_indicator_sheet_matches_the_indicators(self):
        self._indicators_ready()
        Sheet = self.env['construction.project.indicators'].with_user(self.manager)
        sheet = Sheet.get_indicator_sheet(self.project.id)
        data = self.project._construction_indicators()
        self.assertEqual(sheet['executed']['cost'], data['executed']['cost'])
        self.assertEqual(sheet['budget']['close_sale'], data['budget']['close_sale'])
        self.assertTrue(sheet['show_amounts'])
        self.assertEqual(sheet['stage'], 'execution')
        self.assertTrue(sheet['specialties'])
        self.assertTrue(sheet['charts']['progress']['dates'])
        self.assertIn('days_late', sheet['schedule'])
        for kind in ('schedule', 'valuation', 'control', 'change'):
            self.assertTrue(Sheet.action_open_document(self.project.id, kind))

    def test_indicator_sheet_without_amounts(self):
        self._indicators_ready()
        viewer = self.projects_user
        self.assertFalse(viewer.has_group('al_construction_planner.group_planner_amounts'))
        sheet = self.env['construction.project.indicators'].with_user(viewer) \
            .get_indicator_sheet(self.project.id)
        self.assertFalse(sheet['show_amounts'])
        self.assertIs(sheet['executed']['cost'], False)
        self.assertIs(sheet['budget']['close_sale'], False)
        self.assertIs(sheet['tracking']['invoiced'], False)
        # Avance, valorizado % e índices sí se ven.
        self.assertIsInstance(sheet['executed']['physical'], float)
        self.assertIsInstance(sheet['executed']['valued'], float)
        self.assertNotEqual(sheet['cpi'], False)

    def test_favorite_star_by_user(self):
        Sheet = self.env['construction.project.indicators'].with_user(self.projects_user)
        self.assertTrue(Sheet.toggle_favorite(self.project.id))
        self.assertIn(self.projects_user, self.project.favorite_user_ids)
        self.assertNotIn(self.manager, self.project.favorite_user_ids)
        self.assertFalse(Sheet.toggle_favorite(self.project.id))


    # ------------------------------------------------------------------
    # Entrega 4: CR-59 cartera de obras y CR-65 pendientes por área
    # ------------------------------------------------------------------
    def _home_work(self, user, month=False):
        data = self.env['construction.planner.home'].with_user(user).get_home_data(month)
        return data, next(w for w in data['works'] if w['project_id'] == self.project.id)

    def test_portfolio_matches_the_sheet(self):
        self._indicators_ready()
        _data, work = self._home_work(self.manager)
        self.assertEqual(work['stage'], 'execution')
        self.assertFalse(work['is_favorite'])
        sheet = self.env['construction.project.indicators'].with_user(self.manager) \
            .get_indicator_sheet(self.project.id)
        for side in ('budget', 'executed'):
            for key, value in sheet[side].items():
                self.assertAlmostEqual(work['indicators'][side][key] or 0.0, value or 0.0,
                                       places=6, msg='%s.%s' % (side, key))
        self.assertEqual(work['indicators']['light'], sheet['light'])
        # Guardado: la segunda lectura no recalcula.
        self.assertFalse(self.project.construction_indicators_stale)
        self.assertEqual(self.project.construction_indicators_cache['budget'],
                         work['indicators']['budget'])

    def test_portfolio_other_month_is_computed(self):
        self._indicators_ready()
        _data, work = self._home_work(self.manager, '2026-10-01')
        self.assertEqual(work['indicators']['month'], '2026-10-01')

    def test_portfolio_without_amounts(self):
        self._indicators_ready()
        data, work = self._home_work(self.projects_user)
        self.assertFalse(data['show_amounts'])
        self.assertIs(work['indicators']['executed']['sale'], False)
        self.assertIs(work['indicators']['budget']['close_sale'], False)
        self.assertIs(work['indicators']['invoiced'], False)
        self.assertIsInstance(work['indicators']['executed']['physical'], float)
        self.assertNotEqual(work['indicators']['cpi'], False)

    def test_portfolio_favorite_and_postsale(self):
        Home = self.env['construction.planner.home'].with_user(self.projects_user)
        self.assertTrue(Home.toggle_favorite(self.project.id))
        _data, work = self._home_work(self.projects_user)
        self.assertTrue(work['is_favorite'])
        self.plan.state = 'closed'
        _data, work = self._home_work(self.manager)
        self.assertEqual(work['stage'], 'postsale')

    def test_indicators_are_marked_stale(self):
        self.project._construction_refresh_indicators()
        self.assertFalse(self.project.construction_indicators_stale)
        # Una meta aprobada.
        target = self.env['construction.valuation.target'].create({
            'project_id': self.project.id, 'month': date(2026, 11, 1), 'amount_proposed': 10.0})
        target.action_propose()
        target.with_user(self.manager).validate_tier()
        self.assertTrue(self.project.construction_indicators_stale)
        # La acción programada recalcula.
        self.env['project.project'].with_context(
            construction_no_commit=True)._cron_construction_indicators()
        self.assertFalse(self.project.construction_indicators_stale)
        # Un asiento con la analítica de la obra.
        expense = self._account('6399003', 'expense')
        journal = self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.project.company_id.id)], limit=1)
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': journal.id, 'date': date(2026, 10, 25),
            'line_ids': [
                Command.create({'account_id': expense.id, 'debit': 100.0,
                                'analytic_distribution': {str(self.project.account_id.id): 100}}),
                Command.create({'account_id': self._account('4699003', 'liability_current').id,
                                'credit': 100.0}),
            ]})
        move.action_post()
        self.assertTrue(self.project.construction_indicators_stale)

    def test_pending_by_area(self):
        data = self.env['construction.planner.home'].with_user(self.manager).get_home_data()
        by_key = {item['key']: item for item in data['pending']}
        self.assertEqual(by_key['progress_to_validate']['area'], 'site')
        self.assertEqual(by_key['lines_without_cost']['area'], 'planning')
        self.assertEqual(by_key['deliveries_to_confirm']['area'], 'revenue')
        self.assertTrue(by_key['progress_to_validate']['role'])
        self.assertIn(['other', 'Otros'], data['areas'])
        # Un pendiente sin área cae en «Otros».
        Home = type(self.env['construction.planner.home'])
        with patch.object(Home, '_pending_areas', lambda self: {}):
            data = self.env['construction.planner.home'].with_user(self.manager).get_home_data()
        self.assertEqual({item['area'] for item in data['pending']}, {'other'})


@tagged('post_install', '-at_install')
class TestCrevalPackage7Tour(IncomeCommon, HttpCase):

    def setUp(self):
        super().setUp()
        # La obra es de la compañía del test: el administrador entra en ella.
        self.env.ref('base.user_admin').write({
            'company_ids': [Command.link(self.company.id)], 'company_id': self.company.id})

    def test_portfolio_tour(self):
        self.start_tour('/odoo/action-al_construction_planner.action_construction_planner_home',
                        'al_construction_planner_portfolio', login='admin')

    def test_indicator_sheet_tour(self):
        self.start_tour('/odoo/action-project.open_view_project_all/%s' % self.project.id,
                        'al_construction_planner_indicator_sheet', login='admin')
