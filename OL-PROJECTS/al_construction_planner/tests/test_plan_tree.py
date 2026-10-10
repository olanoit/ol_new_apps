# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from .common import load_demo


class TestPlanTree(TransactionCase):
    """Árbol de recursos (P-02) sobre el piso 05 de demostración: 66 módulos,
    41.33 ML, S/ 8,944.44; Dpto 501 con 7 módulos y S/ 993.66."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Copia propia del piso 05 (otra obra): los datos demo de la base
        # pueden tener ya contratas y avances (planner_demo_contracts.py).
        demo = load_demo(cls.env, 'TEST TREE')
        cls.plan = demo['plan']
        cls.project = demo['project']
        cls.floor = demo['floor']
        cls.gonza = demo['gonza']
        Task = cls.env['project.task']
        cls.apt501 = Task.search([('project_id', '=', cls.project.id), ('name', '=', 'Dpto 501')])
        cls.space501 = Task.search([('parent_id', '=', cls.apt501.id)])

    def _node(self, parent_key, name, filters=None):
        nodes = self.plan.get_tree_nodes(parent_key, filters)
        return next(n for n in nodes if n['name'] == name)

    def test_root_and_floor(self):
        root = self.plan.get_tree_nodes('root')[0]
        self.assertEqual(root['key'], 'p')
        self.assertTrue(root['has_children'])
        floor = self._node('p', 'Piso 05')
        for node in (root, floor):
            self.assertEqual(node['modules'], 66)
            self.assertAlmostEqual(node['ml'], 41.33)
            self.assertAlmostEqual(node['material'], 6642.91)
            self.assertAlmostEqual(node['contract'], 2301.53)
            self.assertAlmostEqual(node['total'], 8944.44)
        self.assertEqual(floor['level'], 'floor')
        self.assertEqual(floor['typology'], '8 tipologías')

    def test_apartment_and_modules(self):
        apartments = self.plan.get_tree_nodes(str(self.floor.id))
        self.assertEqual(len(apartments), 8)
        self.assertEqual(sum(a['modules'] for a in apartments), 66)
        self.assertAlmostEqual(sum(a['total'] for a in apartments), 8944.44)
        apt = self._node(str(self.floor.id), 'Dpto 501')
        self.assertEqual(apt['modules'], 7)
        self.assertAlmostEqual(apt['material'], 735.29)
        self.assertAlmostEqual(apt['contract'], 258.37)
        self.assertAlmostEqual(apt['total'], 993.66)
        self.assertAlmostEqual(apt['ml'], 4.22)
        spaces = self.plan.get_tree_nodes(str(self.apt501.id))
        self.assertEqual([s['level'] for s in spaces], ['space'])
        self.assertAlmostEqual(spaces[0]['total'], 993.66)
        modules = self.plan.get_tree_nodes(str(self.space501.id))
        self.assertEqual(len(modules), 7)
        self.assertTrue(all(m['level'] == 'module' and not m['has_children'] for m in modules))
        self.assertEqual(modules[0]['unit_state'], 'planned')
        # Un nodo de otra obra no devuelve nada.
        other = self.env['project.task'].create({
            'name': 'Ajena', 'project_id': self.env['project.project'].create({'name': 'Otra'}).id})
        self.assertEqual(self.plan.get_tree_nodes(str(other.id)), [])

    def test_selection_child_of(self):
        """La selección se expande con child_of: marcar el piso equivale a
        marcar sus 8 departamentos o la obra entera."""
        by_floor = self.plan.get_selection_summary([str(self.floor.id)])
        self.assertEqual(by_floor['modules'], 66)
        self.assertEqual(by_floor['spaces'], 8)
        self.assertAlmostEqual(by_floor['ml'], 41.33)
        self.assertAlmostEqual(by_floor['total'], 8944.44)
        apartments = [n['key'] for n in self.plan.get_tree_nodes(str(self.floor.id))]
        by_apartments = self.plan.get_selection_summary(apartments)
        by_project = self.plan.get_selection_summary(['p'])
        for summary in (by_apartments, by_project):
            self.assertEqual(summary['modules'], 66)
            self.assertAlmostEqual(summary['total'], 8944.44)
        self.assertEqual(
            [r['amount'] for r in by_floor['resources']],
            [r['amount'] for r in by_project['resources']])
        self.assertAlmostEqual(sum(r['amount'] for r in by_floor['resources']), 8944.44)

        apt = self.plan.get_selection_summary([str(self.apt501.id)])
        self.assertEqual(apt['modules'], 7)
        self.assertAlmostEqual(apt['total'], 993.66)
        module = self.plan.get_tree_nodes(str(self.space501.id))[0]
        one = self.plan.get_selection_summary([module['key']])
        self.assertEqual(one['modules'], 1)
        self.assertAlmostEqual(one['total'], module['total'])
        self.assertTrue(self.plan.get_selection_summary([])['empty'])

    def test_filters(self):
        floor = self._node('p', 'Piso 05', {'resource_types': ['material']})
        self.assertAlmostEqual(floor['total'], 6642.91)
        self.assertEqual(floor['contract'], 0.0)
        install = self._node('p', 'Piso 05', {
            'stages': ['installation'], 'resource_types': ['contract']})
        self.assertAlmostEqual(install['total'], 941.17)
        # Todos los módulos nacen planificados.
        none = self._node('p', 'Piso 05', {'unit_states': ['installed']})
        self.assertEqual(none['modules'], 0)
        self.assertEqual(none['total'], 0.0)
        planned = self._node('p', 'Piso 05', {'unit_states': ['planned']})
        self.assertEqual(planned['modules'], 66)
        self.assertEqual(len(self.plan.get_tree_nodes(
            str(self.space501.id), {'unit_states': ['installed']})), 0)

    def test_partner_filter(self):
        lines = self.plan.line_ids.filtered(
            lambda l: l.apartment_task_id == self.apt501 and l.resource_type == 'contract'
            and l.stage == 'assembly')
        self.assertTrue(lines)
        # La asignación de contrata (fase 5) escribe sobre el plan aprobado
        # (el demo puede estarlo, planner_demo_baseline.py): proceso interno.
        lines.with_context(construction_plan_force=True).write({'partner_id': self.gonza.id})
        assigned = round(sum(lines.mapped('amount_planned')), 2)
        self.assertIn([self.gonza.id, self.gonza.display_name], self.plan.get_tree_partners())
        floor = self._node('p', 'Piso 05', {'partner_ids': [self.gonza.id]})
        self.assertAlmostEqual(floor['total'], assigned)
        unassigned = self._node('p', 'Piso 05', {
            'partner_ids': [0], 'resource_types': ['contract', 'labor']})
        self.assertAlmostEqual(unassigned['total'], round(2301.53 - assigned, 2))
        summary = self.plan.get_selection_summary([str(self.floor.id)])
        partners = {r['partners'] for r in summary['resources'] if r['resource_type'] == 'contract'}
        self.assertTrue(any(self.gonza.display_name in p for p in partners))
        self.assertTrue(any('sin asignar' in p for p in partners))

    def test_actions_and_open(self):
        for action in self.plan.get_tree_actions():
            self.assertTrue(self.env.ref(action['xmlid'], raise_if_not_found=False))
        action = self.plan.action_open_tree()
        self.assertEqual(action['tag'], 'al_construction_planner.plan_tree')
        self.assertEqual(action['context']['active_id'], self.plan.id)
        options = self.plan.get_tree_filters()
        self.assertIn('installation', [v for v, _label in options['stages']])
        self.assertEqual(options['levels']['apartment'], 'Departamento')

    def test_access(self):
        outsider = new_test_user(self.env, 'plan_tree_ajeno', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.plan.with_user(outsider).get_tree_nodes('p')
        reporter = new_test_user(
            self.env, 'plan_tree_capataz', groups='al_construction_planner.group_planner_progress')
        self.assertEqual(self.plan.with_user(reporter).get_tree_nodes('root')[0]['modules'], 66)


@tagged('post_install', '-at_install')
class TestPlanTreeTour(HttpCase):

    def test_plan_tree_tour(self):
        plan = load_demo(self.env, 'TEST TOUR')['plan']
        self.start_tour(
            f'/odoo/{plan.id}/action-al_construction_planner.action_construction_plan_tree',
            'al_construction_planner_plan_tree', login='admin')
