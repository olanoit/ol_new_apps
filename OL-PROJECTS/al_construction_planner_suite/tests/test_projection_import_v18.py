# -*- coding: utf-8 -*-
"""Importador de la proyección de materiales (v1.8, M17-18) y validación de
códigos (M17-19), con libros armados en la prueba en el formato de las hojas
de Allcenter (pestaña resumen «… POR PISO» y bloques «MODULO:»)."""
import base64
from io import BytesIO

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PlannerCommon

KITCHEN_COLUMNS = [
    # (etapa, nombre corto, código en la pestaña, código en el resumen, nombre completo)
    ('PRODUCCIÓN', 'MELAMINA BLANCO', 'T18-MEL', 'T18-MEL', 'MELAMINA BLANCO 18MM (test)'),
    ('PRODUCCIÓN', 'del blanco', 'T18-TAP', 'T18-TAP', 'TAPACANTO DELGADO BLANCO (test)'),
    ('ARMADO', 'tor 4*50', 'T18-T450', 'T18-T450', 'TORNILLOS 4X50 (test)'),
    ('ARMADO', 'TARUGOS', 'T18-TAR', 'T18-TAR', 'TARUGO 8X30 (test)'),
    ('INSTALACIÓN', 'tor 4*50', 'T18-T450', 'T18-T450', 'TORNILLOS 4X50 (test)'),
    ('ACABADOS', 'SICASIL', 'T18-SIL', 'T18-SIL', 'SILICONA SIKASIL (test)'),
]
# Módulos de la COCINA 04: (nombre, piezas, totales por columna).
KITCHEN_MODULES = [
    ('MOD BAJO  665 - COCINA 01', 'low',
     [(2, 780, 560, 'COSTADO', 'BLANCO', [0.8736, 5.36, 0, 0, 4, 0]),
      (2, 730, 332.5, 'PUERTA', 'BLANCO', [0.48545, 0.665, 12, 12, 0, 0])],
     [0.5531, 6.025, 12, 12, 4, 0.1]),
    ('MOD ALTO CAMPANA 605- COCINA 01', 'high',
     [(2, 400, 330, 'COSTADO', 'BLANCO', [0.264, 2.92, 20, 0, 3, 0]),
      (2, 400, 302.5, 'PUERTA', 'BLANCO', [0.242, 0, 0, 0, 0, 0])],
     [0.2628, 2.92, 20, 0, 3, 0.05]),
]


def kitchen_workbook(summary_code_override=None):
    from openpyxl import Workbook
    workbook = Workbook()
    summary = workbook.active
    summary.title = 'COCINAS POR PISO '
    columns = list(KITCHEN_COLUMNS)
    if summary_code_override:
        columns[0] = columns[0][:3] + (summary_code_override,) + columns[0][4:]
    summary.append([None, None, None] + [c[0] for c in columns])
    summary.append([None, None, None] + [c[1] for c in columns])
    summary.append([None, None, None] + [c[3] for c in columns])
    summary.append(['PISOS', 'DESCRIPCION COCINA POR DEPARTAMENTO', 'CANTIDAD']
                   + [c[4] for c in columns])
    summary.append([])
    summary.append(['PISO 03'])
    totals = [sum(m[3][i] for m in KITCHEN_MODULES) for i in range(len(columns))]
    summary.append([None, 'COCINA 04_DEP 304', 1] + totals)
    summary.append([None, 'COCINA 04_DEP 305', 1] + totals)
    summary.append([None, 'TOTAL DPTOS PISO 03', 2] + [2 * t for t in totals])
    tab = workbook.create_sheet('COCINA 04')
    tab.append(['Producto', 'COCINA 04 - EDIFICIO TEST'])
    tab.append(['Precio'])
    tab.append([])
    high = False
    for name, group, pieces, module_totals in KITCHEN_MODULES:
        if group == 'high' and not high:
            tab.append(['MODULO ALTO'])
            high = True
        tab.append(['MODULO:', name, None, None, None] + [c[1] for c in KITCHEN_COLUMNS])
        tab.append(['PIEZAS', None, None, None, None, 'MATERIALES'])
        tab.append(['CANT.', 'LARGO', 'ANCHO', 'TIPO PIEZA', 'DESC.']
                   + [c[2] for c in KITCHEN_COLUMNS])
        for qty, length, width, kind, color, values in pieces:
            tab.append([qty, length, width, kind, color] + values)
        tab.append(['Total', None, None, None, None] + module_totals)
    workbook.create_sheet('codigos')
    output = BytesIO()
    workbook.save(output)
    return base64.b64encode(output.getvalue())


