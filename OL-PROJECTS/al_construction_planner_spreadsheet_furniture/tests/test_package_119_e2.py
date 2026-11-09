# -*- coding: utf-8 -*-
"""Paquete 1.19, entrega 2. M119-04: actividades de cada tipología en una
matriz por etapa.

* La plantilla tiene una pestaña por etapa con actividades (nombre y bloques
  del catálogo de etapas) y ACTIVIDADES queda oculta.
* Las actividades por módulo y por ML son celdas grises calculadas; las por
  ambiente, amarillas.
* El envío arma ACTIVIDADES con las celdas escritas y las de ML; las de
  módulo no van, porque «Generar plan» saca el armado de MODULOS.
* «Actualizar a la plantilla vigente» pasa las filas de ACTIVIDADES a la
  matriz y, en una hoja que ya la tiene, conserva lo escrito."""
from odoo.tests import tagged

from ..models.activity_matrix import (
    CODE_ROW, FIRST_ROW, HEADER_ROW, KIND_ML, KIND_MODULE, KIND_ROW, MATRIX_CODE_LABEL,
    MATRIX_KIND_LABEL, _col, merge_matrix,
)
from .test_worksheet_v18 import TestWorksheetV18, _rows


@tagged('post_install', '-at_install')
class TestPackage119Matrix(TestWorksheetV18):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Activity = cls.env['construction.labor.activity']
        unit = cls.env.ref('uom.product_uom_unit')
        meter = cls.env.ref('uom.product_uom_meter')
        cls.push = Activity.create({'code': 'T19-PUSH', 'name': 'Push (test 1.19)',
                                    'stage': 'installation', 'uom_id': unit.id,
                                    'default_price': 4.0, 'sequence': 1})
        cls.ml_low = Activity.create({'code': 'T19-MLB', 'name': 'Mueble bajo ML (test 1.19)',
                                      'stage': 'installation', 'uom_id': meter.id,
                                      'default_price': 12.0, 'ml_based': True,
                                      'ml_group': 'low', 'sequence': 2})
        cls.module = Activity.create({'code': 'T19-ARM', 'name': 'Armado (test 1.19)',
                                      'stage': 'assembly', 'uom_id': unit.id,
                                      'default_price': 6.0, 'module_level': True,
                                      'sequence': 1})

    def _data(self):
        return self.site._construction_spreadsheet_data(10)

    def _tab_of(self, code):
        for tab in self.site._construction_matrix_tabs():
            if code in tab['activities'].mapped('code'):
                return tab
        return None

    def _matrix_sheet(self, data, code):
        tab = self._tab_of(code)
        return next(sheet for sheet in data['sheets'] if sheet['name'] == tab['name'])

    def _column(self, sheet, code):
        return next(ref[:-len(str(CODE_ROW))] for ref, value in sheet['cells'].items()
                    if ref.endswith(str(CODE_ROW)) and ref[:-len(str(CODE_ROW))].isalpha()
                    and value == code)

    def test_template_has_a_matrix_per_stage(self):
        data = self._data()
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        self.assertFalse(sheets['ACTIVIDADES'].get('isVisible', True))
        install, assembly = self._tab_of('T19-PUSH'), self._tab_of('T19-ARM')
        self.assertNotEqual(install['name'], assembly['name'])
        self.assertTrue(install['name'].startswith('ACT '))
        names = [sheet['name'] for sheet in data['sheets']]
        for name in (install['name'], assembly['name']):
            self.assertGreater(names.index(name), names.index('MODULOS'))
            self.assertLess(names.index(name), names.index('BOM'))
        sheet = sheets[install['name']]
        self.assertEqual(sheet['cells']['A%s' % CODE_ROW], MATRIX_CODE_LABEL)
        self.assertEqual(sheet['cells']['A%s' % KIND_ROW], MATRIX_KIND_LABEL)
        push, ml = self._column(sheet, 'T19-PUSH'), self._column(sheet, 'T19-MLB')
        self.assertEqual(sheet['cells']['%s%s' % (push, HEADER_ROW)], 'Push (test 1.19) · %s'
                         % self.push.uom_id.name)
        self.assertEqual(sheet['cells']['%s%s' % (push, KIND_ROW)], 'data')
        self.assertNotIn('%s%s' % (push, FIRST_ROW), sheet['cells'])
        self.assertEqual(sheet['cells']['%s%s' % (ml, KIND_ROW)], KIND_ML)
        self.assertIn('Mueble bajo', sheet['cells']['%s%s' % (ml, FIRST_ROW)])
        # La tipología de la fila sale de TIPOLOGIAS.
        self.assertIn('TIPOLOGIAS!', sheet['cells']['A%s' % FIRST_ROW])
        arm_sheet = sheets[assembly['name']]
        arm = self._column(arm_sheet, 'T19-ARM')
        self.assertEqual(arm_sheet['cells']['%s%s' % (arm, KIND_ROW)], KIND_MODULE)
        self.assertIn('Actividad efectiva (calc.)', str(
            sheets['MODULOS']['cells'].values()))
        self.assertIn('COUNTIFS(', arm_sheet['cells']['%s%s' % (arm, FIRST_ROW)])
        # INICIO suma las contratas de la matriz.
        self.assertIn("'%s'!" % install['name'] if ' ' in install['name'] else install['name'],
                      str(sheets['INICIO']['cells'].values()))

    def _matrix_rows(self, code_cells):
        """Valores calculados de una matriz con la tipología COCINA 04:
        ``code_cells`` = [(código, tipo, cantidad)]."""
        header = ['Tipología'] + ['x'] * len(code_cells)
        codes = [MATRIX_CODE_LABEL] + [code for code, _kind, _qty in code_cells]
        kinds = [MATRIX_KIND_LABEL] + [kind for _code, kind, _qty in code_cells]
        filler = [['Sub etapa'], ['Tarifa'], ['Cantidad en la obra (calc.)']]
        row = ['COCINA 04'] + [qty for _code, _kind, qty in code_cells]
        return [header, codes, kinds] + filler + [row, ['']]

    def test_merge_sends_written_and_ml_cells(self):
        rows = self._matrix_rows([('T19-PUSH', 'data', 2), ('T19-MLB', KIND_ML, 2.39),
                                  ('T19-ARM', KIND_MODULE, 5), ('T19-PUSH2', 'data', '')])
        merged = merge_matrix({'ACT X': rows, 'ACTIVIDADES': [['typology', 'activity', 'qty'],
                                                             ['OLD', 'OLD', 1]]})
        self.assertEqual(merged['ACTIVIDADES'], [
            ['typology', 'activity', 'qty'], ['COCINA 04', 'T19-PUSH', 2],
            ['COCINA 04', 'T19-MLB', 2.39]])
        # Una hoja sin matriz se envía como antes.
        old = {'ACTIVIDADES': [['typology', 'activity', 'qty'], ['A', 'B', 1]]}
        self.assertIs(merge_matrix(old), old)

    def test_send_from_the_matrix(self):
        self.site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])
        tab = self._tab_of('T19-PUSH')
        self.assertIn(tab['name'], document._construction_send_sheet_names())
        sheets = self._sheets()
        sheets.pop('ACTIVIDADES', None)
        sheets[tab['name']] = self._matrix_rows([('T19-PUSH', 'data', 3)])
        action = document.action_construction_send_to_planner(sheets)
        wizard = self.env['construction.master.import.wizard'].browse(action['res_id'])
        data = wizard._analyze()
        self.assertFalse(data['errors'], data['errors'])
        wizard.action_import()
        typology = self.env['construction.typology'].search(
            [('project_id', '=', self.site.id), ('code', '=', 'COCINA 04')])
        line = typology.activity_line_ids.filtered(lambda l: l.activity_id == self.push)
        self.assertEqual(line.qty, 3.0)

    def _upgrade_inputs(self, data):
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        master = {
            'TIPOLOGIAS': {'rows': [['Código', 'Nombre'], ['C01', 'Cocina 1'],
                                    ['C02', 'Cocina 2']], 'keys': {'code': 0, 'name': 1}},
            'ACTIVIDADES': {'rows': [['Tipología', 'Actividad', 'Cantidad por ambiente'],
                                     ['C02', 'T19-PUSH', 4], ['C01', 'T19-MLB', 2.5],
                                     ['C01', 'T19-EXTRA', 1]],
                            'keys': {'typology': 0, 'activity': 1, 'qty': 2}},
        }
        return sheets, master

    def test_upgrade_moves_activities_to_the_matrix(self):
        self.env['construction.labor.activity'].create({
            'code': 'T19-EXTRA', 'name': 'Extra (test 1.19)', 'stage': 'installation',
            'uom_id': self.env.ref('uom.product_uom_unit').id})
        data = self._data()
        sheets, master = self._upgrade_inputs(data)
        Document = self.env['documents.document']
        Document._construction_upgrade_matrix(sheets, self.site, master, {})
        sheet = self._matrix_sheet(data, 'T19-PUSH')
        push = self._column(sheet, 'T19-PUSH')
        ml = self._column(sheet, 'T19-MLB')
        extra = self._column(sheet, 'T19-EXTRA')
        self.assertEqual(sheet['cells']['%s%s' % (push, FIRST_ROW + 1)], '4')
        self.assertEqual(sheet['cells']['%s%s' % (extra, FIRST_ROW)], '1')
        # Las de ML se calculan: no se escriben.
        self.assertIn('SUMIFS', sheet['cells']['%s%s' % (ml, FIRST_ROW)])

    def test_upgrade_unknown_column_goes_to_a_spare(self):
        # Una actividad de otra compañía no tiene columna: va a la primera libre
        # de la pestaña de su etapa.
        other = self.env['res.company'].create({'name': 'Otra compañía (test 1.19)'})
        extra = self.env['construction.labor.activity'].create({
            'code': 'T19-EXTRA', 'name': 'Extra (test 1.19)', 'stage': 'installation',
            'uom_id': self.env.ref('uom.product_uom_unit').id, 'company_id': other.id})
        data = self._data()
        sheets, master = self._upgrade_inputs(data)
        sheet = self._matrix_sheet(data, 'T19-PUSH')
        tab = self._tab_of('T19-PUSH')
        self.assertNotIn(extra, tab['activities'])
        self.env['documents.document']._construction_upgrade_matrix(sheets, self.site, master,
                                                                    {})
        spare = _col(1 + len(tab['activities']))
        self.assertEqual(sheet['cells']['%s%s' % (spare, HEADER_ROW)], 'T19-EXTRA')
        self.assertEqual(sheet['cells']['%s%s' % (spare, FIRST_ROW)], '1')

    def test_upgrade_keeps_an_existing_matrix(self):
        data = self._data()
        sheets, master = self._upgrade_inputs(data)
        tab = self._tab_of('T19-PUSH')
        sheet = self._matrix_sheet(data, 'T19-PUSH')
        push = self._column(sheet, 'T19-PUSH')
        spare = _col(1 + len(tab['activities']))
        old = {tab['name']: {'cells': {
            '%s%s' % (push, CODE_ROW): 'T19-PUSH', '%s%s' % (push, FIRST_ROW): '7',
            '%s%s' % (spare, HEADER_ROW): 'T19-OTHER',
            '%s%s' % (spare, CODE_ROW): '=IF(x)', '%s%s' % (spare, FIRST_ROW + 1): '2'}}}
        self.env['documents.document']._construction_upgrade_matrix(sheets, self.site, master,
                                                                    old)
        self.assertEqual(sheet['cells']['%s%s' % (push, FIRST_ROW)], '7')
        # Lo de ACTIVIDADES (vieja) no pisa la matriz.
        self.assertNotIn('%s%s' % (push, FIRST_ROW + 1), sheet['cells'])
        self.assertEqual(sheet['cells']['%s%s' % (spare, HEADER_ROW)], 'T19-OTHER')
        self.assertEqual(sheet['cells']['%s%s' % (spare, FIRST_ROW + 1)], '2')

    def test_sheet_key_of_assembly_activities(self):
        screw = self.env['construction.labor.activity'].create({
            'code': 'T19-TOR', 'name': 'Tornillo (test 1.19)', 'stage': 'assembly',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'activity_class': 'assembly_method', 'join_method': 'screw'})
        self.assertEqual(screw.construction_sheet_key, 'join:Tornillo')
        self.assertFalse(self.push.construction_sheet_key)
