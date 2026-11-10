# -*- coding: utf-8 -*-
"""Paquete 1.18, entrega 1: venta neta y margen (M118-01), ruta de INICIO y
envío con pendientes (M118-02) y contrato con la orden (M118-03). Datos
ficticios."""
from odoo.tests import TransactionCase, tagged

from .test_package_117_e3e import BringCommon


@tagged('post_install', '-at_install')
class TestPackage118Sheet(BringCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_bring()

    def _sheets(self):
        data = self.site._construction_spreadsheet_data(10)
        return {sheet['name']: sheet for sheet in data['sheets']}

    def test_start_shows_net_sale_and_margin(self):
        start = self._sheets()['INICIO']
        cells = start['cells']
        self.assertEqual(cells['C21'], 'De dónde sale')
        self.assertEqual(cells['A28'], 'Venta antes de descuento')
        self.assertEqual(cells['A29'], 'Descuento comercial')
        self.assertEqual(cells['A30'], 'Venta neta')
        self.assertEqual(cells['A31'], 'Margen estimado')
        self.assertIn('Costo de materiales estimado', cells['A26'])
        # Venta neta: VENTA × ambientes × factor, o el subtotal de la venta.
        self.assertIn('SUM(VENTA!', cells['B30'])
        self.assertIn('Subtotal de la cotización', cells['B30'])
        self.assertEqual(cells['B31'], '=IF(B30=0,"",B30-B26-B27)')
        self.assertIn('start_negative_margin',
                      [rule['id'] for rule in start['conditionalFormats']])

    def test_sale_and_typologies_have_the_factor(self):
        layout = self.site._construction_sheet_layout()
        self.assertIn('Factor (calc.)', layout['sheets']['VENTA']['calc_letters'])
        self.assertIn('Venta neta (calc.)', layout['sheets']['VENTA']['calc_letters'])
        self.assertIn('Factor (calc.)', layout['sheets']['TIPOLOGIAS']['calc_letters'])
        card = self._sheets()['FICHA']['cells']
        self.assertEqual(card['A20'], 'Precio neto por ambiente')
        factor = layout['sheets']['TIPOLOGIAS']['calc_letters']['Factor (calc.)']
        self.assertIn('TIPOLOGIAS!$%s:$%s' % (factor, factor), card['B20'])
        self.assertEqual(card['B21'], '=IF(IFERROR(VALUE(B20),0)=0,"",B20-B17)')

    def test_route_names_what_is_missing(self):
        cells = self._sheets()['INICIO']['cells']
        # Rendimientos antes de Programa por piso; Validar y enviar al final.
        self.assertIn('Rendimientos', cells['A17'])
        self.assertIn('Programa por piso', cells['A18'])
        self.assertIn('Validar y enviar', cells['A19'])
        # «Qué falta» con nombres y «Lo que falta» en una sola celda.
        self.assertIn('sin módulos', cells['E14'])
        self.assertIn('TAKE(FILTER(', cells['E14'])
        self.assertIn('sin tarifa', cells['E16'])
        for row in range(12, 20):
            self.assertIn('D%s' % row, cells['K%s' % row])
        self.assertIn('margen negativo', cells['K20'])
        self.assertIn('TEXTJOIN(CHAR(10),TRUE,K12:K20)', cells['F28'])
        self.assertIn('Nada: la hoja está lista para enviar', cells['F28'])

    def test_pending_send_is_logged(self):
        before = len(self.site.message_ids)
        self.assertTrue(self.document.construction_log_pending_send(
            ['3 · Muebles y módulos del ETO: C02A sin módulos']))
        self.assertEqual(len(self.site.message_ids), before + 1)
        self.assertIn('pasos pendientes', self.site.message_ids[0].body)
        self.assertFalse(self.document.construction_log_pending_send([]))

    def test_contract_marks_the_missing_template(self):
        layout = self.site._construction_sheet_layout()
        parts = self.site._construction_row_parts(layout, 2, 5)
        self.assertTrue(any('milestones' in cf['id'] for cf in parts['CONTRATOS']['conditional']))

    def test_contract_gets_the_order_and_milestones(self):
        """M118-03: el contrato del envío lleva la orden; con plantilla genera
        sus hitos y sin ella avisa; sin hitos, la obra toma la orden."""
        env = self.env
        typology = env['construction.typology'].create({
            'project_id': self.site.id, 'code': 'T118', 'name': 'Cocina T118 (test)'})
        wizard = env['construction.master.import.wizard'].create({'project_id': self.site.id})
        name = 'Venta 1.18 (test)'
        data = {
            'contracts': [{'name': name, 'partner': self.order.partner_id.name}],
            'milestones': [], 'prices': [{'contract': name, 'typology': 'T118', 'price': 1000}],
        }
        warnings = wizard._apply_contracts(data)
        contract = env['construction.contract'].search(
            [('project_id', '=', self.site.id), ('name', '=', name)])
        self.assertEqual(contract.sale_order_id, self.order)
        self.assertTrue(warnings)
        self.assertIn('sin plantilla de hitos', warnings[0])
        self.assertFalse(contract.milestone_ids)
        self.assertEqual(self.site.construction_income_planned,
                         self.order.amount_untaxed)
        self.assertTrue(typology)


@tagged('post_install', '-at_install')
class TestPackage118Lists(BringCommon, TransactionCase):
    """Paquete 1.18, entregas 2 y 3: MODULOS (M118-12) y listas «código ·
    nombre» (M118-08)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_bring()

    def test_modules_columns_and_lists(self):
        layout = self.site._construction_sheet_layout()
        modules = layout['sheets']['MODULOS']
        keys = [key for key, _header in modules['columns']]
        self.assertEqual(keys.index('eto_label'), keys.index('code') + 1)
        self.assertGreater(keys.index('module_class'), keys.index('join_method'))
        self.assertIn('Para elegir (calc.)', modules['calc_letters'])
        self.assertIn('Código de la actividad (calc.)',
                      layout['sheets']['TARIFAS']['calc_letters'])
        self.assertIn('Código del módulo (calc.)', layout['sheets']['BOM']['calc_letters'])
        data = self.site._construction_spreadsheet_data(10)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        self.assertEqual(sheets['REFERENCIAS']['cells']['E3'], '=IF(A3="","",A3&" · "&B3)')
        rules = [rule for rule in sheets['MODULOS'].get('dataValidationRules', [])
                 if 'REFERENCIAS!$E$3' in str(rule['criterion'].get('values'))]
        self.assertTrue(rules)

    def test_furniture_ml_from_modules(self):
        """M118-10: MUEBLES suma los anchos de sus módulos; los escritos
        mandan, y la matriz lee los ML usados."""
        layout = self.site._construction_sheet_layout()
        calc = layout['sheets']['MUEBLES']['calc_letters']
        self.assertIn('Metros lineales (calc.)', calc)
        self.assertIn('ML usados (calc.)', calc)
        data = self.site._construction_spreadsheet_data(10)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        used = 'MUEBLES!$%s:$%s' % (calc['ML usados (calc.)'], calc['ML usados (calc.)'])
        matrix = [sheet for name, sheet in sheets.items() if name.startswith('ACT ')]
        formulas = [cell for sheet in matrix for cell in sheet['cells'].values()
                    if isinstance(cell, str) and 'SUMIFS(' in cell and 'MUEBLES' in cell]
        if formulas:
            self.assertTrue(all(used in cell for cell in formulas))
        self.assertIn('B15-B23', sheets['FICHA']['cells']['C23'])

    def test_delivery5_start_summary_and_dates(self):
        """M118-07: módulos y personal propio en INICIO; M118-14: totales
        arriba en RESUMEN VENTA y fechas escritas como texto marcadas;
        M118-15: tipos de pieza del catálogo."""
        data = self.site._construction_spreadsheet_data(10)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        start = sheets['INICIO']['cells']
        self.assertEqual(start['D22'], 'Módulos (todos)')
        self.assertIn('SUMPRODUCT(', start['E22'])
        self.assertEqual(start['E23'], '=MAX(E22-B23,0)')
        self.assertIn('PROGRAMA', start['D25'])
        self.assertIn('program_date_text', [
            rule['id'] for rule in sheets['PROGRAMA']['conditionalFormats']])
        rules = [rule for rule in sheets['PIEZAS'].get('dataValidationRules', [])
                 if 'REFERENCIAS!$AK$3' in str(rule['criterion'].get('values'))]
        self.assertTrue(rules)
        self.assertTrue(self.env['construction.furniture.type'].search_count(
            [('level', '=', 'piece')]) >= 9)
        summary = self.order._construction_sale_sheet_data()
        resumen = next(sheet for sheet in summary['sheets'] if sheet['name'] == 'RESUMEN VENTA')
        self.assertEqual(resumen['cells']['A11'], 'Suma de partidas')
        self.assertEqual(resumen['cells']['A15'], 'Total')
        self.assertEqual(resumen['cells']['A17'], 'Producto')
        obra = next(sheet for sheet in summary['sheets'] if sheet['name'] == 'OBRA')
        self.assertTrue(any(mark['id'].startswith('obra_date_')
                            for mark in obra['conditionalFormats']))