@tagged('post_install', '-at_install')
class TestProjectionImport(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env['product.product']
        cls.products = {}
        for _stage, _short, code, _sum, full in KITCHEN_COLUMNS:
            if code not in cls.products:
                cls.products[code] = Product.create({'name': full, 'default_code': code,
                                                     'type': 'consu'})
        cls.company.write({
            'construction_join_screw_product_ids': [(6, 0, cls.products['T18-T450'].ids)],
            'construction_join_dowel_product_ids': [(6, 0, cls.products['T18-TAR'].ids)]})
        cls.site = cls.env['project.project'].create({'name': 'Edificio Florece (test v18)',
                                                      'is_construction_site': True})

    def _wizard(self, data):
        return self.env['construction.projection.import.wizard'].create({
            'project_id': self.site.id, 'file': data, 'filename': 'PROYECTO COCINAS TEST.xlsx'})

    def test_kitchen_book_keeps_sheet_totals(self):
        """Criterio M17-18: la receta de cada módulo y mueble queda con los
        mismos totales por material que la hoja."""
        wizard = self._wizard(kitchen_workbook())
        wizard.action_preview()
        self.assertEqual(wizard.family, 'kitchen')
        self.assertFalse(wizard.unresolved_count)
        # Las dos columnas «tor 4*50» son distintas: armado e instalación.
        screws = wizard.line_ids.filtered(lambda l: l.name == 'tor 4*50')
        self.assertEqual(sorted(screws.mapped('stage')), ['assembly', 'installation'])
        wizard.action_import()
        typology = self.env['construction.typology'].search([('project_id', '=', self.site.id)])
        self.assertEqual(typology.code, 'COCINA 04')
        modules = typology.module_line_ids.sorted('sequence')
        self.assertEqual(modules.mapped('name'), ['MOD BAJO  665', 'MOD ALTO CAMPANA 605'])
        self.assertEqual(modules.mapped('ml_group'), ['low', 'high'])
        self.assertEqual(modules.mapped('width_mm'), [665, 605])
        self.assertEqual(modules[1].special_kind, 'hood')
        self.assertEqual(modules[0].join_method, 'mixed')
        self.assertEqual(len(modules[0].piece_ids), 2)
        self.assertEqual(typology.furniture_line_ids.mapped('furniture_kind'), ['low', 'high'])
        for index, (_stage, _short, code, _sum, _full) in enumerate(KITCHEN_COLUMNS):
            if index == 4:
                continue  # el mismo producto que la columna 2, en instalación
            sheet_total = sum(m[3][index] for m in KITCHEN_MODULES)
            if code == 'T18-T450':
                sheet_total += sum(m[3][4] for m in KITCHEN_MODULES)
            imported = sum(modules.material_ids.filtered(
                lambda m, c=code: m.product_id == self.products[c]).mapped('qty'))
            self.assertAlmostEqual(imported, sheet_total, places=4, msg=code)
        install = modules.material_ids.filtered(lambda m: m.stage == 'installation')
        self.assertAlmostEqual(sum(install.mapped('qty')), 7.0)
        spaces = self.env['project.task'].search([('project_id', '=', self.site.id),
                                                  ('construction_level', '=', 'space')])
        self.assertEqual(len(spaces), 2)
        self.assertEqual(set(spaces.construction_typology_id.ids), set(typology.ids))
        self.assertEqual(set(spaces.construction_apartment_task_id.mapped('name')),
                         {'DEP 304', 'DEP 305'})
        # Volver a importar no duplica.
        again = self._wizard(kitchen_workbook())
        again.action_preview()
        again.action_import()
        self.assertEqual(self.env['construction.typology'].search_count(
            [('project_id', '=', self.site.id)]), 1)
        self.assertEqual(len(typology.module_line_ids), 2)
        self.assertEqual(self.env['project.task'].search_count(
            [('project_id', '=', self.site.id), ('construction_level', '=', 'space')]), 2)

    def test_unknown_code_blocks_the_import(self):
        """Criterio M17-19: una hoja con un código inexistente en Odoo no se
        importa y lista la columna y el código; resuelta a mano, sí."""
        wizard = self._wizard(kitchen_workbook(summary_code_override='3101508'))
        wizard.action_preview()
        board = wizard.line_ids.filtered(lambda l: l.name == 'MELAMINA BLANCO')
        self.assertEqual(board.state, 'conflict')
        self.assertIn('3101508', board.note)
        self.assertEqual(wizard.unresolved_count, 1)
        with self.assertRaises(UserError) as error:
            wizard.action_import()
        self.assertIn('MELAMINA BLANCO', str(error.exception))
        board.action_accept()
        self.assertEqual(board.state, 'ok')
        wizard.action_import()
        self.assertTrue(self.env['construction.typology'].search(
            [('project_id', '=', self.site.id)]))
