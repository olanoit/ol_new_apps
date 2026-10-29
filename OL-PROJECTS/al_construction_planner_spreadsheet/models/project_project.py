# -*- coding: utf-8 -*-
"""Plantilla de la hoja de trabajo de presupuesto y plan (requerimiento CREVAL
v1.0, 6.7): las pestañas del libro de carga (6.6) con sus columnas, fórmulas
grises para los costos y listas vivas de Odoo en REFERENCIAS. Se abre desde
la cotización (carpeta Presupuestos › cotización de Documentos) o desde la
obra; la obra que viene de una cotización con hoja usa la misma."""
import json

from odoo import api, fields, models

from odoo.addons.al_construction_planner_sale.wizards.budget_book_wizard import (
    COLUMNS, PRESUPUESTO_FORMULAS,
)

SPREADSHEET_VERSION = '18.5.10'
HEADER_STYLE, TITLE_STYLE, CALC_STYLE, DATA_STYLE = 1, 2, 3, 4
DEFAULT_ROWS = 300
INSTRUCTIONS = [
    'Hoja de trabajo de presupuesto y plan (Planificación de obra)',
    '',
    'Encabezados amarillos: datos. Encabezados grises: fórmulas (no los escriba).',
    '1. OBRA: campo y valor (tipo de contrato, formato de impresión, gastos generales, '
    'imprevistos, utilidad y descuento en %).',
    '2. INSUMOS: un recurso por fila con código único, tipo de insumo, unidad y precio sin IGV. '
    '«Actualizar insumos» trae el costo vigente del maestro.',
    '3. APU y APU_DETALLE: la receta de cada partida tipo (cuadrilla ÷ rendimiento, % de la mano '
    'de obra o cantidad por unidad).',
    '4. PRESUPUESTO: las partidas de la obra con su APU, modalidad, metrado real, holguras y '
    'margen.',
    '5. PLAN: por partida, la modalidad final y las fechas (la oficina técnica).',
    '6. LISTAS: tipos de insumo, modalidades y la tabla de equivalencias de unidades.',
    '7. Menú Planificación de obra: Validar plantilla (errores en ERRORES), Enviar al '
    'planificador (presupuesto o presupuesto y plan), Actualizar insumos, Traer de Odoo y Nueva '
    'versión.',
]
# Columnas calculadas (gris) de cada pestaña: (encabezado, fórmula con {r} =
# fila y {c:clave} = letra de la columna de la pestaña).
CALCULATED = {
    'APU': [
        ('Costo unitario', '=IF({c:code}{r}="","",SUMIF(APU_DETALLE!$A$2:$A${n},{c:code}{r},'
                           'APU_DETALLE!{d:parcial}$2:{d:parcial}${n}))'),
    ],
    'APU_DETALLE': [
        ('Tipo (calc.)', '=IF({c:code}{r}="","",IFERROR(VLOOKUP({c:code}{r},INSUMOS!$A$2:$C${n},'
                         '3,0),""))'),
        ('Cantidad (calc.)', '=IF({c:apu}{r}="","",IF(AND({c:crew}{r}<>"",IFERROR(VLOOKUP('
                             '{c:apu}{r},APU!$A$2:$D${n},4,0),0)<>0),{c:crew}{r}*IF(IFERROR('
                             'VLOOKUP({c:apu}{r},APU!$A$2:$E${n},5,0),"")="",8,VLOOKUP({c:apu}{r},'
                             'APU!$A$2:$E${n},5,0))/VLOOKUP({c:apu}{r},APU!$A$2:$D${n},4,0),'
                             'N({c:qty}{r})))'),
        ('Precio (calc.)', '=IF({c:code}{r}="","",IF({c:price}{r}<>"",{c:price}{r},IFERROR('
                           'VLOOKUP({c:code}{r},INSUMOS!$A$2:$E${n},5,0),0)))'),
        ('Parcial MO (calc.)', '=IF(OR({x:Tipo (calc.)}{r}="Mano de obra",{x:Tipo (calc.)}{r}='
                               '"Subcontrato"),{x:Cantidad (calc.)}{r}*{x:Precio (calc.)}{r},0)'),
        ('Parcial (calc.)', '=IF({c:apu}{r}="","",IF(OR({c:pct}{r}<>"",{x:Tipo (calc.)}{r}='
                            '"Herramienta %MO"),N({c:pct}{r})/100*SUMIF($A$2:$A${n},{c:apu}{r},'
                            '{x:Parcial MO (calc.)}$2:{x:Parcial MO (calc.)}${n}),'
                            '{x:Cantidad (calc.)}{r}*{x:Precio (calc.)}{r}))'),
    ],
}
# PRESUPUESTO (CR-18, c): columnas A a W en el orden del libro 6.6; las
# fórmulas usan la letra de cada clave ({clave}) y los porcentajes van en %.
PRESUPUESTO_KEYS = [key for key, _aliases, _required in COLUMNS['PRESUPUESTO']]
PRESUPUESTO_HEADERS = [aliases[0] for _key, aliases, _required in COLUMNS['PRESUPUESTO']]
PRESUPUESTO_FORMULA_TEXT = {
    'qty_offered': '=IF({qty_real}{r}="","",{qty_real}{r}*(1+N({qty_slack_pct}{r})/100)'
                   '+N({qty_slack}{r}))',
    'unit_cost': '=IF({apu}{r}="",IF({cost_no_apu}{r}="","",{cost_no_apu}{r}),'
                 'IFERROR(VLOOKUP({apu}{r},APU!$A:${apu_unit},{apu_unit_index},0),0))',
    'cost_offered': '=IF({unit_cost}{r}="","",{unit_cost}{r}*(1+N({cost_slack_pct}{r})/100)'
                    '+N({cost_slack}{r}))',
    'price_unit': '=IF({cost_offered}{r}="","",{cost_offered}{r}*(1+N({margin_pct}{r})/100)'
                  '+N({margin}{r}))',
    'cost_real': '=IF(OR({qty_real}{r}="",{unit_cost}{r}=""),"",{qty_real}{r}*{unit_cost}{r})',
    'amount_offered': '=IF(OR({qty_offered}{r}="",{cost_offered}{r}=""),"",'
                      '{qty_offered}{r}*{cost_offered}{r})',
    'subtotal': '=IF(OR({qty_offered}{r}="",{price_unit}{r}=""),"",'
                '{qty_offered}{r}*{price_unit}{r})',
    'reserve': '=IF(OR({amount_offered}{r}="",{cost_real}{r}=""),"",'
               '{amount_offered}{r}-{cost_real}{r})',
}
# Unidad de la partida con APU: la del APU.
PRESUPUESTO_UOM_FORMULA = '=IFERROR(VLOOKUP({apu}{r},APU!$A:$C,3,0),"")'
# Porcentajes de OBRA desde la cotización (CR-18, d): rol de la línea → fila.
FOOTER_ROLES = [('overhead', 'Gastos generales %'), ('contingency', 'Imprevistos %'),
                ('profit', 'Utilidad %'), ('discount', 'Descuento %')]
