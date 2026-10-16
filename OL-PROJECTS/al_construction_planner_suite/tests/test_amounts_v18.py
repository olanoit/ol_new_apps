# -*- coding: utf-8 -*-
"""Visibilidad de montos (v1.8, M18-10).

Criterio: un supervisor sin el grupo «ve montos» abre el cronograma y la
matriz insumo-producto de una obra y no ve ningún importe; la jefatura sí.
Además: vistas sin los campos en soles, lecturas y agrupaciones del cliente
web, exportación con las columnas vacías, árbol y panel sin montos, y el
supervisor sigue registrando avance (los cálculos internos no dependen del
grupo)."""
from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .test_schedule import TestSchedule


@tagged('post_install', '-at_install')
class TestAmountsV18(TestSchedule):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supervisor = new_test_user(
            cls.env, 'montos_supervisor', name='Supervisor sin montos (test)',
            groups='al_construction_planner.group_planner_planner,base.group_allow_export')
        cls.head = new_test_user(
            cls.env, 'montos_jefatura', name='Jefatura (test)',
            groups='al_construction_planner.group_planner_project_head,base.group_allow_export')

    def _payload(self, user):
        return self.env['al.gantt.data'].with_user(user).get_data(
            [self.project.id], {'construction_schedule': True})

    def test_groups(self):
        amounts = 'al_construction_planner.group_planner_amounts'
        self.assertFalse(self.supervisor.has_group(amounts))
        self.assertTrue(self.head.has_group(amounts))
        self.assertTrue(self.env.ref('base.user_admin').has_group(amounts))

    def test_schedule_without_amounts(self):
        payload = self._payload(self.supervisor)
        self.assertFalse(payload['construction']['show_amounts'])
        self.assertTrue(payload['construction_stages'])
        self.assertTrue(all(row['amount'] is False for row in payload['construction_stages']))
        self.assertTrue(all(row['amount'] is False
                            for row in payload['construction_stage_groups']))
        self.assertTrue(all(task['construction'].get('amount') in (False, None)
                            for task in payload['tasks'] if task.get('construction')))
        # Fechas y avance siguen.
        self.assertTrue(all(row['start'] and 'progress' in row
                            for row in payload['construction_stages']))
        with self.assertRaises(AccessError):
            self.plan.with_user(self.supervisor).get_schedule_load()
        # La jefatura ve los montos.
        payload = self._payload(self.head)
        self.assertTrue(payload['construction']['show_amounts'])
        self.assertTrue(any(row['amount'] for row in payload['construction_stages']))
        self.plan.with_user(self.head).get_schedule_load()

    def test_io_matrix_without_amounts(self):
        plan = self.plan.with_user(self.supervisor)
        self.assertFalse(plan.get_io_matrix_options()['show_amounts'])
        matrix = plan.get_io_matrix([str(self.floor.id)], {},
                                    {'level': 'space_task_id', 'measure': 'amount'})
        self.assertEqual(matrix['measure'], 'qty')
        lines = self.plan.line_ids.filtered(lambda l: l.floor_task_id == self.floor)
        self.assertNotAlmostEqual(matrix['total'], round(sum(lines.mapped('amount_planned')), 2))
        head = self.plan.with_user(self.head)
        self.assertTrue(head.get_io_matrix_options()['show_amounts'])
        matrix = head.get_io_matrix([str(self.floor.id)], {},
                                    {'level': 'space_task_id', 'measure': 'amount'})
        self.assertEqual(matrix['measure'], 'amount')
        self.assertAlmostEqual(matrix['total'], round(sum(lines.mapped('amount_planned')), 2),
                               places=2)

    def test_tree_and_panel_without_amounts(self):
        plan = self.plan.with_user(self.supervisor)
        self.assertFalse(plan.get_tree_terms()['show_amounts'])
        root = plan.get_tree_nodes('root')[0]
        self.assertIs(root['total'], False)
        self.assertIs(root['material'], False)
        self.assertTrue(root['qty_total'])
        summary = plan.get_selection_summary([str(self.floor.id)])
        self.assertIs(summary['total'], False)
        self.assertTrue(all(group['amount'] is False for group in summary['groups']))
        self.assertTrue(any(group['qty'] for group in summary['groups']))
        self.assertTrue(self.plan.with_user(self.head).get_tree_nodes('root')[0]['total'])

    def test_views_reads_groups_and_exports(self):
        Plan = self.env['construction.resource.plan']
        for user, visible in ((self.supervisor, False), (self.head, True)):
            arch = etree.fromstring(Plan.with_user(user).get_views(
                [(False, 'form'), (False, 'list')])['views']['form']['arch'])
            names = set(arch.xpath('//field/@name'))
            self.assertEqual('amount_total' in names, visible)
            self.assertEqual('amount_planned' in names, visible)  # sublista de líneas
            self.assertIn('state', names)
        plan = self.plan.with_user(self.supervisor)
        values = plan.web_read({'name': {}, 'amount_total': {}})[0]
        self.assertNotIn('amount_total', values)
        Line = self.env['construction.resource.plan.line'].with_user(self.supervisor)
        with self.assertRaises(AccessError):
            Line.formatted_read_group([('plan_id', '=', self.plan.id)], ['stage'],
                                      ['amount_planned:sum'])
        Line.formatted_read_group([('plan_id', '=', self.plan.id)], ['stage'],
                                  ['qty_planned:sum'])
        lines = Line.search([('plan_id', '=', self.plan.id)], limit=3)
        data = lines.export_data(['product_id', 'qty_planned', 'amount_planned'])['datas']
        self.assertTrue(all(row[2] is False for row in data))
        self.assertTrue(any(row[1] for row in data))
        data = lines.with_user(self.head).export_data(['amount_planned'])['datas']
        self.assertTrue(any(row[0] for row in data))
