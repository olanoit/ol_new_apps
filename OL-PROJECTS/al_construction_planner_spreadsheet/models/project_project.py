# -*- coding: utf-8 -*-
"""Plantilla de la hoja de trabajo de presupuesto y plan (requerimiento CREVAL
v1.0, 6.7): las pestañas del libro de carga (6.6) con sus columnas, fórmulas
grises para los costos y listas vivas de Odoo en REFERENCIAS. Se abre desde
la cotización (carpeta Presupuestos › cotización de Documentos) o desde la
obra; la obra que viene de una cotización con hoja usa la misma."""
import base64
import json

from odoo import api, fields, models

from odoo.addons.al_construction_planner_sale.wizards.budget_book_wizard import (
    COLUMNS, PRESUPUESTO_FORMULAS,
)

from .sheet_keys import keys_sheet
from .sheet_migration import last_part

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
# fila, {n} = última fila, {c:clave} = letra de la columna de la pestaña y
# {i:clave}, {a:clave}, {d:clave} = letra de la columna en INSUMOS, APU y
# APU_DETALLE). Las claves pueden ser de una columna calculada
# (CALCULATED_KEYS). Desde el paquete 1.16 (CR-22 g) el código va al final,
# así que las fórmulas buscan con XLOOKUP por la letra de cada columna.
CALCULATED = {
    'INSUMOS': [
        # CR-22 g: para elegir el insumo por nombre en APU_DETALLE.
        ('Para elegir', '=IF({c:code}{r}="","",{c:kind}{r}&" · "&{c:name}{r}&" · "&{c:uom}{r}'
                        '&" · "&{c:code}{r})'),
    ],
    'APU': [
        ('Costo unitario', '=IF({c:code}{r}="","",SUMIF(APU_DETALLE!{d:apu}$2:{d:apu}${n},'
                           '{c:code}{r},APU_DETALLE!{d:parcial}$2:{d:parcial}${n}))'),
        # CR-22 g: la receta se elige por nombre en APU_DETALLE.
        ('Para elegir', '=IF({c:code}{r}="","",{c:name}{r}&" · "&{c:code}{r})'),
    ],
    'APU_DETALLE': [
        # CR-22 g: los códigos salen de «nombre · código» de la receta y de
        # «tipo · nombre · unidad · código» del insumo elegidos.
        ('Código de la receta', '=IF({c:apu_pick}{r}="","",IFERROR(%s,{c:apu_pick}{r}))'
         % last_part('{c:apu_pick}{r}', '" · "')),
        ('Código del insumo', '=IF({c:pick}{r}="","",IFERROR(%s,{c:pick}{r}))'
         % last_part('{c:pick}{r}', '" · "')),
        ('Tipo (calc.)', '=IF({c:code}{r}="","",IFERROR(XLOOKUP({c:code}{r},INSUMOS!{i:code}$2:'
                         '{i:code}${n},INSUMOS!{i:kind}$2:{i:kind}${n}),""))'),
        ('Cantidad (calc.)', '=IF({c:apu}{r}="","",IF(AND({c:crew}{r}<>"",IFERROR(XLOOKUP('
                             '{c:apu}{r},APU!{a:code}$2:{a:code}${n},APU!{a:productivity}$2:'
                             '{a:productivity}${n}),0)<>0),{c:crew}{r}*IF(IFERROR(XLOOKUP('
                             '{c:apu}{r},APU!{a:code}$2:{a:code}${n},APU!{a:hours}$2:{a:hours}${n}'
                             '),"")="",8,XLOOKUP({c:apu}{r},APU!{a:code}$2:{a:code}${n},'
                             'APU!{a:hours}$2:{a:hours}${n}))/XLOOKUP({c:apu}{r},APU!{a:code}$2:'
                             '{a:code}${n},APU!{a:productivity}$2:{a:productivity}${n}),'
                             'IFERROR(VALUE({c:qty}{r}),0)))'),
        ('Precio (calc.)', '=IF({c:code}{r}="","",IF({c:price}{r}<>"",{c:price}{r},IFERROR('
                           'XLOOKUP({c:code}{r},INSUMOS!{i:code}$2:{i:code}${n},INSUMOS!'
                           '{i:price}$2:{i:price}${n}),0)))'),
        ('Parcial MO (calc.)', '=IF(OR({x:Tipo (calc.)}{r}="Mano de obra",{x:Tipo (calc.)}{r}='
                               '"Subcontrato"),{x:Cantidad (calc.)}{r}*{x:Precio (calc.)}{r},0)'),
        ('Parcial (calc.)', '=IF({c:apu}{r}="","",IF(OR({c:pct}{r}<>"",{x:Tipo (calc.)}{r}='
                            '"Herramienta %MO"),IFERROR(VALUE({c:pct}{r}),0)/100*SUMIF({c:apu}$2:'
                            '{c:apu}${n},{c:apu}{r},{x:Parcial MO (calc.)}$2:{x:Parcial MO (calc.)}'
                            '${n}),{x:Cantidad (calc.)}{r}*{x:Precio (calc.)}{r}))'),
        # CR-22 g: banda de color al cambiar de receta (formato condicional
        # sobre el número de la receta en APU).
        ('Receta n.º (calc.)', '=IF({c:apu}{r}="","",IFERROR(MATCH({c:apu}{r},APU!{a:code}$2:'
                               '{a:code}${n},0),""))'),
    ],
}
BAND_FILL = '#EAF1FB'
# PRESUPUESTO (CR-18, c): columnas A a W en el orden del libro 6.6; las
# fórmulas usan la letra de cada clave ({clave}) y los porcentajes van en %.
PRESUPUESTO_KEYS = [key for key, _aliases, _required in COLUMNS['PRESUPUESTO']]
PRESUPUESTO_HEADERS = [aliases[0] for _key, aliases, _required in COLUMNS['PRESUPUESTO']]
PRESUPUESTO_FORMULA_TEXT = {
    'qty_offered': '=IF({qty_real}{r}="","",{qty_real}{r}*(1+IFERROR(VALUE({qty_slack_pct}{r}),0)/100)'
                   '+IFERROR(VALUE({qty_slack}{r}),0))',
    'unit_cost': '=IF({apu}{r}="",IF({cost_no_apu}{r}="","",{cost_no_apu}{r}),'
                 'IFERROR(XLOOKUP({apu}{r},APU!${apu_code}:${apu_code},APU!${apu_unit}:'
                 '${apu_unit}),0))',
    'cost_offered': '=IF({unit_cost}{r}="","",{unit_cost}{r}*(1+IFERROR(VALUE({cost_slack_pct}{r}),0)/100)'
                    '+IFERROR(VALUE({cost_slack}{r}),0))',
    'price_unit': '=IF({cost_offered}{r}="","",{cost_offered}{r}*(1+IFERROR(VALUE({margin_pct}{r}),0)/100)'
                  '+IFERROR(VALUE({margin}{r}),0))',
    'cost_real': '=IF(OR({qty_real}{r}="",{unit_cost}{r}=""),"",{qty_real}{r}*{unit_cost}{r})',
    'amount_offered': '=IF(OR({qty_offered}{r}="",{cost_offered}{r}=""),"",'
                      '{qty_offered}{r}*{cost_offered}{r})',
    'subtotal': '=IF(OR({qty_offered}{r}="",{price_unit}{r}=""),"",'
                '{qty_offered}{r}*{price_unit}{r})',
    'reserve': '=IF(OR({amount_offered}{r}="",{cost_real}{r}=""),"",'
               '{amount_offered}{r}-{cost_real}{r})',
}
# Unidad de la partida con APU: la del APU.
PRESUPUESTO_UOM_FORMULA = '=IFERROR(XLOOKUP({apu}{r},APU!${apu_code}:${apu_code},APU!${apu_uom}:' \
                          '${apu_uom}),"")'