PLAN_COLUMNS = ['Ítem', 'Partida', 'Modalidad final', 'Contratista sugerido', 'Inicio', 'Fin',
                'Frente o ambiente']
LISTS = {
    'Tipo de insumo': ['Material', 'Mano de obra', 'Equipo', 'Subcontrato', 'Herramienta %MO',
                       'Servicio'],
    'Modalidad': ['Personal propio', 'Contrata solo de mano de obra', 'Contrata a todo costo'],
    'Tipo de contrato': ['Suma alzada', 'Precios unitarios'],
    'Formato de impresión': ['Solo precios', 'Desglosado'],
}
OBRA_LABELS = ['Obra', 'Cliente', 'Moneda', 'Tipo de contrato', 'Formato de impresión',
               'Gastos generales %', 'Imprevistos %', 'Utilidad %', 'Descuento %', 'IGV %',
               'Fecha', 'Versión']


def _col(index):
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def cell_text(value):
    """Contenido de una celda como lo guarda o-spreadsheet: siempre texto
    (CR-18, a: un número guardado como número no abre la hoja)."""
    if value is None or value is False:
        return ''
    return value if isinstance(value, str) else str(value)


def presupuesto_formula(key, row):
    """Fórmula de la columna ``key`` de PRESUPUESTO en la fila ``row``."""
    letters = {k: _col(i) for i, k in enumerate(PRESUPUESTO_KEYS)}
    apu_headers = sheet_headers('APU')[0]
    text = PRESUPUESTO_FORMULA_TEXT[key] if key != 'uom' else PRESUPUESTO_UOM_FORMULA
    text = text.replace('{apu_unit_index}', str(len(apu_headers) + 1)).replace(
        '{apu_unit}', _col(len(apu_headers))).replace('{r}', str(row))
    for name, letter in letters.items():
        text = text.replace('{%s}' % name, letter)
    return text


