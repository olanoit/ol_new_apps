# -*- coding: utf-8 -*-
"""Etapas con sub etapas (v1.8, M18-02) y secuencia de mobiliario (M18-14).

El perfil Mobiliario deja «1 Producción › 1.1 Producción de piezas, 1.2
Armado» y «2 Instalación › 2.1 Instalación, 2.2 Acabado, 2.3 Limpieza». Las
etapas de siempre conservan su código (los montos no cambian); la etapa padre
solo suma y el filtro de etapas es un árbol.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_schedule import TestSchedule

REF = 'al_construction_planner.'


@tagged('post_install', '-at_install')
class TestStagesV18(TestSchedule):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Catalog = cls.env['construction.stage']

    def test_furniture_sequence(self):
        """Las cinco sub etapas en orden y con su número; las etapas padre no
        están en la lista de los campos de etapa."""
        self.assertEqual(self.Catalog._codes()[:5],
                         ['production', 'assembly', 'installation', 'finishing', 'cleaning'])
        labels = dict(self.Catalog._get_selection())
        self.assertEqual(labels['production'], '1.1 Producción de piezas')
        self.assertEqual(labels['assembly'], '1.2 Armado')
        self.assertEqual(labels['installation'], '2.1 Instalación')
        self.assertEqual(labels['finishing'], '2.2 Acabado')
        self.assertEqual(labels['cleaning'], '2.3 Limpieza')
        self.assertNotIn('furniture_production', labels)
        tree = [(node['label'], node['depth']) for node in self.Catalog._get_tree()][:7]
        self.assertEqual(tree, [
            ('1 Producción', 0), ('1.1 Producción de piezas', 1), ('1.2 Armado', 1),
            ('2 Instalación', 0), ('2.1 Instalación', 1), ('2.2 Acabado', 1),
            ('2.3 Limpieza', 1)])
        profile = self.env.ref(REF + 'profile_furniture')
        self.assertIn(self.env.ref(REF + 'stage_cleaning'), profile.stage_ids)
        self.assertEqual(self.Catalog._leaf_codes(['furniture_production']),
                         ['production', 'assembly'])

    def test_resources_go_to_sub_stages(self):
        line = self.plan.line_ids[:1]
        with self.assertRaises(ValidationError):
            self.env['construction.resource.plan.line'].create({
                'plan_id': self.plan.id, 'resource_type': 'material',
                'product_id': line.product_id.id or self.plan.line_ids.product_id[:1].id,
                'stage': 'furniture_production', 'qty_planned': 1,
                'product_uom_id': self.env.ref('uom.product_uom_unit').id})
        # Una etapa con recursos no puede pasar a tener sub etapas.
        with self.assertRaises(ValidationError):
            self.Catalog.create({'name': 'Corte (test)', 'code': 'test_cut', 'kind': 'production',
                                 'parent_id': self.env.ref(REF + 'stage_production').id})
        lines = self.plan.line_ids
        self.assertEqual(set(lines.filtered(lambda l: l.stage in ('production', 'assembly'))
                             .mapped('stage_parent')), {'furniture_production'})
        self.assertEqual(set(lines.filtered(lambda l: l.stage == 'finishing')
                             .mapped('stage_parent')), {'furniture_installation'})

    def test_filter_by_parent_stage(self):
        """Criterio de M18-02: marcar Producción deja sus dos sub etapas y el
        cronograma y el panel muestran solo esas."""
        tree = {node['code']: node for node in self.plan.get_tree_filters()['stage_tree']}
        self.assertEqual(tree['furniture_production']['leaves'], ['production', 'assembly'])
        self.assertEqual(tree['assembly']['parent'], 'furniture_production')
        payload = self._gantt(construction_stages=['furniture_production'])
        self.assertEqual({row['stage'] for row in payload['construction_stages']},
                         {'production', 'assembly'})
        groups = payload['construction_stage_groups']
        self.assertEqual({group['stage'] for group in groups}, {'furniture_production'})
        self.assertEqual(len(groups), 8)
        group = groups[0]
        children = [row for row in payload['construction_stages']
                    if row['group_key'] == group['key']]
        self.assertEqual([row['stage'] for row in children], ['production', 'assembly'])
        self.assertAlmostEqual(group['amount'], round(sum(r['amount'] for r in children), 2))
        summary = self.plan.get_selection_summary(
            [str(self.floor.id)], {'stages': ['furniture_production']})
        lines = self.plan.line_ids.filtered(lambda l: l.stage in ('production', 'assembly'))
        self.assertAlmostEqual(summary['total'], round(sum(lines.mapped('amount_planned')), 2))
        load = self.plan.get_schedule_load(['furniture_installation'])
        self.assertEqual({row['stage'] for row in load['rows']} - {'installation', 'finishing'},
                         set())

    def test_parent_bar_and_chained_sub_stages(self):
        payload = self._gantt()
        groups = {group['key']: group for group in payload['construction_stage_groups']}
        self.assertEqual({group['stage'] for group in groups.values()},
                         {'furniture_production', 'furniture_installation'})
        space = self.spaces[0]
        rows = [row for row in payload['construction_stages'] if row['space_task_id'] == space.id]
        # Armado → Instalación también encadena entre etapas padre.
        links = {(link['source'], link['target']) for link in payload['construction_stage_links']}
        by_stage = {row['stage']: row['id'] for row in rows}
        self.assertIn((by_stage['assembly'], by_stage['installation']), links)
        self.assertNotEqual(next(r for r in rows if r['stage'] == 'assembly')['group_key'],
                            next(r for r in rows if r['stage'] == 'installation')['group_key'])

    def test_control_in_tree_order(self):
        html = str(self.plan.control_html)
        order = ['1 Producción', '1.1 Producción de piezas', '1.2 Armado', '2 Instalación',
                 '2.1 Instalación', '2.2 Acabado']
        positions = [html.index(label) for label in order]
        self.assertEqual(positions, sorted(positions))
        summary = str(self.plan.stage_summary_html)
        self.assertLess(summary.index('1 Producción'), summary.index('1.2 Armado'))

    def test_import_names(self):
        find = self.Catalog._find_by_text
        self.assertEqual(find('Producción'), 'production')
        self.assertEqual(find('PRODUCCION'), 'production')
        self.assertEqual(find('1.2 Armado'), 'assembly')
        self.assertEqual(find('Acabado y entrega'), 'finishing')
        self.assertEqual(find('2.3'), 'cleaning')
        self.assertIsNone(find('Instalación eléctrica'))

    def test_profile_export_keeps_tree(self):
        profile = self.env.ref(REF + 'profile_furniture')
        data = profile._export_data()
        stages = {stage['code']: stage for stage in data['stages']}
        self.assertEqual(stages['assembly']['parent'], 'furniture_production')
        self.assertEqual(stages['assembly']['number'], '1.2')
        self.assertEqual([stage['code'] for stage in data['stages']][:3],
                         ['furniture_production', 'production', 'assembly'])


# Las pruebas del cronograma ya corren en TestSchedule.
for _name in dir(TestSchedule):
    if _name.startswith('test_') and callable(getattr(TestSchedule, _name)) \
            and _name not in vars(TestStagesV18):
        setattr(TestStagesV18, _name, None)
