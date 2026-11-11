# -*- coding: utf-8 -*-
"""CREVAL, paquete 5, entrega 1: hoja de presupuesto de venta y hoja de
planificación de obra (CR-38), «Pasar a la cotización» y contrato de obra en
borrador al confirmar (CR-44), grupo «Presupuestador» y entradas (CR-47).
Datos ficticios."""
from odoo.exceptions import UserError
from odoo.addons.al_construction_planner_spreadsheet.models.project_project import _col
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_migration import (
    col_index as _col_index,
)
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.al_construction_planner_suite.tests.test_budget_book_creval import (
    TestBudgetBook,
)


@tagged('post_install', '-at_install')
class TestCrevalPackage5(TestBudgetBook):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.budgeter = new_test_user(
            cls.env, 'presupuesto_p5',
            groups='al_construction_planner_spreadsheet.group_construction_budgeter',
            name='Presupuestador (test)')

    def test_budgeter_opens_the_sale_sheet(self):
        order = self.order.with_user(self.budgeter)
        order.action_construction_open_budget_sheet()
        document = self.env['documents.document'].search(
            [('construction_sale_order_id', '=', self.order.id),
             ('construction_budget_role', '=', 'sale')])
        self.assertEqual(len(document), 1)
        self.assertTrue(document.name.startswith('Presupuesto de venta · %s' % self.order.name))
        # Pulsar dos veces abre la misma.
        order.action_construction_open_budget_sheet()
        self.assertEqual(self.env['documents.document'].search_count(
            [('construction_sale_order_id', '=', self.order.id),
             ('construction_budget_role', '=', 'sale')]), 1)
        metadata = document.with_user(self.budgeter)._get_spreadsheet_metadata()
        self.assertEqual(metadata['construction_budget_role'], 'sale')
        # La hoja de venta no envía el plan.
        with self.assertRaises(UserError):
            document.action_construction_send_to_planner({}, 'plan')

    def test_plan_sheet_is_another_document(self):
        self.order.action_construction_open_budget_sheet()
        self.project.construction_sale_order_id = self.order
        self.project.action_construction_open_plan_sheet()
        plan = self.env['documents.document'].search(
            [('construction_project_id', '=', self.project.id),
             ('construction_budget_role', '=', 'plan')])
        self.assertEqual(len(plan), 1)
        self.assertTrue(plan.name.startswith('Planificación de obra'))
        with self.assertRaises(UserError):
            plan.action_construction_send_to_planner({}, 'budget')

    def test_budgeter_passes_the_budget(self):
        wizard = self.env['construction.budget.book.wizard'].with_user(self.budgeter).create({
            'sale_order_id': self.order.id, 'target': 'budget', 'file': self._book(),
            'filename': 'libro.xlsx'})
        wizard.action_import()
        lines = self.order.order_line.filtered(
            lambda l: not l.display_type and l.construction_line_role == 'partida')
        self.assertEqual(len(lines), 2)
        self.assertEqual(self.order.state, 'draft')
        self.assertFalse(self.env['construction.resource.plan'].search(
            [('project_id', '=', self.project.id)]))

    def test_confirm_creates_a_draft_contract(self):
        self._send(self._book()).action_import()
        self.order.action_confirm()
        contracts = self.env['construction.contract'].search([('project_id', '=', self.project.id)])
        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts.state, 'draft')
        self.assertEqual(contracts.sale_order_id, self.order)

    # ------------------------------------------------------------------
    # Entrega 2: CR-39, CR-40 y CR-41
    # ------------------------------------------------------------------
    def _sheets(self):
        data = self.env['project.project']._construction_budget_spreadsheet_data(
            self.order, self.project)
        return data, {sheet['name']: sheet for sheet in data['sheets']}

    def test_start_first_and_hidden_lists(self):
        data, sheets = self._sheets()
        self.assertEqual(data['sheets'][0]['name'], 'INICIO')
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertLess(names.index('OBRA'), names.index('PRESUPUESTO'))
        self.assertLess(names.index('PRESUPUESTO'), names.index('APU'))
        for name in ('LISTAS', 'REFERENCIAS', '_CLAVES'):
            self.assertFalse(sheets[name].get('isVisible', True), name)
        start = sheets['INICIO']['cells']
        self.assertEqual(start['A9'], '1 · OBRA')
        self.assertIn('◀ Siguiente', start['E10'])
        self.assertIn('SUM(PRESUPUESTO!', start['B19'])

    def test_obra_gets_the_company_parameters(self):
        self.env.company.write({'construction_budget_overhead_pct': 8.0,
                                'construction_budget_profit_pct': 7.0,
                                'construction_budget_margin_pct': 10.0})
        _data, sheets = self._sheets()
        obra = sheets['OBRA']['cells']
        values = {obra['A%s' % row]: obra.get('B%s' % row) for row in range(1, 14)
                  if obra.get('A%s' % row)}
        self.assertEqual(values['Gastos generales %'], '8.0')
        self.assertEqual(values['Utilidad %'], '7.0')
        self.assertEqual(values['Margen por defecto %'], '10.0')
        self.assertTrue(values['Obra'])
        self.assertTrue(values['Fecha'])

    def test_budget_rows_have_state_and_titles(self):
        _data, sheets = self._sheets()
        presupuesto = sheets['PRESUPUESTO']
        from odoo.addons.al_construction_planner_spreadsheet.models.project_project import (
            presupuesto_letters,
        )
        state = presupuesto_letters()['state']
        self.assertEqual(presupuesto['cells']['%s1' % state], 'Estado')
        self.assertIn('Falta APU o costo', presupuesto['cells']['%s2' % state])
        self.assertIn('PRESUPUESTO_title', [cf['id'] for cf in presupuesto['conditionalFormats']])
        self.assertEqual(presupuesto['panes']['xSplit'], 2)

    def test_presupuesto_in_the_budgeter_order(self):
        """Pendiente de la entrega 2 (CR-41): plantilla 3, con el APU por
        nombre, Especialidad y Sub-especialidad calculadas y las holguras en
        un grupo plegado."""
        from odoo.addons.al_construction_planner_spreadsheet.models.project_project import (
            BUDGET_LAYOUT, presupuesto_letters,
        )
        from odoo.addons.al_construction_planner_spreadsheet.models.sheet_keys import KEYS_SHEET
        self.assertGreaterEqual(BUDGET_LAYOUT, 3)
        self._send(self._book()).action_import()
        _data, sheets = self._sheets()
        presupuesto = sheets['PRESUPUESTO']
        cells = presupuesto['cells']
        self.assertEqual([cells['%s1' % c] for c in 'ABCDEFGHIJK'], [
            'Ítem', 'Partida', 'Und', 'Metrado', 'APU (escriba el nombre)', 'Costo sin APU',
            'Costo unitario', 'Precio unitario', 'Parcial', 'Estado', 'Especialidad'])
        p = presupuesto_letters()
        # Lo que trae la cotización: el APU por nombre y su código calculado.
        self.assertTrue(cells['%s2' % p['apu_pick']].endswith(' · BK-R01'))
        self.assertIn(p['apu_pick'] + '2', cells['%s2' % p['apu']])
        self.assertIn('XLOOKUP', cells['%s2' % p['specialty']])
        self.assertIn('XLOOKUP', cells['%s2' % p['subspecialty']])
        group = presupuesto['headerGroups']['COL'][0]
        self.assertTrue(group['isFolded'])
        self.assertEqual(_col_index(p['subspecialty']), group['start'])
        self.assertIn('PRESUPUESTO_apu_pick', [
            rule['id'] for rule in presupuesto['dataValidationRules']])
        # _CLAVES: el código del APU se lee de su columna calculada; Estado y
        # el nombre del APU no se envían.
        keys = sheets[KEYS_SHEET]['cells']
        refs = {keys.get('B%s' % n): keys.get('C%s' % n) for n in range(2, 200)
                if keys.get('A%s' % n) == 'PRESUPUESTO'}
        self.assertEqual(refs['apu'], '=COLUMN(PRESUPUESTO!%s1)' % p['apu'])
        self.assertNotIn('apu_pick', refs)
        self.assertNotIn('state', refs)

    def test_sheet_in_the_budgeter_order_passes(self):
        """La hoja de venta con los encabezados cortos y la especialidad
        calculada llega a la cotización como el libro de siempre."""
        def budgeter_order(book):
            sheet = book['PRESUPUESTO']
            sheet.delete_rows(1, sheet.max_row)
            sheet.append(['Ítem', 'Partida', 'Und', 'Metrado', 'APU (escriba el nombre)',
                          'Costo sin APU', 'Costo unitario', 'Precio unitario', 'Parcial',
                          'Estado', 'Especialidad', 'Sub-especialidad',
                          'Código del APU (calc.)'])
            sheet.append(['01', 'Arquitectura', None, None, None, None, None, None, None,
                          'Título', None, None, None])
            sheet.append(['01.01', 'Muros', None, None, None, None, None, None, None,
                          'Título', 'Arquitectura', None, None])
            for item, name, qty in (('01.0101', 'Muro del eje A', 100),
                                    ('01.0102', 'Muro del eje B', 50)):
                sheet.append([item, name, 'm2', qty, 'Muro (test) · BK-R01', None, None, None,
                              None, 'OK', 'Arquitectura', 'Muros', 'BK-R01'])
        self._send(self._edited_book(budgeter_order)).action_import()
        lines = self.order.order_line.filtered(
            lambda l: not l.display_type and l.construction_line_role == 'partida')
        self.assertEqual(sorted(lines.mapped('construction_budget_item')),
                         ['01.0101', '01.0102'])
        self.assertEqual(set(lines.mapped('construction_execution_template_id.code')),
                         {'BK-R01'})
        self.assertEqual(lines.mapped('construction_qty_real'), [100.0, 50.0])
        sections = self.order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertIn('Arquitectura', sections.mapped('name'))

    def test_old_sheet_is_upgraded_to_the_sale_sheet(self):
        """Pendiente de la entrega 1 (CR-38, punto 4): «Actualizar a la
        plantilla vigente» rehace la hoja «Presupuesto y plan» como hoja de
        venta, con lo escrito en ella; la Especialidad escrita en cada fila
        pasa a filas de título."""
        import base64
        import json
        from io import BytesIO

        from openpyxl import load_workbook

        book = load_workbook(BytesIO(base64.b64decode(self._book())))
        sheets = {name: [['' if value is None else value for value in row]
                         for row in book[name].iter_rows(values_only=True)]
                  for name in book.sheetnames}
        data = self.env['project.project']._construction_budget_spreadsheet_data(
            self.order, self.project)
        old = self.env['documents.document'].create({
            'name': 'Presupuesto y plan (test)', 'mimetype': 'application/o-spreadsheet',
            'handler': 'spreadsheet', 'datas': base64.b64encode(json.dumps(data).encode()),
            'construction_sale_order_id': self.order.id,
            'construction_project_id': self.project.id, 'construction_sheet_kind': 'budget',
            'construction_sheet_layout': 0})
        old.construction_budget_upgrade(sheets)
        self.assertEqual(old.construction_budget_role, 'sale')
        self.assertEqual(old.construction_sheet_layout, 4)
        self.assertTrue(old.name.startswith('Presupuesto de venta · %s' % self.order.name))
        self.assertEqual(self.env['documents.document'].search_count(
            [('construction_source_id', '=', old.id)]), 1, 'versión anterior guardada')
        sheets = {sheet['name']: sheet for sheet in json.loads(old.spreadsheet_data)['sheets']}
        cells = sheets['PRESUPUESTO']['cells']
        column = lambda letter: [cells.get('%s%s' % (letter, n)) for n in range(2, 7)]  # noqa
        self.assertEqual(column('A'), ['01', '01.01', '01.02', None, None])
        self.assertEqual(column('B')[:2], ['Arquitectura', 'Muro del eje A'])
        self.assertEqual(column('E')[1], 'Muro de ladrillo KK (test) · BK-R01')
        # «01.01» ya es la partida: su Sub-especialidad no tiene título propio
        # (el ítem solo tiene dos niveles), así que no se inventa una fila.
        detail = sheets['APU_DETALLE']['cells']
        self.assertEqual(detail['A2'], 'Muro de ladrillo KK (test) · BK-R01')
        self.assertTrue(detail['B2'].endswith(' · BK-OPE'))
        self.assertEqual(sheets['OBRA']['cells']['B1'], 'OBR-03')
        with self.assertRaises(UserError):
            old.construction_budget_upgrade(sheets)

    def _plan_sheet(self):
        self._send(self._book()).action_import()
        self.project.construction_sale_order_id = self.order
        self.project.action_construction_open_plan_sheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.project.id),
             ('construction_budget_role', '=', 'plan')])

    def test_plan_bring_compares_only_the_sold_columns(self):
        """Pendiente de la entrega 4 (CR-45, punto 2): «Traer la venta» con
        vista previa: PLAN compara por ítem solo ítem y partida; los APU de
        obra se comparan por su código y lo vendido llega a PRESUPUESTO."""
        plan = self._plan_sheet()
        data = plan.construction_plan_bring()
        self.assertEqual(data['tabs']['PLAN']['keys'], ['item', 'name'])
        self.assertEqual(data['tabs']['PLAN']['rows'],
                         [['01.01', 'Muro del eje A'], ['01.02', 'Muro del eje B']])
        self.assertFalse(data['tabs']['PLAN']['keep_extra'])
        # La vista previa de PLAN es una tabla por partida con lo vendido.
        self.assertEqual(data['tabs']['PLAN']['table'],
                         ['Ítem', 'Partida', 'Metrado vendido', 'APU'])
        qty, apu = data['tabs']['PLAN']['info'][0]
        self.assertTrue(qty.startswith('100'), qty)
        self.assertEqual(apu, 'Muro de ladrillo KK (test) · BK-R01')
        self.assertEqual(data['tabs']['APU']['match'], ['code'])
        self.assertIn(['BK-R01'], [[row[data['tabs']['APU']['keys'].index('code')]]
                                   for row in data['tabs']['APU']['rows']])
        self.assertEqual(data['tabs']['APU_DETALLE']['keys'][0], 'apu_pick')
        self.assertTrue(data['tabs']['APU_DETALLE']['keep_extra'])
        self.assertEqual(data['from_top']['PRESUPUESTO'][0][4], 'APU (escriba el nombre)')
        # La hoja de venta no trae la venta (la tiene).
        sale = self.env['documents.document'].search(
            [('construction_sale_order_id', '=', self.order.id),
             ('construction_budget_role', '=', 'sale')])
        if sale:
            with self.assertRaises(UserError):
                sale.construction_plan_bring()

    def test_plan_date_outside_the_obra(self):
        """Pendiente de la entrega 4 (CR-45, punto 3): OBRA lleva el plazo de
        la obra y PLAN avisa «Fecha fuera de la obra»."""
        self.project.write({'date_start': '2026-11-01', 'date': '2026-12-31'})
        _data, sheets = self._sheets()
        obra = sheets['OBRA']['cells']
        self.assertEqual((obra['A14'], obra['B14']), ('Inicio de la obra', '2026-11-01'))
        self.assertEqual((obra['A15'], obra['B15']), ('Fin de la obra', '2026-12-31'))
        plan = sheets['PLAN']['cells']
        state = next(letter for letter in 'HIJKLMN' if plan.get('%s1' % letter) == 'Estado (calc.)')
        formula = plan['%s2' % state]
        self.assertIn('"Fecha fuera de la obra"', formula)
        self.assertIn('OBRA!$B$14', formula)
        self.assertIn('OBRA!$B$15', formula)
        self.assertEqual(formula.count('('), formula.replace('"+0.0%;-0.0%"', '').count(')'))

    def test_default_margin_when_the_row_has_none(self):
        def margin(book):
            book['OBRA'].append(('Margen por defecto %', 10))
        wizard = self._send(self._edited_book(margin))
        wizard.action_import()
        line = self.order.order_line.filtered(lambda l: l.construction_budget_item == '01.02')
        self.assertAlmostEqual(line.construction_margin_pct, 10.0)

    # ------------------------------------------------------------------
    # Entrega 3: CR-42, CR-43 y el pie de CR-44
    # ------------------------------------------------------------------
    def test_apu_and_insumos_have_state(self):
        _data, sheets = self._sheets()
        apu = sheets['APU']['cells']
        insumos = sheets['INSUMOS']['cells']
        headers = lambda cells: [value for ref, value in cells.items()  # noqa: E731
                                 if ref.endswith('1') and not ref[-2].isdigit()]
        for header in ('Usado en (calc.)', 'Estado (calc.)', 'Código propuesto (calc.)'):
            self.assertIn(header, headers(apu))
        for header in ('Usado en (calc.)', 'Estado (calc.)'):
            self.assertIn(header, headers(insumos))
        state = next(value for ref, value in insumos.items()
                     if ref[-1] == '2' and not ref[-2].isdigit() and 'Producto nuevo sin precio'
                     in str(value))
        self.assertIn('Precio de más de 90 días', state)
        self.assertIn('Total del APU (calc.)', headers(sheets['APU_DETALLE']['cells']))

    def test_footer_sheet(self):
        data, sheets = self._sheets()
        footer = sheets['PIE DE PRESUPUESTO']['cells']
        self.assertEqual(footer['A11'], 'Total')
        self.assertEqual(footer['B9'], '=B7+B8')
        self.assertIn('SUM(PRESUPUESTO!', footer['B3'])
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertEqual(names.index('PIE DE PRESUPUESTO'), names.index('INSUMOS') + 1)

    def test_apu_without_code_gets_the_next_one(self):
        def new_apu(book):
            book['APU'].append([None, 'Salida de termostato (test)', 'und', 10, 8,
                                'Personal propio', 'book_test_stage'])
        wizard = self.env['construction.budget.book.wizard'].create({
            'sale_order_id': self.order.id, 'target': 'budget',
            'file': self._edited_book(new_apu), 'filename': 'libro.xlsx'})
        book, _errors, _warnings = wizard._parse()
        self.assertIn('R01', book['apus'])
        self.assertEqual(book['apus']['R01']['name'], 'Salida de termostato (test)')

    # ------------------------------------------------------------------
    # Entrega 4: CR-45 y CR-46
    # ------------------------------------------------------------------
    def test_plan_uses_the_site_quantity(self):
        def site(book):
            sheet = book['PLAN']
            sheet.cell(row=1, column=7, value='Metrado de obra')
            sheet.cell(row=2, column=7, value=55)
        wizard = self._send(self._edited_book(site), target='plan')
        wizard.action_import()
        line = self.order.order_line.filtered(lambda l: l.construction_budget_item == '01.02')
        self.assertAlmostEqual(line.construction_qty_real, 50.0)
        plan = self.env['construction.resource.plan'].search([('project_id', '=', self.project.id)])
        self.assertIn(55.0, plan.line_ids.task_id.mapped('construction_qty'))

    def test_plan_and_control_tabs(self):
        self._send(self._book()).action_import()
        _data, sheets = self._sheets()
        plan = sheets['PLAN']['cells']
        headers = [plan.get('%s1' % chr(65 + i)) for i in range(14)]
        for header in ('Metrado vendido (calc.)', 'Metrado de obra', 'Estado (calc.)'):
            self.assertIn(header, headers)
        self.assertEqual(plan['A2'], '01.01')
        control = sheets['CONTROL']['cells']
        self.assertEqual(control['G2'], 'Estado')
        self.assertIn('Supera el umbral', control['G3'])
        self.assertEqual(control['L2'], '0.05')
        self.assertIn('$L$2', control['G3'])
        # CR-46, punto 3: el plan de Odoo, que escribe «Actualizar CONTROL».
        self.assertEqual(control['H2'], 'Costo en el plan de Odoo')
        self.assertEqual(control['I3'], '=IF(OR($A3="",H3=""),"",D3-H3)')

    # ------------------------------------------------------------------
    # Pendientes del 11-nov: CR-43, CR-45 punto 4 y CR-46 punto 3
    # ------------------------------------------------------------------
    def test_insumo_is_picked_from_the_product_master(self):
        """CR-43: INSUMOS elige el producto del maestro por su nombre; la
        lista va en LISTAS con su tipo, unidad, código y precio vigente."""
        from odoo.addons.al_construction_planner_spreadsheet.models.project_project import (
            PRODUCT_LIST,
        )
        self.env['product.product'].create({
            'name': 'Tubo PVC SEL 3/4" (test)', 'default_code': 'BK-TUB',
            'standard_price': 3.5})
        self._send(self._book()).action_import()
        _data, sheets = self._sheets()
        lists = sheets['LISTAS']['cells']
        start = next(ref[:-1] for ref, value in lists.items()
                     if ref.endswith('1') and not ref[-2].isdigit()
                     and value == 'Producto (nombre · código)')
        index = _col_index(start)
        headers = [lists.get('%s1' % _col(index + i)) for i in range(len(PRODUCT_LIST))]
        self.assertEqual(headers, [header for _key, header in PRODUCT_LIST])
        row = next(n for n in range(2, 6000)
                   if lists.get('%s%s' % (start, n)) == 'Tubo PVC SEL 3/4" (test) · BK-TUB')
        values = [lists.get('%s%s' % (_col(index + i), row)) for i in range(len(PRODUCT_LIST))]
        self.assertEqual((values[2], values[3], values[5]), ('BK-TUB', 'Material', '3.5'))
        self.assertEqual(values[8], 'Maestro de productos')
        # El ladrillo del APU es Material y está en la lista.
        self.assertTrue(any(value == 'Ladrillo KK 18 huecos (test) · BK-LAD'
                            for value in lists.values()))
        insumos = sheets['INSUMOS']
        self.assertEqual(insumos['cells']['A1'], 'Producto (escriba el nombre)')
        rule = next(rule for rule in insumos['dataValidationRules']
                    if rule['id'] == 'INSUMOS_product_pick')
        self.assertFalse(rule['isBlocking'])
        self.assertEqual(rule['criterion']['values'], ['LISTAS!$%s$2:$%s$5000' % (start, start)])
        # Lo que ya está en Odoo llega con el producto elegido.
        self.assertIn('Ladrillo KK 18 huecos (test) · BK-LAD',
                      [value for ref, value in insumos['cells'].items() if ref[0] == 'A'])

    def test_bring_from_odoo_renews_the_products(self):
        """CR-43: «Traer de Odoo» trae la lista de productos; el envío no
        lleva esa lista (solo las listas y las unidades de LISTAS)."""
        from io import BytesIO

        from openpyxl import load_workbook
        plan = self._plan_sheet()
        data = plan.construction_odoo_rows()
        self.assertEqual(data['_products']['headers'][0], 'Producto (nombre · código)')
        self.assertIn('Ladrillo KK 18 huecos (test) · BK-LAD',
                      [row[0] for row in data['_products']['rows']])
        self.assertCountEqual(data['_keyed']['APU_DETALLE']['calculated'], ['apu', 'code'])
        self.assertEqual(data['_keyed']['INSUMOS']['calculated'], [])
        self.assertEqual(data['_keyed']['INSUMOS']['keys'][-1], 'product_pick')
        row = ['Tipo de insumo', '', 'Modalidad', '', 'Tipo de contrato', '',
               'Formato de impresión', '', 'Escrito como', 'Unidad', '',
               'Producto (nombre · código)', 'Nombre', 'Código']
        book = load_workbook(BytesIO(plan._construction_book({'LISTAS': [row, [''] * 14]})))
        self.assertEqual(book['LISTAS'].max_column, 10)
        self.assertEqual(book['LISTAS'].max_row, 1)

    def _site_plan(self, edit=None):
        """Envía el plan desde la hoja de planificación de obra (CR-45,
        punto 4): el asistente con ``site_plan``."""
        wizard = self.env['construction.budget.book.wizard'].create({
            'sale_order_id': self.order.id, 'target': 'plan', 'site_plan': True,
            'file': self._edited_book(edit) if edit else self._book(),
            'filename': 'planificación.xlsx'})
        wizard.action_preview()
        wizard.action_import()
        return wizard

    def test_site_plan_keeps_the_sold_apu(self):
        """CR-45, punto 4: los APU de la hoja de planificación son los de la
        obra; cambiar la cuadrilla no toca la venta (la partida queda con una
        copia del APU vendido) y el plan usa el APU de obra."""
        plan_sheet = self._plan_sheet()
        self.assertEqual(plan_sheet._construction_book_wizard(
            {'OBRA': [['Obra', 'OBR-03']]}, 'plan').site_plan, True)
        line = self.order.order_line.filtered(lambda l: l.construction_budget_item == '01.02')
        cost, price = line.construction_cost_apu, line.price_unit
        sold = line.construction_execution_template_id
        self.assertEqual(sold.project_id, self.project)
        crew = sold.line_ids.filtered('activity_id').crew_size

        def two_workers(book):
            book['APU_DETALLE'].cell(row=2, column=3, value=crew * 2)
        wizard = self._site_plan(two_workers)
        self.assertIn('sin cambios', wizard.preview_html)
        kept = line.construction_execution_template_id
        self.assertNotEqual(kept, sold)
        self.assertEqual((kept.code, kept.construction_sale_order_id, kept.project_id),
                         ('BK-R01', self.order, self.env['project.project']))
        self.assertEqual(kept.line_ids.filtered('activity_id').crew_size, crew)
        self.assertEqual(sold.line_ids.filtered('activity_id').crew_size, crew * 2)
        self.assertEqual((line.construction_cost_apu, line.price_unit), (cost, price))
        task = self.env['project.task'].search([('sale_line_id', '=', line.id)])
        self.assertEqual(task.construction_execution_template_id, sold)
        plan = self.env['construction.resource.plan'].search(
            [('project_id', '=', self.project.id)])
        self.assertTrue(plan.line_ids.filtered(lambda l: l.task_id == task))
        # Un segundo envío no vuelve a copiar.
        self._site_plan(two_workers)
        self.assertEqual(line.construction_execution_template_id, kept)
        Template = self.env['construction.execution.template']
        self.assertEqual(Template.search_count([('code', '=', 'BK-R01'),
                                                ('construction_sale_order_id', '=',
                                                 self.order.id)]), 1)
        # La hoja de venta trae el APU vendido; la de planificación, el de obra.
        Project = self.env['project.project']
        sold_rows = Project._construction_budget_rows(self.order, self.project)
        site_rows = Project._construction_budget_rows(self.order, self.project, sold=False)
        # Horas del operario por unidad: con el doble de cuadrilla, el doble.
        hours = lambda rows: [row[4] for row in rows['APU_DETALLE']  # noqa: E731
                              if row[0] == 'BK-R01' and row[7] == 'BK-OPE']
        self.assertEqual(len(hours(sold_rows)), 1)
        self.assertAlmostEqual(hours(site_rows)[0], hours(sold_rows)[0] * 2, places=5)

    def test_control_compares_with_the_odoo_plan(self):
        """CR-46, punto 3: después del envío, CONTROL compara con el plan de
        Odoo: el costo planificado de cada partida, por su ítem."""
        plan_sheet = self._plan_sheet()
        empty = plan_sheet.construction_plan_control()
        self.assertEqual(empty['items'], {})
        self._site_plan()
        data = plan_sheet.construction_plan_control()
        plan = self.env['construction.resource.plan'].search(
            [('project_id', '=', self.project.id)], order='id desc', limit=1)
        self.assertEqual(data['plan'], plan.display_name)
        self.assertEqual(set(data['items']), {'01.01', '01.02'})
        task = self.env['project.task'].search([
            ('sale_line_id.construction_budget_item', '=', '01.02'),
            ('project_id', '=', self.project.id)])
        expected = sum(plan.line_ids.filtered(
            lambda l: l.task_id == task or l.task_id.parent_id == task).mapped('amount_planned'))
        self.assertAlmostEqual(data['items']['01.02'], expected, places=2)
        self.assertTrue(plan_sheet.construction_control_date)
        sale = self.env['documents.document'].search(
            [('construction_sale_order_id', '=', self.order.id),
             ('construction_budget_role', '=', 'sale')], limit=1)
        if sale:
            with self.assertRaises(UserError):
                sale.construction_plan_control()


