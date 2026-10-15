# -*- coding: utf-8 -*-
"""Control por cualquier nivel y generalización del paquete 1.6 (v1.7, M17-13
a M17-17), sobre la obra de constructora Disciplina › Subpartida › Partida ›
Actividad de test_levels_v17."""
import re

from odoo.tests import HttpCase, new_test_user, tagged

from .test_levels_v17 import TestFreeLevels
from .test_portal_v15 import PNG


class ApprovedSite:

    @classmethod
    def _approve_site(cls):
        cls.plan_site.action_request_approval()
        assert cls.plan_site.state == 'approved', cls.plan_site.state


@tagged('post_install', '-at_install')
class TestGeneralized(ApprovedSite, TestFreeLevels):

    def test_control_by_template_levels(self):
        """M17-13: desvío por disciplina, subpartida y partida contra la versión
        aprobada."""
        self._approve_site()
        drywall = self.plan_site.line_ids.filtered(lambda l: l.task_id == self.drywall)
        self.assertEqual(set(drywall.mapped('level_1_id')), {self.arq})
        self.assertEqual(set(drywall.mapped('level_2_id')), {self.walls})
        self.assertEqual(set(drywall.mapped('level_3_id')), {self.drywall})
        self.assertFalse(drywall.mapped('level_4_id'))
        for line in drywall:
            self.assertEqual(line.amount_baseline, line.amount_planned)
        # Versión 2: el muro sube de 66 a 80 placas.
        wizard = self.env['construction.plan.replan.wizard'].create({
            'plan_id': self.plan_site.id, 'reason': 'Más muro en el eje B', 'mode': 'all'})
        plan_v2 = self.env['construction.resource.plan'].browse(
            wizard.action_create_version()['res_id'])
        board = plan_v2.line_ids.filtered(lambda l: l.product_id == self.board_mat
                                          and l.task_id == self.drywall)
        board.qty_planned = 80.0
        Line = self.env['construction.resource.plan.line']
        diffs = dict(Line._read_group([('plan_id', '=', plan_v2.id)], ['level_1_id'],
                                      ['amount_version_diff:sum']))
        self.assertAlmostEqual(diffs[self.arq], 14 * 33.0)
        self.assertAlmostEqual(diffs[self.iee], 0.0)
        by_partida = dict(Line._read_group([('plan_id', '=', plan_v2.id)], ['level_3_id'],
                                           ['amount_baseline:sum']))
        # La partida suma también su actividad (muro eje A, por la ruta).
        under = self.plan_site.line_ids.filtered(
            lambda l: l.task_path.startswith(self.drywall.construction_path))
        self.assertAlmostEqual(by_partida[self.drywall], sum(under.mapped('amount_budgeted')))
        action = plan_v2.action_open_control_analysis()
        self.assertEqual(action['context']['pivot_row_groupby'],
                         ['level_1_id', 'level_2_id', 'level_3_id'])
        self.assertIn('amount_deviation', action['context']['pivot_measures'])
        # El desvío de ejecución: comprometido más real menos la línea base.
        line = self.plan_site.line_ids[0]
        line.write({'amount_committed': line.amount_baseline + 5.0})
        self.assertAlmostEqual(line.amount_deviation, 5.0 + line.amount_actual)

    def test_purchase_destination(self):
        """M17-14: la plantilla de constructora compra directo a la obra."""
        self.assertEqual(self.site.construction_purchase_destination, 'general')
        self.template.purchase_destination = 'project'
        self.assertEqual(self.site.construction_purchase_destination, 'project')
        self._approve_site()
        account = self.env['account.analytic.account'].create({
            'name': 'Obra Torre Lima (test)',
            'plan_id': self.env['account.analytic.plan'].search([], limit=1).id})
        self.plan_site.line_ids.with_context(construction_plan_force=True).write(
            {'analytic_distribution': {str(account.id): 100.0}})
        wizard = self.env['construction.plan.purchase.wizard'].with_context(
            default_plan_id=self.plan_site.id, construction_selection_project=True).create({})
        self.assertEqual(wizard.mode, 'project')
        board = wizard.line_ids.filtered(lambda l: l.product_id == self.board_mat)
        # Toda la necesidad (66 del muro y 2 de las luminarias), sin descontar el central.
        self.assertAlmostEqual(board.qty_need, 68.0)
        self.assertAlmostEqual(board.qty_to_buy, 68.0)
        action = wizard.action_create()
        request = self.env['purchase.request'].browse(action['res_id'])
        pr_line = request.line_ids.filtered(lambda l: l.product_id == self.board_mat)
        self.assertEqual(pr_line.construction_plan_mode, 'project')
        self.assertEqual(pr_line.analytic_distribution, {str(account.id): 100.0})
        maker = self.env['purchase.request.line.make.purchase.order']
        item = self.env['purchase.request.line.make.purchase.order.item'].new(
            {'line_id': pr_line.id})
        self.assertFalse(maker._al_is_general_stock(item))
        self.assertEqual(maker._al_final_location(item), self.site.construction_location_id)

    def test_measurement_in_level_unit(self):
        """M17-15: el metrado de la partida en m² con su diferencia en soles."""
        self.drywall.construction_qty = 120.0
        self._approve_site()
        measurement = self.env['construction.measurement'].create({'task_id': self.drywall.id})
        line = measurement.line_ids
        self.assertEqual(line.driver, 'qty')
        self.assertEqual(line.uom_id, self.m2)
        self.assertEqual(line.qty_planned, 120.0)
        drywall_lines = self.plan_site.line_ids.filtered(
            lambda l: l.task_path.startswith(self.drywall.construction_path))
        unit = sum(drywall_lines.mapped('amount_planned')) / 120.0
        self.assertAlmostEqual(line.unit_amount, unit, places=4)
        line.qty_measured = 130.0
        self.assertTrue(measurement.has_difference)
        self.assertAlmostEqual(measurement.amount_difference, round(10 * unit, 2))

    def test_path_names(self):
        self.assertEqual(self.drywall_a._construction_path_name(),
                         'ARQ Arquitectura › ARQ-03 Tabiquería › ARQ-03.02.01 Muro drywall RF '
                         '› Muro eje A')


