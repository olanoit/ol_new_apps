# -*- coding: utf-8 -*-
"""Hoja de trabajo de la oficina técnica (v1.8, M18-22).

Criterio: la COCINA 04 armada solo en la hoja, con un material que no existe
en el maestro, se envía al planificador y deja la obra con su árbol, la
tipología, sus muebles y sus módulos con código, tipo y método de unión, la
lista de materiales de cada módulo, las actividades y tarifas de la obra, el
contrato con sus hitos y el producto nuevo creado con su código. Un segundo
envío no duplica nada."""
import json

from odoo.tests import tagged

from odoo.addons.al_construction_planner_suite.tests.common import PlannerCommon
from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import SHEETS


def _rows(name, records):
    """Filas de una pestaña: encabezados y valores por clave."""
    columns = SHEETS[name][1]
    header = [h for _k, h, _r, _x in columns]
    return [header] + [[record.get(key, '') for key, _h, _r, _x in columns]
                       for record in records]


@tagged('post_install', '-at_install')
class TestWorksheetV18(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Category = cls.env['product.category']
        cls.boards = Category.create({'name': 'TEST18 TABLEROS',
                                      'construction_family_code': '9181'})
        Product = cls.env['product.product']
        cls.white = Product.create({'name': 'Tablero melamínico blanco (test v18h)',
                                    'default_code': 'T18H-MEL', 'type': 'consu',
                                    'categ_id': cls.boards.id, 'standard_price': 120.0})
        cls.screw = Product.create({'name': 'Tornillo 4x50 (test v18h)',
                                    'default_code': 'T18H-TOR', 'type': 'consu',
                                    'standard_price': 0.05})
        cls.client = cls.env['res.partner'].create({'name': 'Inmobiliaria hoja (test v18h)'})
        cls.site = cls.env['project.project'].create({'name': 'Obra MOMEN hoja (test)',
                                                      'is_construction_site': True})

    def _sheets(self):
        assembly = self.act_screw.code
        return {
            'TIPOLOGIAS': _rows('TIPOLOGIAS', [{'code': 'COCINA 04', 'name': 'Cocina 04',
                                                'family': 'Cocina'}]),
            'MUEBLES': _rows('MUEBLES', [
                {'typology': 'COCINA 04', 'name': 'Mueble bajo', 'ml_group': 'Bajo'},
                {'typology': 'COCINA 04', 'name': 'Mueble alto', 'ml_group': 'Alto'}]),
            'MODULOS': _rows('MODULOS', [
                {'typology': 'COCINA 04', 'code': 'MB01', 'type': 'Bajo', 'width': 800,
                 'ml_group': 'Mueble bajo', 'furniture': 'Mueble bajo', 'activity': assembly,
                 'name': 'MOD LAVADERO 800', 'module_class': 'Estándar',
                 'join_method': 'Tornillo'},
                {'typology': 'COCINA 04', 'code': 'MA01', 'type': 'Campana', 'width': 605,
                 'ml_group': 'Mueble alto', 'furniture': 'Mueble alto',
                 'name': 'MOD ALTO CAMPANA 605', 'module_class': 'Especial',
                 'join_method': 'Mixto'}]),
            'BOM': _rows('BOM', [
                {'typology': 'COCINA 04', 'module': 'MB01', 'product_code': 'T18H-MEL',
                 'product_name': '[T18H-MEL] Tablero', 'qty': 0.5, 'stage': 'Producción'},
                {'typology': 'COCINA 04', 'module': 'MB01', 'product_code': 'T18H-TOR',
                 'qty': 25, 'stage': '1.2 Armado'},
                {'typology': 'COCINA 04', 'module': 'MA01', 'product_code': 'PROV-1',
                 'product_name': '[PROV-1] Tablero nuevo', 'qty': 0.3, 'stage': 'Producción'}]),
            'PIEZAS': _rows('PIEZAS', [
                {'typology': 'COCINA 04', 'module': 'MB01', 'qty': 2, 'length': 730,
                 'width': 400, 'piece_type': 'PUERTA', 'color': 'BLANCO',
                 'product_code': 'T18H-MEL'}]),
            'PRODUCTOS NUEVOS': _rows('PRODUCTOS NUEVOS', [
                {'code': 'PROV-1', 'name': 'Tablero melamínico capri 18 mm (test v18h)',
                 'uom': 'Units', 'categ': 'TEST18 TABLEROS', 'cost': 140.0}]),
            'TARIFAS': _rows('TARIFAS', [{'activity': assembly, 'price': 6.5}]),
            'CONTRATOS': _rows('CONTRATOS', [{'name': 'Contrato cocinas (test)',
                                              'partner': self.client.name,
                                              'advance': 10, 'guarantee': 5,
                                              'milestone_template': 'Hitos cocina (test)'}]),
            'HITOS': _rows('HITOS', [
                {'template': 'Hitos cocina (test)', 'name': 'Instalado', 'pct': 70},
                {'template': 'Hitos cocina (test)', 'name': 'Entregado', 'pct': 30}]),
            'VENTA': _rows('VENTA', [{'contract': 'Contrato cocinas (test)',
                                      'typology': 'COCINA 04', 'price': 9500}]),
            'ARBOL': _rows('ARBOL', [{'floor': 'Piso 03', 'apartment': 'Dpto 304',
                                      'space': 'Cocina', 'typology': 'COCINA 04'}]),
        }

    def _send(self):
        self.site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id)])
        action = document.action_construction_send_to_planner(self._sheets())
        wizard = self.env['construction.master.import.wizard'].browse(action['res_id'])
        data = wizard._analyze()
        self.assertFalse(data['errors'], data['errors'])
        wizard.action_import()
        return data

    def test_template_structure(self):
        data = self.site._construction_spreadsheet_data()
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        self.assertFalse(sheets['_LISTAS'].get('isVisible', True))
        pieces = sheets['PIEZAS']
        self.assertIn('m² (calc.)', pieces['cells'].values())
        bom = sheets['BOM']
        product_rules = [r for r in bom['dataValidationRules'] if '_prod_' in r['id']]
        self.assertEqual(len(product_rules), self.site.construction_spreadsheet_rows)
        self.assertEqual(len(data['pivots']), 4)
        self.assertTrue(all(p['rows'][0]['order'] == 'asc' for p in data['pivots'].values()))
        self.assertIn('=PIVOT(1,', sheets['RESUMEN']['cells']['A2'])
        products = self.env['product.product'].search_count(
            [('type', '=', 'consu'), ('company_id', 'in', (self.site.company_id.id, False))])
        self.assertIn('=ODOO.LIST(3,%s,"display_name")' % products,
                      sheets['REFERENCIAS']['cells'].values())
        # En construcción la hoja es la del presupuesto y el plan (CREVAL v1.0, 6.7).
        works = self.env['project.project'].create({
            'name': 'Obra por partidas (test hoja)', 'is_construction_site': True,
            'construction_profile_id': self.env.ref(
                'al_construction_planner.profile_construction').id})
        works.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', works.id)])
        self.assertEqual(document.construction_sheet_kind, 'budget')
        names = [sheet['name'] for sheet in json.loads(document.spreadsheet_data)['sheets']]
        self.assertIn('PRESUPUESTO', names)

    def test_kitchen_from_the_worksheet(self):
        self._send()
        typology = self.env['construction.typology'].search([('project_id', '=', self.site.id)])
        self.assertEqual(typology.code, 'COCINA 04')
        modules = typology.module_line_ids.sorted('sequence')
        self.assertEqual(modules.mapped('code'), ['MB01', 'MA01'])
        self.assertEqual(modules.mapped('join_method'), ['screw', 'mixed'])
        self.assertEqual(modules[1].module_class, 'special')
        self.assertEqual(modules[1].name, 'MOD ALTO CAMPANA 605')
        self.assertFalse(modules[1].assembly_activity_id)
        new = self.env['product.product'].search(
            [('name', '=', 'Tablero melamínico capri 18 mm (test v18h)')])
        self.assertEqual(len(new), 1)
        self.assertTrue(new.default_code.startswith('9181'))
        self.assertEqual(new.categ_id, self.boards)
        self.assertEqual(modules[1].material_ids.product_id, new)
        self.assertEqual(modules[0].material_ids.filtered(
            lambda m: m.product_id == self.screw).stage, 'assembly')
        self.assertEqual(len(modules[0].piece_ids), 1)
        rate_list = self.env['construction.rate.list'].search([('project_id', '=', self.site.id)])
        self.assertAlmostEqual(rate_list.line_ids.price, 6.5)
        contract = self.env['construction.contract'].search([('project_id', '=', self.site.id)])
        self.assertEqual(contract.milestone_template_id.line_ids.mapped('pct'), [70.0, 30.0])
        self.assertAlmostEqual(contract.price_line_ids.unit_price, 9500.0)
        space = self.env['project.task'].search([('project_id', '=', self.site.id),
                                                 ('construction_level', '=', 'space')])
        self.assertEqual(space.construction_typology_id, typology)
        # Un segundo envío no duplica nada.
        self._send()
        self.assertEqual(self.env['product.product'].search_count(
            [('name', '=', 'Tablero melamínico capri 18 mm (test v18h)')]), 1)
        self.assertEqual(len(typology.module_line_ids), 2)
        self.assertEqual(len(modules[1].material_ids), 1)
        self.assertEqual(self.env['construction.contract'].search_count(
            [('project_id', '=', self.site.id)]), 1)
        self.assertEqual(len(rate_list.line_ids), 1)
        self.assertEqual(self.env['project.task'].search_count(
            [('project_id', '=', self.site.id), ('construction_level', '=', 'space')]), 1)