# Orden de las columnas de la plantilla (paquete 1.16, CR-22 g). Las hojas
# creadas antes tienen el código en la columna A (``construction_sheet_layout``
# 0 o 1); «Traer de Odoo» les escribe las fórmulas de su orden.
BUDGET_LAYOUT = 2
# Hoja de planificación: desde el 2, BOM y PIEZAS en el orden del paquete 1.17
# (M117-02) y _LISTAS con los módulos por tipología.
# 4: M117-24, MODULOS calcula la clase desde el catálogo de tipos (REFERENCIAS AB:AD).
FURNITURE_LAYOUT = 4
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


def presupuesto_formula(key, row, layout=BUDGET_LAYOUT):
    """Fórmula de la columna ``key`` de PRESUPUESTO en la fila ``row``.
    ``layout`` < 2: hoja anterior, con el código del APU en la columna A."""
    letters = {k: _col(i) for i, k in enumerate(PRESUPUESTO_KEYS)}
    text = PRESUPUESTO_FORMULA_TEXT[key] if key != 'uom' else PRESUPUESTO_UOM_FORMULA
    if layout < BUDGET_LAYOUT:
        apu = template_letters('APU', layout=layout)
        text = text.replace(
            'IFERROR(XLOOKUP({apu}{r},APU!${apu_code}:${apu_code},APU!${apu_unit}:${apu_unit}),0)',
            'IFERROR(VLOOKUP({apu}{r},APU!$A:$%s,%s,0),0)' % (
                apu['Costo unitario'], _letter_number(apu['Costo unitario']))).replace(
            'IFERROR(XLOOKUP({apu}{r},APU!${apu_code}:${apu_code},APU!${apu_uom}:${apu_uom}),"")',
            'IFERROR(VLOOKUP({apu}{r},APU!$A:$C,3,0),"")')
    else:
        apu = template_letters('APU')
        text = text.replace('{apu_code}', apu['code']).replace(
            '{apu_unit}', apu['Costo unitario']).replace('{apu_uom}', apu['uom'])
    text = text.replace('{r}', str(row))
    for name, letter in letters.items():
        text = text.replace('{%s}' % name, letter)
    return text