@tagged('post_install', '-at_install')
class TestCrevalPackage5PlanBringTour(TestBudgetBook, HttpCase):

    def test_plan_bring_keeps_what_the_planner_wrote(self):
        """CR-45, punto 2, en el navegador: vista previa, huella y la partida
        editada a mano desmarcada. Pendientes del 11-nov: el producto elegido
        por nombre llena la fila de INSUMOS (CR-43) y CONTROL se compara con el
        plan de Odoo (CR-46, punto 3)."""
        self.env['product.product'].create({
            'name': 'Tubo PVC SEL 3/4" (test)', 'default_code': 'BK-TUB',
            'standard_price': 3.5})
        self._send(self._book()).action_import()
        self.project.construction_sale_order_id = self.order
        self.project.action_construction_open_plan_sheet()
        plan = self.env['documents.document'].search(
            [('construction_project_id', '=', self.project.id),
             ('construction_budget_role', '=', 'plan')])
        plan.name = 'Planificación de obra (traer la venta, test)'
        # El admin de la base de pruebas trabaja en otra compañía.
        admin = self.env.ref('base.user_admin')
        admin.write({'company_ids': [(4, self.order.company_id.id)],
                     'company_id': self.order.company_id.id})
        wizard = self.env['construction.budget.book.wizard'].create({
            'sale_order_id': self.order.id, 'target': 'plan', 'site_plan': True,
            'file': self._book(), 'filename': 'planificación.xlsx'})
        wizard.action_preview()
        wizard.action_import()
        self.start_tour('/odoo', 'al_construction_plan_bring', login='admin')