def presupuesto_row(values, row):
    """Fila completa de PRESUPUESTO: los datos de ``values`` y las fórmulas
    grises; la unidad, con fórmula si hay APU."""
    result = []
    for key in PRESUPUESTO_KEYS:
        if key in PRESUPUESTO_FORMULAS:
            result.append(presupuesto_formula(key, row))
        elif key == 'uom' and values.get('apu'):
            result.append(presupuesto_formula('uom', row))
        else:
            result.append(cell_text(values.get(key)))
    return result


def sheet_headers(name):
    """Encabezados de datos y calculados de una pestaña del libro."""
    data = [aliases[0] for key, aliases, _required in COLUMNS[name]
            if not (name, key) in (('APU', 'unit_cost'), ('PRESUPUESTO', 'cost_real'))]
    return data, [header for header, _formula in CALCULATED.get(name, [])]


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_spreadsheet_rows = fields.Integer(
        string='Filas de la hoja de trabajo', default=DEFAULT_ROWS,
        help='Filas con listas y columnas calculadas por pestaña (ampliable antes de crear la '
             'hoja).')

    def _construction_spreadsheet_kind(self):
        """Presupuesto y plan; el puente de mobiliario cambia a su maestro."""
        self.ensure_one()
        return 'budget'

    def _construction_spreadsheet_template(self, kind):
        """(datos, nombre) de la hoja nueva de la obra."""
        self.ensure_one()
        order = self.construction_sale_order_id
        data = self._construction_budget_spreadsheet_data(order, self)
        return data, self.env._('Presupuesto y plan · %s', self.name)

    def action_construction_open_spreadsheet(self):
        """Abre la hoja de trabajo de la obra; la crea la primera vez. Si la
        obra viene de una cotización con hoja, es la misma."""
        self.ensure_one()
        kind = self._construction_spreadsheet_kind()
        Document = self.env['documents.document']
        document = Document.search([('construction_project_id', '=', self.id),
                                    ('construction_source_id', '=', False),
                                    ('handler', '=', 'spreadsheet')], limit=1)
        if not document and kind == 'budget' and self.construction_sale_order_id:
            document = Document.search([
                ('construction_sale_order_id', '=', self.construction_sale_order_id.id),
                ('construction_source_id', '=', False),
                ('handler', '=', 'spreadsheet')], limit=1)
            if document:
                document.construction_project_id = self
        if not document:
            data, name = self._construction_spreadsheet_template(kind)
            vals = {
                'name': name, 'mimetype': 'application/o-spreadsheet', 'handler': 'spreadsheet',
                'raw': json.dumps(data).encode(),
                'construction_project_id': self.id, 'construction_sheet_kind': kind,
                'construction_sale_order_id': self.construction_sale_order_id.id
                if kind == 'budget' else False,
            }
            folder = self['documents_folder_id'] if 'documents_folder_id' in self._fields \
                else False
            if folder:
                vals['folder_id'] = folder.id
            document = Document.create(vals)
        return document.action_open_spreadsheet()

    # ------------------------------------------------------------------
    # Plantilla de presupuesto y plan
    # ------------------------------------------------------------------
    @api.model
    def _construction_budget_rows(self, order, project):
        """Filas de datos de cada pestaña con lo que hay en Odoo: la
        cotización (OBRA y PRESUPUESTO) y las recetas de la obra (INSUMOS, APU
        y APU_DETALLE)."""
        rows = {name: [] for name in ('OBRA', 'INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO',
                                      'PLAN')}
        kinds = {'material': 'Material', 'labor': 'Mano de obra', 'equipment': 'Equipo',
                 'contract': 'Subcontrato', 'service': 'Servicio', 'production': 'Material'}
        modes = dict(zip(('own', 'labor_contract', 'full_contract'), LISTS['Modalidad']))
        if order:
            rows['OBRA'] = [
                ['Obra', (project or order.project_id).display_name or ''],
                ['Cliente', order.partner_id.display_name or ''],
                ['Moneda', order.currency_id.name],
                ['Tipo de contrato', dict(order._fields['construction_contract_type'].selection)
                 .get(order.construction_contract_type, '')],
                ['Formato de impresión', dict(order._fields['construction_print_format']
                                              .selection).get(order.construction_print_format,
                                                              '')],
            ]
        if order:
            rows['OBRA'] += self._construction_footer_pcts(order)
        Template = self.env['construction.execution.template']
        if project:
            recipes = Template.search([('project_id', '=', project.id)])
        else:
            # Cotización sin obra (D4): la biblioteca de la compañía y las
            # recetas que ya guardó la cotización (las de la cotización mandan).
            company = order.company_id if order else self.env.company
            own = order.construction_recipe_ids if order else Template
            recipes = own | Template.search([
                ('project_id', '=', False), ('construction_sale_order_id', '=', False),
                ('company_id', '=', company.id), ('code', 'not in', own.mapped('code'))])
        tasks = self.env['project.task']
        if order:
            tasks = tasks.search([('sale_line_id', 'in', order.order_line.ids)])
            recipes |= tasks.construction_execution_template_id
            recipes |= order.order_line.construction_execution_template_id.filtered(
                lambda r: not r.project_id or r.project_id == project)
        insumos = {}
        for recipe in recipes:
            rows['APU'].append([recipe.code, recipe.name, recipe.uom_id.name or '', '', '',
                                modes.get(recipe.execution_mode, '')])
            for line in recipe.line_ids:
                record = line.activity_id or line.product_id
                code = (line.product_id.default_code or line.activity_id.code or
                        'P-%s' % line.product_id.id) if record else ''
                if not code:
                    continue
                kind = 'Herramienta %MO' if line.calc_method == 'pct_labor' else \
                    kinds.get(line.resource_type, 'Material')
                insumos.setdefault(code, [code, record.display_name, kind,
                                          line.product_uom_id.name or '',
                                          line.price_unit or line._construction_default_cost(),
                                          (line.line_currency_id or recipe.currency_id).name])
                rows['APU_DETALLE'].append([
                    recipe.code, code,
                    line.crew_size if line.calc_method == 'crew' else '',
                    line.calc_pct if line.calc_method == 'pct_labor' else '',
                    line.qty if line.calc_method == 'qty' else '',
                    line.price_unit or '', line.stage or ''])
        rows['INSUMOS'] = list(insumos.values())
        if order:
            section = subsection = ''
            for line in order.order_line.sorted(lambda l: (l.sequence, l.id)):
                if line.display_type == 'line_section':
                    section, subsection = line.name, ''
                    continue
                if line.display_type == 'line_subsection':
                    subsection = line.name
                    continue
                if line.display_type or line.is_downpayment or \
                        line.construction_line_role != 'partida':
                    continue
                task = tasks.filtered(lambda t, l=line: t.sale_line_id == l)[:1]
                item = line.construction_budget_item or ''
                name = (line.name or '').splitlines()[0]
                if item and name.startswith(item):
                    name = name[len(item):].strip()
                apu = (task.construction_execution_template_id or
                       line.construction_execution_template_id).code or ''
                rows['PRESUPUESTO'].append({
                    'item': item, 'specialty': section, 'subspecialty': subsection,
                    'name': name, 'apu': apu,
                    # D1: sin receta, el costo de la línea (o su precio, si
                    # vino de otro sistema solo con precio por partida).
                    'cost_no_apu': '' if apu else (
                        line.construction_cost_apu or line.price_unit),
                    'uom': line.product_uom_id.name or '',
                    'mode': modes.get(task.construction_execution_mode, ''),
                    'qty_real': line.construction_qty_real or line.product_uom_qty,
                    'qty_slack_pct': line.construction_qty_slack_pct or '',
                    'qty_slack': line.construction_qty_slack or '',
                    'cost_slack_pct': line.construction_cost_slack_pct or '',
                    'cost_slack': line.construction_cost_slack or '',
                    'margin_pct': line.construction_margin_pct or '',
                    'margin': line.construction_margin_amount or ''})
                if task:
                    rows['PLAN'].append([item, name, modes.get(task.construction_execution_mode,
                                                               ''), '', '', '', ''])
        return rows

    @api.model
    def _construction_presupuesto_sheet(self, partidas, rows, last):
        """Pestaña PRESUPUESTO (CR-18, c): columnas A a W; amarillo los
        datos, gris las fórmulas, que llegan hasta la última fila."""
        cells, styles = {}, {}
        for i, (key, header) in enumerate(zip(PRESUPUESTO_KEYS, PRESUPUESTO_HEADERS)):
            cells['%s1' % _col(i)] = header
            styles['%s1' % _col(i)] = CALC_STYLE if key in PRESUPUESTO_FORMULAS else DATA_STYLE
        for number in range(2, rows + 2):
            index = number - 2
            values = partidas[index] if index < len(partidas) else {}
            for i, content in enumerate(presupuesto_row(values, number)):
                if content:
                    cells['%s%s' % (_col(i), number)] = content
        mode = _col(PRESUPUESTO_KEYS.index('mode'))
        return {
            'id': 'sheet_presupuesto', 'name': 'PRESUPUESTO',
            'colNumber': max(26, len(PRESUPUESTO_KEYS)), 'rowNumber': rows + 50,
            'cells': cells, 'styles': styles, 'panes': {'xSplit': 0, 'ySplit': 1},
            'cols': {str(i): {'size': max(110, 8 * len(header))}
                     for i, header in enumerate(PRESUPUESTO_HEADERS)},
            'dataValidationRules': [{
                'id': 'PRESUPUESTO_mode', 'isBlocking': False,
                'ranges': ['%s2:%s%s' % (mode, mode, last)],
                'criterion': {'type': 'isValueInList', 'displayStyle': 'arrow',
                              'values': LISTS['Modalidad']}}],
        }

    @api.model
    def _construction_footer_pcts(self, order):
        """Filas de OBRA con los % de gastos generales, imprevistos, utilidad
        y descuento de la cotización (CR-18, d), con 6 decimales (D2): los tres
        primeros sobre las partidas; el descuento, sobre partidas más ellos."""
        lines = order.order_line.filtered(lambda l: not l.display_type and not l.is_downpayment)
        partidas = sum(lines.filtered(
            lambda l: l.construction_line_role == 'partida').mapped('price_subtotal'))
        before_discount = partidas
        amounts = {}
        for role, _label in FOOTER_ROLES:
            amounts[role] = sum(lines.filtered(
                lambda l, r=role: l.construction_line_role == r).mapped('price_subtotal'))
            if role != 'discount':
                before_discount += amounts[role]
        result = []
        for role, label in FOOTER_ROLES:
            base = before_discount if role == 'discount' else partidas
            if not amounts[role] or not base:
                result.append([label, ''])
                continue
            pct = abs(amounts[role]) / base * 100.0
            result.append([label, round(pct, 6)])
        return result

    @api.model
    def _construction_budget_spreadsheet_data(self, order=None, project=None):
        """Datos de la hoja de presupuesto y plan, con lo que ya hay en Odoo."""
        values = self._construction_budget_rows(order, project)
        rows = max((project.construction_spreadsheet_rows if project else 0) or DEFAULT_ROWS,
                   max(len(v) for v in values.values()) + 100)
        last = rows + 1
        sheets = []
        sheets.append({
            'id': 'sheet_instrucciones', 'name': 'INSTRUCCIONES', 'colNumber': 4,
            'rowNumber': 40, 'cells': {'A%s' % (i + 1): text for i, text in
                                       enumerate(INSTRUCTIONS) if text},
            'styles': {'A1': TITLE_STYLE}, 'cols': {'0': {'size': 900}}})
        obra_cells, obra_styles = {}, {}
        given = {row[0]: row[1] for row in values['OBRA']}
        for index, label in enumerate(OBRA_LABELS, start=1):
            obra_cells['A%s' % index] = label
            obra_styles['A%s' % index] = HEADER_STYLE
            obra_styles['B%s' % index] = DATA_STYLE
            if given.get(label) not in (None, ''):
                obra_cells['B%s' % index] = cell_text(given[label])
        sheets.append({'id': 'sheet_obra', 'name': 'OBRA', 'colNumber': 4, 'rowNumber': 30,
                       'cells': obra_cells, 'styles': obra_styles,
                       'cols': {'0': {'size': 220}, '1': {'size': 260}}})
        letters_by_sheet = {}
        for name in ('INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO'):
            data_headers, calc_headers = sheet_headers(name)
            keys = [key for key, aliases, _required in COLUMNS[name]
                    if aliases[0] in data_headers]
            letters_by_sheet[name] = (
                {key: _col(i) for i, key in enumerate(keys)},
                {header: _col(len(data_headers) + i) for i, header in enumerate(calc_headers)})
        detail_calc = letters_by_sheet['APU_DETALLE'][1]
        apu_letters, apu_calc = letters_by_sheet['APU']
        unit_letter = apu_calc['Costo unitario']
        unit_index = len(sheet_headers('APU')[0]) + 1
        for position, name in enumerate(('INSUMOS', 'APU', 'APU_DETALLE'), 2):
            data_headers, calc_headers = sheet_headers(name)
            letters, calc_letters = letters_by_sheet[name]
            cells, styles = {}, {}
            for i, header in enumerate(data_headers + calc_headers):
                cells['%s1' % _col(i)] = header
                styles['%s1' % _col(i)] = DATA_STYLE if i < len(data_headers) else CALC_STYLE
            for number, row in enumerate(values[name], start=2):
                for i, value in enumerate(row[:len(data_headers)]):
                    if value not in (None, '', False):
                        cells['%s%s' % (_col(i), number)] = cell_text(value)
            for header, formula in CALCULATED.get(name, []):
                column = calc_letters[header]
                for number in range(2, rows + 2):
                    text = formula.replace('{r}', str(number)).replace('{n}', str(last))
                    for key, letter in letters.items():
                        text = text.replace('{c:%s}' % key, letter)
                    for calc_header, letter in calc_letters.items():
                        text = text.replace('{x:%s}' % calc_header, letter)
                    text = text.replace('{d:parcial}', detail_calc['Parcial (calc.)'])
                    text = text.replace('{a:unit}', unit_letter).replace(
                        '{a:unit_index}', str(unit_index))
                    cells['%s%s' % (column, number)] = text
            rules = []
            for key, list_name in (('kind', 'Tipo de insumo'), ('mode', 'Modalidad')):
                if key in letters:
                    rules.append({'id': '%s_%s' % (name, key), 'isBlocking': False,
                                  'ranges': ['%s2:%s%s' % (letters[key], letters[key], last)],
                                  'criterion': {'type': 'isValueInList', 'displayStyle': 'arrow',
                                                'values': LISTS[list_name]}})
            headers = data_headers + calc_headers
            sheets.append({
                'id': 'sheet_%s' % name.lower(), 'name': name,
                'colNumber': max(26, len(headers)), 'rowNumber': rows + 50,
                'cells': cells, 'styles': styles, 'panes': {'xSplit': 0, 'ySplit': 1},
                'cols': {str(i): {'size': max(110, 8 * len(header))}
                         for i, header in enumerate(headers)},
                'dataValidationRules': rules,
            })
        sheets.append(self._construction_presupuesto_sheet(values['PRESUPUESTO'], rows, last))
        plan_cells = {'%s1' % _col(i): header for i, header in enumerate(PLAN_COLUMNS)}
        for number, row in enumerate(values['PLAN'], start=2):
            for i, value in enumerate(row):
                if value not in (None, '', False):
                    plan_cells['%s%s' % (_col(i), number)] = cell_text(value)
        sheets.append({'id': 'sheet_plan', 'name': 'PLAN', 'colNumber': 10,
                       'rowNumber': rows + 50, 'cells': plan_cells,
                       'styles': {'%s1' % _col(i): DATA_STYLE for i in range(len(PLAN_COLUMNS))},
                       'panes': {'xSplit': 0, 'ySplit': 1},
                       'dataValidationRules': [{
                           'id': 'plan_mode', 'isBlocking': False,
                           'ranges': ['C2:C%s' % last],
                           'criterion': {'type': 'isValueInList', 'displayStyle': 'arrow',
                                         'values': LISTS['Modalidad']}}]})
        # LISTAS: valores válidos y la tabla de equivalencias de unidades.
        list_cells = {}
        for column, (title, items) in enumerate(LISTS.items()):
            list_cells['%s1' % _col(column * 2)] = title
            for number, item in enumerate(items, start=2):
                list_cells['%s%s' % (_col(column * 2), number)] = item
        alias_col = len(LISTS) * 2
        list_cells['%s1' % _col(alias_col)] = 'Escrito como'
        list_cells['%s1' % _col(alias_col + 1)] = 'Unidad'
        for number, alias in enumerate(self.env['construction.uom.alias'].search([]), start=2):
            list_cells['%s%s' % (_col(alias_col), number)] = alias.name
            list_cells['%s%s' % (_col(alias_col + 1), number)] = alias.uom_id.name
        sheets.append({'id': 'sheet_listas', 'name': 'LISTAS', 'colNumber': 12, 'rowNumber': 200,
                       'cells': list_cells,
                       'styles': {'%s1' % _col(i): HEADER_STYLE for i in range(alias_col + 2)}})
        # REFERENCIAS: listas vivas de Odoo.
        company = (project.company_id if project else False) or \
            (order.company_id if order else False) or self.env.company
        reference_lists = [
            ('1', 'Actividades', 'construction.labor.activity', ['code', 'name', 'uom_id'], 0,
             300, [['company_id', 'in', [company.id, False]]], 'code'),
            ('2', 'Unidades y equivalencias', 'construction.uom.alias', ['name', 'uom_id'], 4,
             200, [], 'name'),
            ('3', 'Contratistas', 'res.partner', ['name', 'vat'], 7, 300,
             [['supplier_rank', '>', 0]], 'name'),
            ('4', 'Productos', 'product.product',
             ['default_code', 'display_name', 'uom_id', 'standard_price'], 10, 2000,
             [['default_code', '!=', False], ['company_id', 'in', [company.id, False]]],
             'default_code'),
        ]
        ref_cells, ref_styles, lists = {}, {}, {}
        for list_id, title, model, columns, start, count, domain, order_by in reference_lists:
            ref_cells['%s1' % _col(start)] = title
            ref_styles['%s1' % _col(start)] = TITLE_STYLE
            for offset, field in enumerate(columns):
                col = _col(start + offset)
                ref_cells['%s2' % col] = '=ODOO.LIST.HEADER(%s,"%s")' % (list_id, field)
                ref_styles['%s2' % col] = HEADER_STYLE
                for row in range(1, count + 1):
                    ref_cells['%s%s' % (col, row + 2)] = '=ODOO.LIST(%s,%s,"%s")' % (
                        list_id, row, field)
            lists[list_id] = {'id': list_id, 'name': title, 'model': model, 'columns': columns,
                              'domain': domain, 'context': {},
                              'orderBy': [{'name': order_by, 'asc': True}], 'fieldMatching': {}}
        ref_cells['P1'] = 'Especialidades'
        ref_styles['P1'] = TITLE_STYLE
        stage_labels = [label for _code, label in self.env['construction.stage']._get_selection()]
        for number, label in enumerate(stage_labels, start=3):
            ref_cells['P%s' % number] = label
        sheets.append({'id': 'sheet_referencias', 'name': 'REFERENCIAS', 'colNumber': 26,
                       'rowNumber': 2010, 'cells': ref_cells, 'styles': ref_styles})
        sheets.append({'id': 'sheet_errores', 'name': 'ERRORES', 'colNumber': 6, 'rowNumber': 300,
                       'cells': {'A1': 'Hoja', 'B1': 'Fila', 'C1': 'Columna', 'D1': 'Mensaje'},
                       'styles': {'%s1' % c: HEADER_STYLE for c in 'ABCD'},
                       'cols': {'3': {'size': 700}}})
        settings = self.env['documents.document']._empty_spreadsheet_data().get('settings', {})
        return {
            'version': SPREADSHEET_VERSION, 'sheets': sheets,
            'styles': {str(HEADER_STYLE): {'bold': True, 'fillColor': '#DDE4EE'},
                       str(TITLE_STYLE): {'bold': True, 'fontSize': 12},
                       str(CALC_STYLE): {'bold': True, 'fillColor': '#D9D9D9'},
                       str(DATA_STYLE): {'bold': True, 'fillColor': '#FFF2CC'}},
            'settings': settings, 'lists': lists, 'listNextId': len(reference_lists) + 1,
            'pivots': {}, 'pivotNextId': 1, 'revisionId': 'START_REVISION',
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _construction_spreadsheet_folder(self):
        """Carpeta Presupuestos › <cotización> de Documentos."""
        self.ensure_one()
        Document = self.env['documents.document']
        root = Document.search([('type', '=', 'folder'), ('name', '=', 'Presupuestos'),
                                ('folder_id', '=', False)], limit=1) or Document.create(
            {'type': 'folder', 'name': 'Presupuestos'})
        return Document.search([('type', '=', 'folder'), ('name', '=', self.name),
                                ('folder_id', '=', root.id)], limit=1) or Document.create(
            {'type': 'folder', 'name': self.name, 'folder_id': root.id})

    def action_construction_open_spreadsheet(self):
        """«Hoja de trabajo» de la cotización: la crea en Presupuestos ›
        <cotización> con lo que ya tiene la cotización; después, la abre."""
        self.ensure_one()
        Document = self.env['documents.document']
        document = Document.search([('construction_sale_order_id', '=', self.id),
                                    ('construction_source_id', '=', False),
                                    ('handler', '=', 'spreadsheet')], limit=1)
        if not document:
            project = self.project_id
            data = self.env['project.project']._construction_budget_spreadsheet_data(
                self, project)
            document = Document.create({
                'name': self.env._('Presupuesto y plan · %s', self.name),
                'mimetype': 'application/o-spreadsheet', 'handler': 'spreadsheet',
                'raw': json.dumps(data).encode(),
                'folder_id': self._construction_spreadsheet_folder().id,
                'construction_sale_order_id': self.id,
                'construction_project_id': project.id,
                'construction_sheet_kind': 'budget',
            })
        return document.action_open_spreadsheet()