def presupuesto_row(values, row, layout=BUDGET_LAYOUT):
    """Fila completa de PRESUPUESTO: los datos de ``values`` y las fórmulas
    grises; la unidad, con fórmula si hay APU."""
    result = []
    for key in PRESUPUESTO_KEYS:
        if key in PRESUPUESTO_FORMULAS:
            result.append(presupuesto_formula(key, row, layout))
        elif key == 'uom' and values.get('apu'):
            result.append(presupuesto_formula('uom', row, layout))
        else:
            result.append(cell_text(values.get(key)))
    return result


# Columnas de datos de la plantilla, en su orden, cuando no es el del libro
# (paquete 1.16, CR-22 g): nombre primero y código al final. En APU_DETALLE la
# receta y el insumo se eligen por nombre y sus códigos son fórmulas.
TEMPLATE_KEYS = {
    'INSUMOS': ['kind', 'name', 'uom', 'price', 'currency', 'date', 'source', 'worker_category',
                'code'],
    'APU': ['name', 'uom', 'productivity', 'hours', 'mode', 'stage', 'code'],
    'APU_DETALLE': ['apu_pick', 'pick', 'crew', 'pct', 'qty', 'price', 'stage'],
}
# Orden de las hojas anteriores (código en la columna A).
LEGACY_TEMPLATE_KEYS = {
    'APU_DETALLE': ['apu', 'pick', 'crew', 'pct', 'qty', 'price', 'stage'],
}
# Encabezados de las columnas que no son del libro.
TEMPLATE_LABELS = {'apu_pick': 'Receta (nombre · código)'}
# Columnas calculadas que el envío lee con una clave.
CALCULATED_KEYS = {('APU_DETALLE', 'Código de la receta'): 'apu',
                   ('APU_DETALLE', 'Código del insumo'): 'code'}

# Orden de los valores de cada fila de ``_construction_budget_rows``.
ROW_KEYS = {
    'INSUMOS': ['code', 'name', 'kind', 'uom', 'price', 'currency'],
    'APU': ['code', 'name', 'uom', 'productivity', 'hours', 'mode'],
    'APU_DETALLE': ['apu', 'pick', 'crew', 'pct', 'qty', 'price', 'stage', 'code', 'apu_pick'],
}


def data_keys(name, layout=BUDGET_LAYOUT):
    """Claves de las columnas de datos de la plantilla, en su orden."""
    if layout < BUDGET_LAYOUT and name in LEGACY_TEMPLATE_KEYS:
        return list(LEGACY_TEMPLATE_KEYS[name])
    if layout >= BUDGET_LAYOUT and name in TEMPLATE_KEYS:
        return list(TEMPLATE_KEYS[name])
    return [key for key, _aliases, _required in COLUMNS[name]
            if (name, key) not in (('APU', 'unit_cost'), ('PRESUPUESTO', 'cost_real'))
            and key != 'pick']