@tagged('post_install', '-at_install')
class TestGeneralizedPortal(ApprovedSite, HttpCase, TestFreeLevels):
    """M17-16 y M17-17: la contrata de drywall reporta y pide material en los
    niveles de su obra de constructora."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contract_line = cls.plan_site.line_ids.filtered(lambda l: l.resource_type == 'contract')
        cls.contract_line.partner_id = cls.contractor
        # Una línea de la contrata en una etapa de taller: no va al portal.
        cls.shop = cls.env['construction.stage'].create({
            'name': 'Prefabricado (test)', 'code': 'test17_shop', 'kind': 'production'})
        cls.shop_line = cls.env['construction.resource.plan.line'].create({
            'plan_id': cls.plan_site.id, 'task_id': cls.led.id, 'stage': 'test17_shop',
            'resource_type': 'contract', 'activity_id': cls.act_doors.id, 'qty_planned': 3,
            'price_unit_planned': 5.0, 'product_uom_id': cls.unit.id,
            'partner_id': cls.contractor.id})
        cls._approve_site()
        new_test_user(cls.env, 'capataz_drywall', groups='base.group_portal',
                      name='Capataz drywall (test)',
                      partner_id=cls.env['res.partner'].create({
                          'name': 'Capataz drywall (test)', 'parent_id': cls.contractor.id}).id)

    def _csrf(self, url):
        return re.search(r'name="csrf_token" value="([^"]+)"',
                         self.url_open(url).text).group(1)

    def test_progress_and_extra_on_any_level(self):
        self.authenticate('capataz_drywall', 'capataz_drywall')
        url = '/my/obra/avance?project_id=%s&activity_id=%s' % (self.site.id, self.act_doors.id)
        page = self.url_open(url)
        self.assertIn('qty_%s' % self.contract_line.id, page.text)
        self.assertNotIn('qty_%s' % self.shop_line.id, page.text, 'etapa de taller')
        self.assertIn('ARQ-03 Tabiquería › ARQ-03.02.01 Muro drywall RF › Muro eje A', page.text)
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url), 'qty_%s' % self.contract_line.id: '20',
            'date': '2026-11-03'}, files={'photos': ('muro.png', PNG, 'image/png')})
        self.assertEqual(response.status_code, 200)
        progress = self.env['construction.task.progress'].search(
            [('plan_line_id', '=', self.contract_line.id)])
        self.assertEqual((progress.qty, progress.task_id), (20.0, self.drywall_a))

        url = '/my/obra/material?project_id=%s' % self.site.id
        page = self.url_open(url)
        for name in ('ARQ Arquitectura', 'ARQ-03 Tabiquería'):
            self.assertIn('<option value="%s">' % self.env['project.task'].search(
                [('name', '=', name), ('project_id', '=', self.site.id)]).id, page.text)
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url), 'task_id': str(self.walls.id),
            'product_id': str(self.board_mat.id), 'qty': '4', 'reason': 'waste'})
        self.assertEqual(response.status_code, 200)
        extra = self.env['construction.material.request'].search([
            ('project_id', '=', self.site.id), ('is_extra', '=', True)])
        self.assertEqual(extra.task_id, self.walls)


# Solo las pruebas propias: las de TestFreeLevels ya corren en su clase.
for _cls in (TestGeneralized, TestGeneralizedPortal):
    for _name in dir(TestFreeLevels):
        if _name.startswith('test_') and callable(getattr(TestFreeLevels, _name)) \
                and _name not in vars(_cls):
            setattr(_cls, _name, None)
