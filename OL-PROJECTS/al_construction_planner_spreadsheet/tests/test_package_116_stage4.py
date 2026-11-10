# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4, bloque 4a: hoja de presupuesto y plan.

* M116-09 y CR-22 d: las columnas se leen por su clave interna (_CLAVES): un
  encabezado renombrado no rompe el envío y una columna obligatoria borrada
  da un error en ERRORES.
* CR-22 c: ninguna fórmula usa N().
* CR-22 e: «Traer de Odoo» trae el rendimiento de la receta.
* CR-22 g: el insumo se elige por nombre; «Traer de Odoo» escribe por clave.
* CR-22 b y f: la migración deja las hojas anteriores como las nuevas.
* El tipo de hoja sale del perfil de la obra.
"""
import base64
import json
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.al_construction_planner_spreadsheet.models import sheet_migration
from odoo.addons.al_construction_planner_spreadsheet.models.project_project import (
    PRESUPUESTO_KEYS, presupuesto_row,
)
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_keys import (
    KEYS_SHEET, apply_keys, keys_rows,
)
from odoo.addons.al_construction_planner_suite.tests.test_budget_book_creval import (
    TestBudgetBook,
)

from .test_budget_worksheet import _sheets_from_book


def _keyed(sheets, columns):
    """Valores de _CLAVES como los calcula la hoja: ``{pestaña: {clave:
    columna (1 = A)}}``."""
    rows = [['Pestaña', 'Clave', 'Columna']]
    for sheet, keys in columns.items():
        rows += [[sheet, key, column] for key, column in keys.items()]
    return dict(sheets, **{KEYS_SHEET: rows})


@tagged('post_install', '-at_install')
class TestPackage116Stage4Budget(TestBudgetBook):

    def _document(self):
        self.order.action_construction_open_spreadsheet()
        return self.env['documents.document'].search([
            ('construction_sale_order_id', '=', self.order.id),
            ('construction_source_id', '=', False)])

    def test_template_without_n_and_with_keys(self):
        data = json.loads(self._document().spreadsheet_data)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        formulas = [content for sheet in data['sheets']
                    for content in sheet.get('cells', {}).values()
                    if isinstance(content, str) and content.startswith('=')]
        self.assertFalse([f for f in formulas if re.search(r'(?<![A-Z.])N\(', f)])
        self.assertTrue(any('IFERROR(VALUE(' in f for f in formulas))
        keys = sheets[KEYS_SHEET]
        self.assertFalse(keys.get('isVisible', True))
        rows = {(keys['cells'].get('A%s' % n), keys['cells'].get('B%s' % n)):
                keys['cells'].get('C%s' % n) for n in range(2, 200)}
        self.assertEqual(rows[('PRESUPUESTO', 'qty_real')], '=COLUMN(PRESUPUESTO!D1)')
        # APU_DETALLE: el insumo se elige por nombre; el código es fórmula y
        # se lee con su clave.
        detail = sheets['APU_DETALLE']['cells']
        self.assertEqual(detail['B1'], 'Insumo: escriba tipo o nombre')
        code_ref = rows[('APU_DETALLE', 'code')]
        column = re.search(r'!([A-Z]+)1', code_ref).group(1)
        self.assertEqual(detail['%s1' % column], 'Código del insumo')
        self.assertTrue(detail['%s2' % column].startswith('=IF(B2=""'))
        self.assertIn('Para elegir', sheets['INSUMOS']['cells'].values())
        self.assertEqual(sheets['ERRORES']['cells']['F2'], 'Ir')
        # Encabezados de fórmula en gris, de datos en amarillo.
        styles = data['styles']
        presupuesto = sheets['PRESUPUESTO']
        self.assertEqual(styles[str(presupuesto['styles']['G1'])]['fillColor'], '#D9D9D9')
        self.assertEqual(styles[str(presupuesto['styles']['A1'])]['fillColor'], '#FFF2CC')

    def test_budget_layout_name_first_code_last(self):
        """CR-22 g: nombre primero y código al final en INSUMOS y APU; la
        receta se elige por nombre en APU_DETALLE, con su código calculado y
        una banda de color por receta. Las hojas anteriores conservan su
        orden al traer de Odoo."""
        document = self._document()
        self.assertEqual(document.construction_sheet_layout, 3)
        data = json.loads(document.spreadsheet_data)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        keys = sheets[KEYS_SHEET]
        rows = {(keys['cells'].get('A%s' % n), keys['cells'].get('B%s' % n)):
                keys['cells'].get('C%s' % n) for n in range(2, 300)}

        def letter(sheet, key):
            return re.search(r'!([A-Z]+)1', rows[(sheet, key)]).group(1)

        insumos = sheets['INSUMOS']['cells']
        self.assertEqual(insumos['A1'], 'Tipo de insumo')
        self.assertEqual(insumos['%s1' % letter('INSUMOS', 'code')], 'Código')
        self.assertGreater(letter('INSUMOS', 'code'), letter('INSUMOS', 'worker_category'))
        apu = sheets['APU']['cells']
        self.assertEqual(apu['A1'], 'Descripción')
        self.assertEqual(apu['%s1' % letter('APU', 'code')], 'Código')
        self.assertIn('Para elegir', apu.values())
        detail = sheets['APU_DETALLE']
        self.assertEqual(detail['cells']['A1'], 'Receta (nombre · código)')
        apu_col = letter('APU_DETALLE', 'apu')
        self.assertEqual(detail['cells']['%s1' % apu_col], 'Código de la receta')
        self.assertTrue(detail['cells']['%s2' % apu_col].startswith('=IF(A2=""'))
        self.assertIn('APU_DETALLE_apu_pick', [rule['id'] for rule in
                                               detail['dataValidationRules']])
        band = detail['conditionalFormats'][0]
        self.assertEqual(band['id'], 'APU_DETALLE_band')
        self.assertIn('ISODD', band['rule']['values'][0])
        # Las fórmulas buscan por la letra de cada columna, no por la A.
        formulas = [content for name in ('APU', 'APU_DETALLE', 'PRESUPUESTO')
                    for content in sheets[name]['cells'].values()
                    if isinstance(content, str) and content.startswith('=')]
        self.assertFalse([f for f in formulas if 'VLOOKUP' in f and '$A$' in f])
        # «Traer de Odoo» en una hoja anterior: PRESUPUESTO con VLOOKUP sobre
        # la columna A de APU, como su orden.
        index = PRESUPUESTO_KEYS.index('unit_cost')
        self.assertIn('VLOOKUP(E2,APU!$A:$H,8,0)', presupuesto_row({'apu': 'R1'}, 2, 0)[index])
        self.assertIn('XLOOKUP(E2,APU!$G:$G,APU!$H:$H)',
                      presupuesto_row({'apu': 'R1'}, 2, 2)[index])
        self.assertIn('VLOOKUP(E2,APU!$A:$C,3,0)', presupuesto_row(
            {'apu': 'R1'}, 2, 0)[PRESUPUESTO_KEYS.index('uom')])

    def test_renamed_header_and_missing_column(self):
        document = self._document()
        sheets = _sheets_from_book(base64.b64decode(self._book()))
        # El presupuestador renombra «Código del insumo» y «Metrado real».
        detail = [list(row) for row in sheets['APU_DETALLE']]
        detail[0][1] = 'Insumo del APU (mi nombre)'
        budget = [list(row) for row in sheets['PRESUPUESTO']]
        position = budget[0].index('Metrado real')
        budget[0][position] = 'Metrado (propio)'
        renamed = dict(sheets, APU_DETALLE=detail, PRESUPUESTO=budget)
        self.assertTrue(document.action_construction_validate(renamed)['errors'],
                        'sin claves el encabezado renombrado no se encuentra')
        keyed = _keyed(renamed, {'APU_DETALLE': {'apu': 1, 'code': 2},
                                 'PRESUPUESTO': {'qty_real': position + 1}})
        result = document.action_construction_validate(keyed)
        self.assertEqual(result['errors'], 0, result['rows'])
        action = document.action_construction_send_to_planner(keyed, 'budget')
        wizard = self.env[action['res_model']].browse(action['res_id'])
        self.assertEqual(wizard.state, 'preview', wizard.preview_html)
        # La columna obligatoria borrada (#REF en _CLAVES) es un error.
        removed = _keyed(dict(renamed, PRESUPUESTO=[
            row[:position] + row[position + 1:] for row in budget]),
            {'APU_DETALLE': {'apu': 1, 'code': 2}})
        removed[KEYS_SHEET].append(['PRESUPUESTO', 'qty_real', '#REF'])
        result = document.action_construction_validate(removed)
        self.assertTrue(result['errors'])
        self.assertTrue(any(row[0] == 'PRESUPUESTO' and row[4] == 'Error'
                            for row in result['rows']), result['rows'])

    def test_bring_from_odoo_by_key_with_productivity(self):
        document = self._document()
        sheets = _sheets_from_book(base64.b64decode(self._book()))
        action = document.action_construction_send_to_planner(sheets, 'plan')
        self.env[action['res_model']].browse(action['res_id']).action_import()
        rows = document.construction_odoo_rows()
        keyed = rows['_keyed']
        apu = keyed['APU']
        recipe = dict(zip(apu['keys'], apu['rows'][0]))
        self.assertEqual(recipe['code'], 'BK-R01')
        self.assertEqual(float(recipe['productivity']), 19.0)   # CR-22 e
        self.assertTrue(recipe['hours'])
        detail = keyed['APU_DETALLE']
        self.assertIn('code', detail['keys'])
        line = dict(zip(detail['keys'], detail['rows'][0]))
        self.assertTrue(line['pick'].endswith(' · %s' % line['code']))
        # CR-22 g: la receta por nombre, con el código al final.
        self.assertTrue(line['apu_pick'].endswith(' · %s' % line['apu']))
        self.assertNotIn('[', line['pick'])                      # CR-22 g
        insumos = keyed['INSUMOS']
        names = [dict(zip(insumos['keys'], row))['name'] for row in insumos['rows']]
        self.assertFalse([name for name in names if name.startswith('[')])
        self.assertIn('Código del insumo', detail['aliases']['code'])

    def test_migration_of_an_old_sheet(self):
        """CR-22 b, c y f: una hoja anterior queda sin N(), con «Costo
        unitario sin APU», encabezados de fórmula en gris y _CLAVES."""
        old = {
            'version': '18.5.10',
            'styles': {'1': {'bold': True, 'fillColor': '#DDE4EE'},
                       '3': {'bold': True, 'fillColor': '#FFF2CC'}},
            'sheets': [
                {'id': 's1', 'name': 'APU_DETALLE', 'cells': {
                    'A1': 'Código del APU', 'B1': 'Código del insumo', 'C1': 'Cuadrilla',
                    'H1': 'Cantidad (calc.)',
                    'H2': '=IF(A2="","",IF(C2<>"",C2*8,N(E2)))',
                    'H3': {'content': '=MIN(N(E3),LEN("N(x)"))'}},
                 'styles': {'H1': 3}},
                {'id': 's2', 'name': 'PRESUPUESTO', 'cells': {
                    'A1': 'Ítem', 'D1': 'Partida', 'E1': 'Código del APU',
                    'H1': 'Metrado real', 'M1': 'Costo unitario'}, 'styles': {}},
            ],
        }
        self.assertTrue(self._migration_module()._transform(old))
        detail, budget = old['sheets'][0], old['sheets'][1]
        self.assertEqual(detail['cells']['H2'],
                         '=IF(A2="","",IF(C2<>"",C2*8,IFERROR(VALUE(E2),0)))')
        self.assertEqual(detail['cells']['H3']['content'],
                         '=MIN(IFERROR(VALUE(E3),0),LEN("N(x)"))')
        self.assertEqual(budget['cells']['N1'], 'Costo unitario sin APU')
        grey = old['styles'][str(detail['styles']['H1'])]
        self.assertEqual(grey['fillColor'], '#D9D9D9')
        keys = next(sheet for sheet in old['sheets'] if sheet['name'] == KEYS_SHEET)
        self.assertIn('=COLUMN(PRESUPUESTO!H1)', keys['cells'].values())
        self.assertFalse(self._migration_module()._transform(old), 'una segunda vez no cambia')

    def _migration_module(self):
        import importlib.util
        from odoo.modules.module import get_module_path
        path = '%s/migrations/9.20261101/post-migrate.py' % get_module_path(
            'al_construction_planner_spreadsheet')
        spec = importlib.util.spec_from_file_location('migration_9', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_sheet_kind_from_profile(self):
        Profile = self.env['construction.vertical.profile']
        deep = Profile.search([('code', '=', 'construction_prof4')], limit=1)
        self.assertTrue(deep)
        site = self.env['project.project'].create({
            'name': 'Obra PROF 4 (test hoja)', 'is_construction_site': True,
            'construction_profile_id': deep.id})
        self.assertEqual(site._construction_spreadsheet_kind(), 'budget')
        deep.construction_spreadsheet_kind = 'furniture'
        self.assertEqual(site._construction_spreadsheet_kind(), 'furniture')
        self.assertEqual(deep._export_data()['spreadsheet_kind'], 'furniture')


@tagged('post_install', '-at_install')
class TestSheetKeysHelpers(TransactionCase):
    """Ayudas puras de las claves y la migración."""

    def test_apply_keys(self):
        rows = keys_rows({'PRODUCTOS NUEVOS': [('code', 0)], 'BOM': [('qty', 3)]})
        self.assertEqual(rows[1][2], "=COLUMN('PRODUCTOS NUEVOS'!A1)")
        sheets = {
            'BOM': [['Tipología', 'Código', 'Producto', 'Mi cantidad'], ['C1', 'X', 'p', 2]],
            KEYS_SHEET: [['Pestaña', 'Clave', 'Columna'], ['BOM', 'qty', 4],
                         ['BOM', 'stage', '#REF']],
        }
        result = apply_keys(sheets)
        self.assertNotIn(KEYS_SHEET, result)
        self.assertEqual(result['BOM'][0], ['Tipología', 'Código', 'Producto', 'qty'])
        self.assertEqual(result['BOM'][1], ['C1', 'X', 'p', 2])
        self.assertEqual(sheets['BOM'][0][3], 'Mi cantidad', 'no cambia lo recibido')
        self.assertEqual(sheet_migration.replace_n('=SUMN(A1)+N(B1)'),
                         '=SUMN(A1)+IFERROR(VALUE(B1),0)')


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestBudgetBook):
    if _name.startswith('test_') and callable(getattr(TestBudgetBook, _name)) \
            and _name not in vars(TestPackage116Stage4Budget):
        setattr(TestPackage116Stage4Budget, _name, None)