def calculated(name, layout=BUDGET_LAYOUT):
    """Columnas calculadas de la pestaña (las hojas anteriores no tienen las
    de la receta por nombre)."""
    items = CALCULATED.get(name, [])
    if layout < BUDGET_LAYOUT:
        items = [(header, formula) for header, formula in items if header not in (
            'Código de la receta', 'Receta n.º (calc.)') and not (
            name == 'APU' and header == 'Para elegir')]
    return items


def sheet_headers(name, layout=BUDGET_LAYOUT):
    """Encabezados de datos y calculados de una pestaña del libro."""
    labels = {key: aliases[0] for key, aliases, _required in COLUMNS[name]}
    labels.update(TEMPLATE_LABELS)
    data = [labels[key] for key in data_keys(name, layout)]
    return data, [header for header, _formula in calculated(name, layout)]


def template_letters(name, layout=BUDGET_LAYOUT):
    """{clave o encabezado calculado: letra} de una pestaña de la plantilla."""
    data_headers, calc_headers = sheet_headers(name, layout)
    letters = {key: _col(i) for i, key in enumerate(data_keys(name, layout))}
    for index, header in enumerate(calc_headers):
        letter = _col(len(data_headers) + index)
        letters[header] = letter
        key = CALCULATED_KEYS.get((name, header))
        if key:
            letters[key] = letter
    return letters


def _letter_number(letters):
    """Número de la columna (A → 1)."""
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - 64
    return number


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # Paquete 1.13, M113-05: 0 = automático (la hoja nace con 300 filas y
    # «Importar Excel a la hoja» la amplía a las del archivo más un 10 %).
    construction_spreadsheet_rows = fields.Integer(
        string='Filas de la hoja de trabajo', default=0,
        help='Filas con listas y columnas calculadas por pestaña. 0 (automático): la hoja nace '
             'con 300 filas y la importación de un Excel la amplía. Con un número, la hoja nace '
             'con esas filas; la importación también la amplía si no alcanzan.')

    # Paquete 1.13, M113-12: la hoja vigente y su estado, en la ficha.
    construction_sheet_document_id = fields.Many2one(
        'documents.document', string='Hoja de trabajo vigente',
        compute='_compute_construction_sheet_document_id',
        search='_search_construction_sheet_document_id')
    construction_sheet_state = fields.Selection(
        related='construction_sheet_document_id.construction_sheet_state')
    construction_sheet_version = fields.Integer(
        related='construction_sheet_document_id.construction_version')
    construction_sheet_import_filename = fields.Char(
        related='construction_sheet_document_id.construction_import_filename')
    construction_sheet_import_date = fields.Datetime(
        related='construction_sheet_document_id.construction_import_date')
    construction_sheet_import_errors = fields.Integer(
        related='construction_sheet_document_id.construction_import_errors')
    construction_sheet_send_version = fields.Integer(
        related='construction_sheet_document_id.construction_send_version')
    construction_sheet_send_date = fields.Datetime(
        related='construction_sheet_document_id.construction_send_date')
    construction_sheet_send_message_id = fields.Many2one(
        related='construction_sheet_document_id.construction_send_message_id')
    construction_sheet_control_state = fields.Selection(
        related='construction_sheet_document_id.construction_control_state')
    construction_sheet_control_date = fields.Datetime(
        related='construction_sheet_document_id.construction_control_date')

    def _compute_construction_sheet_document_id(self):
        # sudo: la ficha muestra el estado de la hoja aunque el usuario no
        # tenga acceso a la carpeta del documento; solo se lee el vínculo.
        documents_sudo = self.env['documents.document'].sudo().search([
            ('construction_project_id', 'in', self.ids),
            ('construction_source_id', '=', False),
            ('handler', '=', 'spreadsheet')], order='id')
        by_project = {}
        for document_sudo in documents_sudo:
            by_project.setdefault(document_sudo.construction_project_id.id, document_sudo)
        for project in self:
            project.construction_sheet_document_id = by_project.get(project.id, False)

    def _search_construction_sheet_document_id(self, operator, value):
        # Búsqueda del campo calculado: Odoo la usa para saber qué proyectos
        # recalcular cuando cambia el estado de la hoja (campos relacionados).
        if operator not in ('in', 'not in'):
            return NotImplemented
        ids = {v for v in value if v}
        # sudo: solo el vínculo de la hoja con su obra, como en el cálculo.
        documents_sudo = self.env['documents.document'].sudo().browse(ids).exists().filtered(
            lambda d: d.construction_project_id and not d.construction_source_id
            and d.handler == 'spreadsheet')
        projects = documents_sudo.construction_project_id
        current = projects.filtered(
            lambda p: p.construction_sheet_document_id in documents_sudo).ids
        if False in value:
            # Sin hoja vigente: las obras sin documento de hoja.
            with_sheet = self.env['documents.document'].sudo().search([
                ('construction_project_id', '!=', False), ('construction_source_id', '=', False),
                ('handler', '=', 'spreadsheet')]).construction_project_id.ids
            domain = ['|', ('id', 'in', current), ('id', 'not in', with_sheet)]
        else:
            domain = [('id', 'in', current)]
        return domain if operator == 'in' else ['!', *domain]

    def action_construction_open_sheet_message(self):
        """Abre el registro con el mensaje del último envío de la hoja."""
        self.ensure_one()
        message = self.construction_sheet_send_message_id
        if not message:
            return False
        return {'type': 'ir.actions.act_window', 'res_model': message.model,
                'res_id': message.res_id, 'view_mode': 'form', 'views': [(False, 'form')]}

    def _construction_spreadsheet_kind(self):
        """La hoja del perfil de la obra; sin ella, presupuesto y plan."""
        self.ensure_one()
        return self.construction_profile_id.construction_spreadsheet_kind or 'budget'

    def _construction_spreadsheet_template(self, kind):
        """(datos, nombre) de la hoja nueva de la obra."""
        self.ensure_one()
        order = self.construction_sale_order_id
        data = self._construction_budget_spreadsheet_data(order, self)
        return data, self.env._('Presupuesto y plan · %s', self.name)

    def _construction_home_extra(self):
        """M117-09: estado de la hoja de la obra y su acción en Inicio."""
        result = super()._construction_home_extra()
        document = self.construction_sheet_document_id
        selection = dict(document._fields['construction_sheet_state']._description_selection(
            self.env))
        result['sheet_state'] = selection.get(document.construction_sheet_state, '') \
            if document else self.env._('Sin hoja')
        result['actions'] = result['actions'] + [{
            'label': self.env._('Abrir hoja') if document else self.env._('Crear hoja'),
            'method': 'action_construction_open_spreadsheet'}]
        return result

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
                'datas': base64.b64encode(json.dumps(data).encode()),
                'construction_project_id': self.id, 'construction_sheet_kind': kind,
                'construction_sheet_rows': max(self.construction_spreadsheet_rows or
                                               DEFAULT_ROWS, 10),
                'construction_sale_order_id': self.construction_sale_order_id.id
                if kind == 'budget' else False,
                'construction_sheet_layout': BUDGET_LAYOUT if kind == 'budget' else FURNITURE_LAYOUT,
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
        # CR-22 g: unidades en español y la etapa por su nombre.
        lang = 'es_PE' if 'es_PE' in dict(self.env['res.lang'].get_installed()) \
            else self.env.lang
        Stage = self.env['construction.stage'].with_context(lang=lang, active_test=False)
        stage_names = {stage.code: stage._label() for stage in Stage.search([])}
        hours_default = (project.company_id if project else
                         (order.company_id if order else self.env.company)
                         ).construction_workday_hours or 8.0  # como el envío
        for recipe in recipes.with_context(lang=lang):
            # CR-22 e: el rendimiento y las horas de la receta (líneas por
            # cuadrilla), para que el envío recalcule la mano de obra.
            crew_lines = recipe.line_ids.filtered('productivity')
            productivity = crew_lines[:1].productivity or ''
            rows['APU'].append([recipe.code, recipe.name, recipe.uom_id.name or '',
                                productivity, hours_default if productivity else '',
                                modes.get(recipe.execution_mode, '')])
            for line in recipe.line_ids:
                record = line.activity_id or line.product_id
                code = (line.product_id.default_code or line.activity_id.code or
                        'P-%s' % line.product_id.id) if record else ''
                if not code:
                    continue
                kind = 'Herramienta %MO' if line.calc_method == 'pct_labor' else \
                    kinds.get(line.resource_type, 'Material')
                # El nombre sin el código entre corchetes (CR-22 g).
                name = record.name or record.display_name
                uom = line.product_uom_id.name or ''
                insumos.setdefault(code, [code, name, kind, uom,
                                          line.price_unit or line._construction_default_cost(),
                                          (line.line_currency_id or recipe.currency_id).name])
                info = insumos[code]
                rows['APU_DETALLE'].append([
                    recipe.code, ' · '.join(str(v) for v in (info[2], info[1], info[3], code)),
                    line.crew_size if line.calc_method == 'crew' else '',
                    line.calc_pct if line.calc_method == 'pct_labor' else '',
                    line.qty if line.calc_method == 'qty' else '',
                    line.price_unit or '', stage_names.get(line.stage, line.stage or ''),
                    # El código va al final: en las hojas anteriores es dato.
                    code,
                    # CR-22 g: la receta por nombre, con el código al final.
                    '%s · %s' % (recipe.name, recipe.code)])
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
                    'margin': line.construction_margin_amount or '',
                    # Paquete 1.16, M116-05: catálogo de los dos primeros niveles.
                    'specialty_catalog': (line.construction_budget_catalog or ['', ''])[0] or '',
                    'subspecialty_catalog': ((line.construction_budget_catalog or ['', ''])
                                             + [''])[1] or ''})
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
                'id': 'PRESUPUESTO_mode', 'isBlocking': True,
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
        stage_count = len(self.env['construction.stage']._offered_stages(project))
        key_columns = {}
        for name in ('INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO'):
            data_headers, calc_headers = sheet_headers(name)
            keys = data_keys(name) if name != 'PRESUPUESTO' else PRESUPUESTO_KEYS
            letters = {key: _col(i) for i, key in enumerate(keys)}
            calc_letters = {header: _col(len(data_headers) + i)
                            for i, header in enumerate(calc_headers)}
            key_columns[name] = [(key, i) for i, key in enumerate(keys)]
            for header, letter in calc_letters.items():
                key = CALCULATED_KEYS.get((name, header))
                if key:
                    letters[key] = letter
                    key_columns[name].append((key, len(data_headers) + calc_headers.index(header)))
            letters_by_sheet[name] = (letters, calc_letters)
        # Letras de las otras pestañas para las fórmulas ({i:}, {a:}, {d:}).
        others = {prefix: dict(letters_by_sheet[sheet][0], **letters_by_sheet[sheet][1])
                  for prefix, sheet in (('i', 'INSUMOS'), ('a', 'APU'), ('d', 'APU_DETALLE'))}
        others['d']['parcial'] = others['d']['Parcial (calc.)']
        for name in ('INSUMOS', 'APU', 'APU_DETALLE'):
            data_headers, calc_headers = sheet_headers(name)
            letters, calc_letters = letters_by_sheet[name]
            cells, styles = {}, {}
            for i, header in enumerate(data_headers + calc_headers):
                cells['%s1' % _col(i)] = header
                styles['%s1' % _col(i)] = DATA_STYLE if i < len(data_headers) else CALC_STYLE
            # Los datos llegan en el orden de ROW_KEYS; cada uno va a la
            # columna de su clave (las calculadas no se escriben).
            data_letters = {key: letters[key] for key in data_keys(name)}
            for number, row in enumerate(values[name], start=2):
                for key, value in zip(ROW_KEYS[name], row):
                    if key in data_letters and value not in (None, '', False):
                        cells['%s%s' % (data_letters[key], number)] = cell_text(value)
            for header, formula in CALCULATED.get(name, []):
                column = calc_letters[header]
                template = formula.replace('{n}', str(last))
                for key, letter in letters.items():
                    template = template.replace('{c:%s}' % key, letter)
                for calc_header, letter in calc_letters.items():
                    template = template.replace('{x:%s}' % calc_header, letter)
                for prefix, sheet_letters in others.items():
                    for key, letter in sheet_letters.items():
                        template = template.replace('{%s:%s}' % (prefix, key), letter)
                for number in range(2, rows + 2):
                    cells['%s%s' % (column, number)] = template.replace('{r}', str(number))
            rules = []
            for key, list_name in (('kind', 'Tipo de insumo'), ('mode', 'Modalidad')):
                if key in letters:
                    rules.append({'id': '%s_%s' % (name, key), 'isBlocking': True,
                                  'ranges': ['%s2:%s%s' % (letters[key], letters[key], last)],
                                  'criterion': {'type': 'isValueInList', 'displayStyle': 'arrow',
                                                'values': LISTS[list_name]}})
            conditional = []
            if name == 'APU_DETALLE':
                # CR-22 g: la receta y el insumo se eligen escribiendo parte
                # del nombre (el desplegable nativo filtra al escribir).
                for key, sheet, letter in (
                        ('apu_pick', 'APU', letters_by_sheet['APU'][1]['Para elegir']),
                        ('pick', 'INSUMOS', letters_by_sheet['INSUMOS'][1]['Para elegir'])):
                    rules.append({'id': 'APU_DETALLE_%s' % key, 'isBlocking': False,
                                  'ranges': ['%s2:%s%s' % (letters[key], letters[key], last)],
                                  'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                                                'values': ['%s!$%s$2:$%s$%s' % (
                                                    sheet, letter, letter, last)]}})
                # Banda de color al cambiar de receta: las recetas impares de
                # APU en celeste.
                band = calc_letters['Receta n.º (calc.)']
                conditional.append({
                    'id': 'APU_DETALLE_band', 'stopIfTrue': False,
                    'ranges': ['A2:%s%s' % (_col(len(data_headers) + len(calc_headers) - 1),
                                            last)],
                    'rule': {'type': 'CellIsRule', 'operator': 'customFormula',
                             'values': ['=ISODD(IFERROR(VALUE($%s2),0))' % band],
                             'style': {'fillColor': BAND_FILL}}})
                if stage_count:
                    rules.append({'id': 'APU_DETALLE_stage', 'isBlocking': False,
                                  'ranges': ['%s2:%s%s' % (letters['stage'], letters['stage'],
                                                           last)],
                                  'criterion': {'type': 'isValueInRange', 'displayStyle': 'arrow',
                                                'values': ['REFERENCIAS!$P$3:$P$%s' % (
                                                    stage_count + 2)]}})
            headers = data_headers + calc_headers
            sheets.append({
                'id': 'sheet_%s' % name.lower(), 'name': name,
                'colNumber': max(26, len(headers)), 'rowNumber': rows + 50,
                'cells': cells, 'styles': styles,
                # Encabezado y primeras columnas inmovilizados (CR-22 g).
                'panes': {'xSplit': 0 if name == 'INSUMOS' else 2, 'ySplit': 1},
                'cols': {str(i): {'size': max(110, 8 * len(header))}
                         for i, header in enumerate(headers)},
                'dataValidationRules': rules,
                'conditionalFormats': conditional,
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
                           'id': 'plan_mode', 'isBlocking': True,
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
        # Las etapas del perfil de la obra (paquete 1.16, M116-01).
        stage_labels = [stage._label() for stage in
                        self.env['construction.stage']._offered_stages(project)]
        for number, label in enumerate(stage_labels, start=3):
            ref_cells['P%s' % number] = label
        sheets.append({'id': 'sheet_referencias', 'name': 'REFERENCIAS', 'colNumber': 26,
                       'rowNumber': 2010, 'cells': ref_cells, 'styles': ref_styles})
        sheets.append({'id': 'sheet_errores', 'name': 'ERRORES', 'colNumber': 8, 'rowNumber': 300,
                       'cells': {'A2': 'Hoja', 'B2': 'Fila', 'C2': 'Columna', 'D2': 'Mensaje',
                                 'E2': 'Tipo', 'F2': 'Ir'},
                       'styles': {'%s2' % c: HEADER_STYLE for c in 'ABCDEF'},
                       'cols': {'3': {'size': 700}}})
        # Clave interna de cada columna (paquete 1.16, M116-09 y CR-22 d).
        sheets.append(keys_sheet(key_columns, header_style=HEADER_STYLE))
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
                'datas': base64.b64encode(json.dumps(data).encode()),
                'folder_id': self._construction_spreadsheet_folder().id,
                'construction_sale_order_id': self.id,
                'construction_project_id': project.id,
                'construction_sheet_kind': 'budget',
                'construction_sheet_layout': BUDGET_LAYOUT,
            })
        return document.action_open_spreadsheet()
