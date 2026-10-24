# -*- coding: utf-8 -*-
"""Excel de carga de APU y presupuesto (requerimiento CREVAL v1.0, 6.6 y 6.8).

Un libro con siete hojas reemplaza al de dos (RECETAS y NIVELES) para la
carga inicial y para los presupuestos que llegan de fuera:

* OBRA: datos de la cotización (tipo de contrato, formato, porcentajes del
  pie) como pares «Campo | Valor».
* INSUMOS: los recursos con su código único, tipo, unidad y precio.
* APU y APU_DETALLE: las recetas y sus recursos (cuadrilla, % de la mano de
  obra, cantidad por unidad, precio manual).
* PRESUPUESTO: las partidas de la obra con su APU, modalidad, metrado real,
  holguras y margen.
* LISTAS: valores válidos y la tabla de equivalencias de unidades.
* INSTRUCCIONES: no se lee.

Con destino Presupuesto crea o actualiza los insumos, las recetas y la
cotización (secciones, subsecciones, partidas y las líneas de gastos
generales, imprevistos, utilidad y descuento); con destino Plan, además, los
niveles de la obra, la receta, la modalidad y el metrado real de cada
partida, y genera el plan. Volver a importar actualiza sin duplicar. La hoja
de trabajo en Hojas de cálculo (6.7) usa las mismas hojas y columnas."""
import base64
import io
from collections import defaultdict

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import norm

from .budget_import_wizard import _number, _text

SHEETS = ('OBRA', 'INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO', 'LISTAS', 'INSTRUCCIONES')
# Columnas de cada hoja: clave, encabezados aceptados (el primero es el de la
# plantilla) y si es obligatoria.
COLUMNS = {
    'INSUMOS': [
        ('code', ('Código', 'Codigo'), True),
        ('name', ('Descripción', 'Descripcion'), True),
        ('kind', ('Tipo de insumo', 'Tipo'), True),
        ('uom', ('Unidad',), True),
        ('price', ('Precio sin IGV', 'Precio', 'Costo vigente'), False),
        ('currency', ('Moneda',), False),
        ('date', ('Fecha del precio', 'Fecha'), False),
        ('source', ('Fuente del precio', 'Fuente'), False),
        ('worker_category', ('Categoría de obrero', 'Categoria de obrero'), False),
    ],
    'APU': [
        ('code', ('Código', 'Codigo'), True),
        ('name', ('Descripción', 'Descripcion'), True),
        ('uom', ('Unidad',), True),
        ('productivity', ('Rendimiento por día', 'Rendimiento por dia', 'Rendimiento'), False),
        ('hours', ('Horas por jornada',), False),
        ('mode', ('Modalidad por defecto', 'Modalidad'), False),
        ('stage', ('Etapa',), False),
        ('unit_cost', ('Costo unitario',), False),
    ],
    'APU_DETALLE': [
        ('apu', ('Código del APU', 'Codigo del APU', 'APU'), True),
        ('code', ('Código del insumo', 'Codigo del insumo', 'Insumo'), True),
        ('crew', ('Cuadrilla',), False),
        ('pct', ('% de la mano de obra', '% MO', '%MO'), False),
        ('qty', ('Cantidad por unidad', 'Cantidad'), False),
        ('price', ('Precio manual',), False),
        ('stage', ('Etapa',), False),
    ],
    'PRESUPUESTO': [
        ('item', ('Ítem', 'Item'), False),
        ('specialty', ('Especialidad',), False),
        ('subspecialty', ('Sub-especialidad', 'Subespecialidad'), False),
        ('name', ('Partida',), True),
        ('apu', ('Código del APU', 'Codigo del APU', 'APU'), False),
        ('uom', ('Unidad',), False),
        ('mode', ('Modalidad',), False),
        ('qty_real', ('Metrado real',), True),
        ('qty_slack_pct', ('Holgura de metrado (%)', 'Holgura de metrado %'), False),
        ('qty_slack', ('Holgura de metrado',), False),
        ('cost_slack_pct', ('Holgura de costo (%)', 'Holgura de costo %'), False),
        ('cost_slack', ('Holgura de costo',), False),
        ('margin_pct', ('Margen (%)', 'Margen %'), False),
        ('margin', ('Margen',), False),
        ('cost_real', ('Costo real',), False),
    ],
}
# Campos de la hoja OBRA (columna A) → clave.
OBRA_FIELDS = {
    'obra': 'project', 'cliente': 'customer', 'moneda': 'currency',
    'tipo de contrato': 'contract_type', 'formato de impresion': 'print_format',
    'gastos generales %': 'overhead_pct', 'gastos generales': 'overhead_pct',
    'imprevistos %': 'contingency_pct', 'imprevistos': 'contingency_pct',
    'utilidad %': 'profit_pct', 'utilidad': 'profit_pct',
    'descuento %': 'discount_pct', 'descuento': 'discount_pct',
    'igv %': 'tax_pct', 'igv': 'tax_pct', 'fecha': 'date', 'version': 'version',
}
# Tipo de insumo → comportamiento del recurso («equipment_pct»: herramientas
# en % de la mano de obra).
KINDS = {
    'material': 'material', 'materiales': 'material',
    'mano de obra': 'labor', 'personal propio': 'labor',
    'equipo': 'equipment', 'equipos': 'equipment', 'equipo propio': 'equipment',
    'equipo alquilado': 'equipment',
    'subcontrato': 'contract', 'subcontratos': 'contract', 'contrata': 'contract',
    'herramienta %mo': 'equipment_pct', 'herramientas': 'equipment_pct',
    'herramientas %mo': 'equipment_pct', 'servicio': 'service', 'servicios': 'service',
}
MODES = {
    'personal propio': 'own', 'propio': 'own',
    'contrata solo de mano de obra': 'labor_contract', 'solo mano de obra': 'labor_contract',
    'contrata de mano de obra': 'labor_contract',
    'contrata a todo costo': 'full_contract', 'todo costo': 'full_contract',
}
CONTRACT_TYPES = {'suma alzada': 'lump_sum', 'precios unitarios': 'unit_price'}
PRINT_FORMATS = {'solo precios': 'prices', 'suma alzada': 'prices', 'desglosado': 'breakdown'}
FORMULA_ERRORS = ('#REF!', '#DIV/0!', '#VALUE!', '#N/A', '#NAME?', '#NUM!', '#NULL!')
# Líneas del pie que no son partidas (CR-12): nombre de la línea y signo.
FOOTER_LINES = (
    ('overhead_pct', 'Gastos generales', 1),
    ('contingency_pct', 'Imprevistos', 1),
    ('profit_pct', 'Utilidad', 1),
    ('discount_pct', 'Descuento', -1),
)


class ConstructionBudgetBookWizard(models.TransientModel):
    _name = 'construction.budget.book.wizard'
    _description = 'Importar el libro de APU y presupuesto'

    sale_order_id = fields.Many2one('sale.order', string='Cotización', required=True,
                                    readonly=True)
    company_id = fields.Many2one(related='sale_order_id.company_id')
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    project_id = fields.Many2one(
        'project.project', string='Obra', compute='_compute_project_id', store=True,
        readonly=False, domain=[('is_construction_site', '=', True)],
        help='La de la cotización. Con destino Plan es obligatoria.')
    target = fields.Selection(
        [('budget', 'Presupuesto'), ('plan', 'Presupuesto y plan')], string='Destino',
        default='budget', required=True,
        help='Presupuesto: insumos, recetas y cotización. Presupuesto y plan: además los niveles '
             'de la obra con su receta, modalidad y metrado real, y el plan.')
    file = fields.Binary(string='Libro (Excel)', required=True)
    filename = fields.Char(string='Nombre del archivo')
    default_stage_id = fields.Many2one(
        'construction.stage', string='Etapa por defecto',
        help='La de los recursos y actividades sin etapa en el libro.')
    replan_reason = fields.Text(
        string='Motivo de la versión',
        help='Con el plan aprobado, el envío crea una nueva versión del plan con este motivo.')
    state = fields.Selection(
        [('upload', 'Archivo'), ('preview', 'Revisión'), ('done', 'Hecho')], default='upload')
    preview_html = fields.Html(string='Revisión', readonly=True, sanitize=False)
    accept_warnings = fields.Boolean(string='Acepto los avisos')
    has_warnings = fields.Boolean(readonly=True)

    @api.depends('sale_order_id')
    def _compute_project_id(self):
        for wizard in self:
            order = wizard.sale_order_id
            wizard.project_id = order.project_id or order.project_ids[:1] \
                if order else wizard.project_id

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    @api.model
    def _load_book(self, content):
        try:
            import openpyxl
        except ImportError as error:
            raise UserError(self.env._('Falta la librería openpyxl en el servidor.')) from error
        book = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheets = {}
        for sheet in book.worksheets:
            name = norm(sheet.title).upper().replace(' ', '_')
            sheets[name] = list(sheet.iter_rows(values_only=True))
        return sheets

    @api.model
    def _sheet_rows(self, rows, sheet, errors):
        """Filas de una hoja con encabezados: [{clave: valor, '_row': n}]."""
        columns = COLUMNS[sheet]
        for position, row in enumerate(rows[:10]):
            names = [norm(_text(cell)) for cell in row]
            index = {}
            for key, aliases, _required in columns:
                for alias in aliases:
                    if norm(alias) in names:
                        index[key] = names.index(norm(alias))
                        break
            if all(key in index for key, _aliases, required in columns if required):
                break
        else:
            missing = [aliases[0] for key, aliases, required in columns if required]
            errors.append((sheet, 1, '', self.env._(
                'No se encuentran los encabezados obligatorios: %s.', ', '.join(missing))))
            return []
        result = []
        for number, row in enumerate(rows[position + 1:], start=position + 2):
            values = {key: row[i] if i < len(row) else None for key, i in index.items()}
            if not any(_text(value) for value in values.values()):
                continue
            for key, value in values.items():
                if isinstance(value, str) and value.strip().upper() in FORMULA_ERRORS:
                    errors.append((sheet, number, key, self.env._(
                        'La fórmula da error (%s).', value.strip())))
            values['_row'] = number
            result.append(values)
        return result

    def _uom(self, text):
        text = _text(text)
        if not text:
            return self.env['uom.uom']
        return self.env['construction.uom.alias']._find(text, self.company_id) or \
            self.env['uom.uom'].search([('name', '=ilike', text)], limit=1)

    def _parse(self, content=None):
        """El libro como datos y la lista de errores y avisos:
        ``(book, errors, warnings)``; cada error es (hoja, fila, columna,
        mensaje)."""
        self.ensure_one()
        sheets = self._load_book(content or base64.b64decode(self.file))
        errors, warnings = [], []
        for name in ('INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO'):
            if name not in sheets:
                errors.append((name, 0, '', self.env._('Falta la hoja %s.', name)))
        if errors:
            return {}, errors, warnings
        book = {'obra': {}, 'aliases': [], 'insumos': {}, 'apus': {}, 'partidas': []}
        # OBRA: pares «Campo | Valor».
        for row in sheets.get('OBRA', []):
            if len(row) >= 2 and _text(row[0]):
                key = OBRA_FIELDS.get(norm(_text(row[0])).rstrip(':'))
                if key:
                    book['obra'][key] = row[1]
        # LISTAS: la tabla de equivalencias («Escrito como» | «Unidad»).
        rows = sheets.get('LISTAS', [])
        for position, row in enumerate(rows):
            names = [norm(_text(cell)) for cell in row]
            if 'escrito como' in names and 'unidad' in names:
                written, unit = names.index('escrito como'), names.index('unidad')
                for number, values in enumerate(rows[position + 1:], start=position + 2):
                    text = _text(values[written]) if written < len(values) else ''
                    target = _text(values[unit]) if unit < len(values) else ''
                    if text and target:
                        book['aliases'].append((text, target, number))
                break
        alias_by_text = {norm(text): target for text, target, _row in book['aliases']}

        def uom_of(text, sheet, row, required=True):
            text = _text(text)
            target = alias_by_text.get(norm(text), text)
            uom = self._uom(target) or self._uom(text)
            if text and not uom and required:
                errors.append((sheet, row, 'uom', self.env._(
                    'La unidad «%s» no tiene equivalencia (hoja LISTAS).', text)))
            return uom

        for row in self._sheet_rows(sheets['INSUMOS'], 'INSUMOS', errors):
            code = _text(row.get('code'))
            if code in book['insumos']:
                errors.append(('INSUMOS', row['_row'], 'code', self.env._(
                    'El código %s está repetido.', code)))
                continue
            kind = KINDS.get(norm(_text(row.get('kind'))))
            if not kind:
                errors.append(('INSUMOS', row['_row'], 'kind', self.env._(
                    'El tipo de insumo «%s» no es válido (hoja LISTAS).', _text(row.get('kind')))))
                continue
            currency_text = _text(row.get('currency'))
            currency = self.env['res.currency'].with_context(active_test=False).search(
                [('name', '=ilike', currency_text)], limit=1) if currency_text else \
                self.company_id.currency_id
            if currency_text and not currency:
                errors.append(('INSUMOS', row['_row'], 'currency', self.env._(
                    'La moneda «%s» no existe.', currency_text)))
            book['insumos'][code] = {
                'code': code, 'name': _text(row.get('name')), 'kind': kind,
                'uom': uom_of(row.get('uom'), 'INSUMOS', row['_row']) if kind != 'equipment_pct'
                else self.env['uom.uom'],
                'price': _number(row.get('price')) or 0.0, 'currency': currency,
                'row': row['_row']}
        for row in self._sheet_rows(sheets['APU'], 'APU', errors):
            code = _text(row.get('code'))
            if code in book['apus']:
                errors.append(('APU', row['_row'], 'code', self.env._(
                    'El APU %s está repetido.', code)))
                continue
            mode_text = norm(_text(row.get('mode')))
            if mode_text and mode_text not in MODES:
                errors.append(('APU', row['_row'], 'mode', self.env._(
                    'La modalidad «%s» no es válida.', _text(row.get('mode')))))
            book['apus'][code] = {
                'code': code, 'name': _text(row.get('name')),
                'uom': uom_of(row.get('uom'), 'APU', row['_row']),
                'productivity': _number(row.get('productivity')) or 0.0,
                'hours': _number(row.get('hours')) or 0.0,
                'mode': MODES.get(mode_text, 'own'), 'stage': _text(row.get('stage')),
                'unit_cost': _number(row.get('unit_cost')), 'lines': [], 'row': row['_row']}
        for row in self._sheet_rows(sheets['APU_DETALLE'], 'APU_DETALLE', errors):
            apu, code = _text(row.get('apu')), _text(row.get('code'))
            if apu not in book['apus']:
                errors.append(('APU_DETALLE', row['_row'], 'apu', self.env._(
                    'El APU %s no existe en la hoja APU.', apu)))
                continue
            if code not in book['insumos']:
                errors.append(('APU_DETALLE', row['_row'], 'code', self.env._(
                    'El insumo %s no existe en la hoja INSUMOS.', code)))
                continue
            book['apus'][apu]['lines'].append({
                'insumo': code, 'crew': _number(row.get('crew')), 'pct': _number(row.get('pct')),
                'qty': _number(row.get('qty')), 'price': _number(row.get('price')),
                'stage': _text(row.get('stage')), 'row': row['_row']})
        items = defaultdict(int)
        for row in self._sheet_rows(sheets['PRESUPUESTO'], 'PRESUPUESTO', errors):
            apu = _text(row.get('apu'))
            if apu and apu not in book['apus']:
                errors.append(('PRESUPUESTO', row['_row'], 'apu', self.env._(
                    'El APU %s no existe en la hoja APU.', apu)))
                continue
            item = _text(row.get('item'))
            if item:
                items[item] += 1
            mode_text = norm(_text(row.get('mode')))
            book['partidas'].append({
                'item': item, 'specialty': _text(row.get('specialty')),
                'subspecialty': _text(row.get('subspecialty')), 'name': _text(row.get('name')),
                'apu': apu, 'uom': uom_of(row.get('uom'), 'PRESUPUESTO', row['_row'], False),
                'mode': MODES.get(mode_text) if mode_text else False,
                'qty_real': _number(row.get('qty_real')) or 0.0,
                'qty_slack_pct': _number(row.get('qty_slack_pct')) or 0.0,
                'qty_slack': _number(row.get('qty_slack')) or 0.0,
                'cost_slack_pct': _number(row.get('cost_slack_pct')) or 0.0,
                'cost_slack': _number(row.get('cost_slack')) or 0.0,
                'margin_pct': _number(row.get('margin_pct')) or 0.0,
                'margin': _number(row.get('margin')) or 0.0,
                'cost_real': _number(row.get('cost_real')), 'row': row['_row']})
        for item, count in items.items():
            if count > 1:
                warnings.append(self.env._('El ítem %(item)s aparece %(count)s veces.',
                                           item=item, count=count))
        unnumbered = [p for p in book['partidas'] if not p['item']]
        if unnumbered:
            warnings.append(self.env._('%s partidas sin número de ítem.', len(unnumbered)))
        if self.target == 'plan' and not self.project_id:
            errors.append(('OBRA', 0, '', self.env._(
                'El destino Plan necesita la obra de la cotización.')))
        if self.target == 'plan' and self.sale_order_id.construction_contract_type == \
                'unit_price' and any(p['qty_slack'] or p['qty_slack_pct']
                                     for p in book['partidas']):
            warnings.append(self.env._(
                'Contrato a precios unitarios: la holgura de metrado no se cobra.'))
        return book, errors, warnings

    @api.model
    def _errors_html(self, errors):
        return Markup('<ul class="text-danger">%s</ul>') % Markup('').join(
            Markup('<li>%s</li>') % self.env._(
                '%(sheet)s fila %(row)s%(col)s: %(msg)s', sheet=sheet, row=row or '-',
                col=(' (%s)' % col) if col else '', msg=msg)
            for sheet, row, col, msg in errors[:100])

    # ------------------------------------------------------------------
    # Pasos
    # ------------------------------------------------------------------
    def action_preview(self):
        self.ensure_one()
        book, errors, warnings = self._parse()
        if errors:
            body = Markup('<p class="text-danger">%s</p>') % self.env._(
                'El libro tiene %s errores: corríjalos y vuelva a cargarlo.', len(errors))
            body += self._errors_html(errors)
        else:
            body = Markup('<p>%s</p>') % self.env._(
                '%(insumos)s insumos, %(apus)s APU y %(partidas)s partidas; costo directo real '
                '%(amount)s.', insumos=len(book['insumos']), apus=len(book['apus']),
                partidas=len(book['partidas']),
                amount=self.currency_id.format(self._book_direct_cost(book)))
            if warnings:
                body += Markup('<p class="text-warning mb-1">%s</p><ul>%s</ul>') % (
                    self.env._('Avisos (acéptelos para enviar):'),
                    Markup('').join(Markup('<li>%s</li>') % w for w in warnings))
        self.write({'state': 'preview', 'preview_html': body, 'has_warnings': bool(warnings),
                    'accept_warnings': False})
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    def _book_direct_cost(self, book):
        """Costo directo real del libro: el «Costo real» de cada partida o,
        sin él, metrado real × costo del APU."""
        unit = {code: self._apu_unit_cost(book, apu) for code, apu in book['apus'].items()}
        total = 0.0
        for partida in book['partidas']:
            if partida['cost_real'] is not None:
                total += partida['cost_real']
            elif partida['apu']:
                total += partida['qty_real'] * unit[partida['apu']]
        return total

    def _apu_unit_cost(self, book, apu):
        """Costo por unidad del APU con las fórmulas de 6.6: cuadrilla ×
        horas ÷ rendimiento, % de la mano de obra y cantidad por unidad."""
        labor = 0.0
        total = 0.0
        pct_lines = []
        for line in apu['lines']:
            insumo = book['insumos'][line['insumo']]
            price = line['price'] if line['price'] is not None else insumo['price']
            if insumo['kind'] == 'equipment_pct' or line['pct']:
                pct_lines.append(line['pct'] or line['qty'] or 0.0)
                continue
            qty = self._detail_qty(apu, line)
            cost = qty * price
            total += cost
            if insumo['kind'] in ('labor', 'contract'):
                labor += cost
        return total + sum(pct / 100.0 * labor for pct in pct_lines)

    def _detail_qty(self, apu, line):
        if line['crew'] and apu['productivity']:
            hours = apu['hours'] or self.company_id.construction_workday_hours or 8.0
            return line['crew'] * hours / apu['productivity']
        return line['qty'] or 0.0

    def action_import(self):
        self.ensure_one()
        book, errors, warnings = self._parse()
        if errors:
            raise UserError(self.env._(
                'El libro tiene errores; revíselos con «Revisar» antes de enviar.'))
        if warnings and not self.accept_warnings:
            raise UserError(self.env._('Acepte los avisos de la revisión para enviar.'))
        result = self._apply(book)
        self.write({'state': 'done', 'preview_html': result})
        return self._reopen()

    # ------------------------------------------------------------------
    # Envío
    # ------------------------------------------------------------------
    def _apply(self, book):
        """Crea o actualiza insumos, recetas y cotización (y con destino Plan,
        niveles y plan). Si el costo directo de la cotización no es el del
        libro, todo se revierte."""
        self.ensure_one()
        order = self.sale_order_id
        company = self.company_id
        Alias = self.env['construction.uom.alias']
        for text, target, _row in book['aliases']:
            uom = self._uom(target)
            if uom and not Alias._find(text, company):
                Alias.create({'name': text, 'uom_id': uom.id, 'company_id': company.id})
        products, activities = self._apply_insumos(book)
        recipes = self._apply_apus(book, products, activities)
        lines = self._apply_budget(book, recipes)
        real = sum(lines.mapped('construction_amount_real'))
        # Con «Costo real» en el libro, la cotización da lo mismo (máx. 0.01).
        with_cost = [p for p in book['partidas'] if p['cost_real'] is not None]
        expected = sum(p['cost_real'] for p in with_cost)
        compared = sum(line.construction_amount_real for line in lines
                       if line.construction_budget_item in {p['item'] for p in with_cost})
        if with_cost and abs(compared - expected) > 0.011:
            raise UserError(self.env._(
                'El costo directo de la cotización (%(real)s) no es el del libro (%(book)s): '
                'se revierte el envío. Revise los costos del APU y el «Costo real».',
                real=self.currency_id.format(compared), book=self.currency_id.format(expected)))
        messages = [self.env._(
            'Cotización %(order)s: %(lines)s partidas, costo directo real %(amount)s.',
            order=order.name, lines=len(lines), amount=self.currency_id.format(real))]
        if self.target == 'plan':
            messages += self._apply_plan(book, recipes, lines)
        order.message_post(body=self.env._(
            'Libro de APU y presupuesto importado (%(file)s): %(summary)s',
            file=self.filename or '', summary=' '.join(messages)))
        return Markup('').join(Markup('<p>%s</p>') % message for message in messages)

    def _stage_code(self, text):
        Stage = self.env['construction.stage']
        if text:
            code = Stage._find_by_text(text)
            if code:
                return code
        return self.default_stage_id.code or next(iter(Stage._field_codes()), False)

    def _apply_insumos(self, book):
        """Productos (y actividades de mano de obra y contrata) de los
        insumos: los que existen por su código se respetan; los nuevos se
        crean con el precio del libro."""
        Product = self.env['product.product']
        Activity = self.env['construction.labor.activity']
        products, activities = {}, {}
        for code, insumo in book['insumos'].items():
            product = Product.search([('default_code', '=', code),
                                      ('company_id', 'in', (self.company_id.id, False))],
                                     limit=1)
            kind = insumo['kind']
            if not product:
                values = {
                    'name': insumo['name'], 'default_code': code,
                    'type': 'service' if kind in ('labor', 'contract', 'service', 'equipment_pct')
                    else 'consu',
                    'standard_price': insumo['price'] if insumo['currency'] ==
                    self.company_id.currency_id else 0.0,
                    'purchase_ok': kind not in ('labor', 'equipment_pct'),
                    'sale_ok': False,
                }
                if insumo['uom']:
                    values['uom_id'] = insumo['uom'].id
                product = Product.create(values)
            products[code] = product
            if kind in ('labor', 'contract'):
                activity = Activity.search([
                    ('code', '=', code), ('company_id', 'in', (self.company_id.id, False))],
                    limit=1)
                if not activity:
                    activity = Activity.create({
                        'code': code, 'name': insumo['name'],
                        'uom_id': (insumo['uom'] or product.uom_id).id,
                        'stage': self._stage_code(False), 'default_price': insumo['price'],
                        'company_id': self.company_id.id, 'product_id': product.id})
                activities[code] = activity
        return products, activities

    def _apply_apus(self, book, products, activities):
        """Recetas de la obra (o de la compañía) con sus líneas, por la
        importación de recetas del planificador."""
        Type = self.env['construction.resource.type']
        recipes = {}
        for code, apu in book['apus'].items():
            lines = []
            for line in apu['lines']:
                insumo = book['insumos'][line['insumo']]
                kind = insumo['kind']
                product = products[line['insumo']]
                price = line['price'] if line['price'] is not None else insumo['price']
                stage = self._stage_code(line['stage'] or apu['stage'])
                behavior = 'equipment' if kind == 'equipment_pct' else kind
                vals = {
                    'resource_type': behavior, 'resource_type_id': Type._default_for(behavior).id,
                    'stage': stage, 'qty': self._detail_qty(apu, line),
                    'price_unit': price,
                    'product_uom_id': (insumo['uom'] or product.uom_id).id,
                    'note': insumo['name'],
                }
                if kind == 'equipment_pct' or line['pct']:
                    pct = line['pct'] or line['qty'] or 0.0
                    vals.update(calc_method='pct_labor', calc_pct=pct, qty=pct / 100.0,
                                resource_type='equipment', price_unit=0.0,
                                resource_type_id=Type._default_for('equipment').id,
                                product_uom_id=self.env.ref('uom.product_uom_unit').id)
                elif line['crew'] and apu['productivity']:
                    vals.update(crew_size=line['crew'], productivity=apu['productivity'])
                if behavior in ('labor', 'contract'):
                    activity = activities[line['insumo']]
                    vals.update(activity_id=activity.id, product_id=product.id,
                                product_uom_id=(insumo['uom'] or activity.uom_id).id)
                else:
                    vals['product_id'] = product.id
                if insumo['currency'] and insumo['currency'] != self.company_id.currency_id:
                    vals['line_currency_id'] = insumo['currency'].id
                lines.append(vals)
            recipes[code] = {'name': apu['name'], 'uom': apu['uom'], 'lines': lines}
        importer = self.env['construction.recipe.import.wizard'].create({
            'source': 'excel', 'project_id': self.project_id.id,
            'company_id': self.company_id.id})
        templates, _created, _updated = importer._upsert_recipes(
            recipes, 'excel', dict.fromkeys(recipes, self.filename or False))
        result = {template.code: template for template in templates}
        for code, apu in book['apus'].items():
            result[code].execution_mode = apu['mode']
        return result

    def _partida_product(self):
        return self.env['construction.budget.import.wizard'].new(
            {'sale_order_id': self.sale_order_id.id})._partida_product()

    def _apply_budget(self, book, recipes):
        """Secciones, subsecciones y partidas de la cotización (y el pie):
        se actualizan por el ítem o el nombre; las nuevas se crean."""
        order = self.sale_order_id
        # Crear los niveles confirma la venta (Odoo, al enlazar la tarea): la
        # revisión del presupuesto sigue entrando a la orden mientras no esté
        # bloqueada ni anulada.
        if order.state == 'cancel' or order.locked:
            raise UserError(self.env._(
                'El presupuesto no entra a una orden anulada o bloqueada.'))
        obra = book['obra']
        header = {}
        contract_type = CONTRACT_TYPES.get(norm(_text(obra.get('contract_type'))))
        if contract_type:
            header['construction_contract_type'] = contract_type
        print_format = PRINT_FORMATS.get(norm(_text(obra.get('print_format'))))
        if print_format:
            header['construction_print_format'] = print_format
        if header:
            order.write(header)
        product = self._partida_product()
        Line = self.env['sale.order.line']
        existing = order.order_line
        by_item = {line.construction_budget_item: line for line in existing
                   if line.construction_budget_item and not line.display_type}
        by_title = {(line.display_type, norm(line.name)): line for line in existing
                    if line.display_type in ('line_section', 'line_subsection')}
        sequence = 0
        touched = Line
        section_key = subsection_key = None
        for partida in book['partidas']:
            for display_type, title, key_attr in (
                    ('line_section', partida['specialty'], 'section'),
                    ('line_subsection', partida['subspecialty'], 'subsection')):
                if not title:
                    continue
                key = (display_type, norm(title))
                if (key_attr == 'section' and key == section_key) or \
                        (key_attr == 'subsection' and key == subsection_key):
                    continue
                sequence += 1
                line = by_title.get(key)
                if line:
                    line.sequence = sequence
                else:
                    line = Line.create({'order_id': order.id, 'display_type': display_type,
                                        'name': title, 'sequence': sequence})
                    by_title[key] = line
                touched |= line
                if key_attr == 'section':
                    section_key, subsection_key = key, None
                else:
                    subsection_key = key
            sequence += 1
            # El costo del libro manda (el «Costo real» de la partida o las
            # fórmulas del APU, sin redondear: CR-03).
            if partida['cost_real'] is not None and partida['qty_real']:
                cost_apu = partida['cost_real'] / partida['qty_real']
            elif partida['apu']:
                cost_apu = self._apu_unit_cost(book, book['apus'][partida['apu']])
            else:
                cost_apu = 0.0
            label = ' '.join(filter(None, [partida['item'], partida['name']]))
            values = {
                'name': label, 'sequence': sequence,
                'construction_budget_item': partida['item'] or False,
                'construction_qty_real': partida['qty_real'],
                'construction_qty_slack_pct': partida['qty_slack_pct'],
                'construction_qty_slack': partida['qty_slack'],
                'construction_cost_apu': cost_apu,
                'construction_cost_slack_pct': partida['cost_slack_pct'],
                'construction_cost_slack': partida['cost_slack'],
                'construction_margin_pct': partida['margin_pct'],
                'construction_margin_amount': partida['margin'],
                'construction_line_role': 'partida',
            }
            if partida['uom']:
                values['product_uom_id'] = partida['uom'].id
            line = by_item.get(partida['item']) if partida['item'] else False
            if line:
                line.write(values)
            else:
                line = Line.create(dict(values, order_id=order.id, product_id=product.id))
            touched |= line
        partidas = touched.filtered(lambda l: not l.display_type)
        self._apply_footer(book, partidas, sequence)
        return partidas

    def _apply_footer(self, book, partidas, sequence):
        """Gastos generales, imprevistos, utilidad y descuento del libro (hoja
        OBRA, en % del costo de las partidas): líneas que no son partidas."""
        order = self.sale_order_id
        product = self._partida_product()
        base = sum(partidas.mapped('price_subtotal'))
        for key, label, sign in FOOTER_LINES:
            pct = _number(book['obra'].get(key))
            if not pct:
                continue
            sequence += 1
            name = '%s %s %%' % (label, round(pct, 4))
            line = order.order_line.filtered(
                lambda l, n=norm(label): not l.display_type and l.construction_line_role != 'partida'
                and norm(l.name or '').startswith(n))[:1]
            values = {'name': name, 'product_uom_qty': 1.0, 'sequence': sequence,
                      'price_unit': sign * base * pct / 100.0}
            if line:
                line.write(values)
            else:
                self.env['sale.order.line'].create(dict(values, order_id=order.id,
                                                        product_id=product.id))

    def _apply_plan(self, book, recipes, lines):
        """Niveles de la obra desde la cotización, con la receta, la modalidad
        y el metrado real de cada partida, y el plan generado. Con el plan
        aprobado, una versión nueva con el motivo."""
        order = self.sale_order_id
        project = self.project_id
        if not order.project_id:
            order.project_id = project
        order.action_construction_create_levels()
        Task = self.env['project.task']
        by_line = {task.sale_line_id: task for task in Task.search([
            ('project_id', '=', project.id), ('sale_line_id', 'in', lines.ids)])}
        partida_by_line = {}
        for line in lines:
            item = line.construction_budget_item
            partida_by_line[line] = next(
                (p for p in book['partidas'] if (p['item'] and p['item'] == item)
                 or (not p['item'] and ' '.join(filter(None, [p['item'], p['name']])) ==
                     line.name)), None)
        Plan = self.env['construction.resource.plan']
        plan = Plan.search([('project_id', '=', project.id), ('state', '=', 'draft')],
                           order='id desc', limit=1)
        messages = []
        if not plan:
            current = project._construction_current_plan()
            if current:
                if not (self.replan_reason or '').strip():
                    raise UserError(self.env._(
                        'El plan %s está aprobado: escriba el motivo de la nueva versión.',
                        current.display_name))
                action = self.env['construction.plan.replan.wizard'].create({
                    'plan_id': current.id, 'reason': self.replan_reason}).action_create_version()
                plan = Plan.browse(action['res_id'])
                messages.append(self.env._('Versión nueva del plan: %s.', plan.display_name))
            else:
                plan = Plan.create({'project_id': project.id})
        blocked = []
        tasks = Task
        for line, task in by_line.items():
            partida = partida_by_line.get(line)
            recipe = recipes.get(partida['apu']) if partida else False
            committed = plan.line_ids.filtered(
                lambda l, t=task: l.task_id == t and l.previous_line_id
                and (l.previous_line_id.qty_requested or l.previous_line_id.qty_executed))
            if committed:
                # Con compromisos o avance no se regenera: se resuelve con un
                # cambio de obra (6.7).
                blocked.append(task.display_name)
                continue
            values = {'construction_qty': line.construction_qty_real or line.product_uom_qty}
            if recipe:
                values['construction_execution_template_id'] = recipe.id
            task.with_context(construction_plan_force=True).write(values)
            mode = (partida or {}).get('mode') or (recipe.execution_mode if recipe else False)
            if mode:
                task.with_context(construction_plan_force=True).construction_execution_mode = mode
            if recipe:
                tasks |= task
        if tasks:
            plan.line_ids.filtered(
                lambda l: l.task_id in tasks and l.source in ('recipe', 'replan')).unlink()
            self.env['construction.plan.recipe.wizard'].create({
                'plan_id': plan.id, 'task_ids': [Command.set(tasks.ids)],
                'mode': 'add'}).action_generate()
        messages.append(self.env._(
            'Plan %(plan)s: %(tasks)s partidas con su receta.', plan=plan.display_name,
            tasks=len(tasks)))
        if blocked:
            messages.append(self.env._(
                'Con compromisos o avance, no se regeneraron (resuélvalas con un cambio de '
                'obra): %s.', ', '.join(blocked[:20])))
        return messages

    # ------------------------------------------------------------------
    # Plantilla
    # ------------------------------------------------------------------
    @api.model
    def _template_workbook(self):
        """Libro vacío de 6.6: las siete hojas con sus encabezados; celdas
        amarillas para datos y la tabla de equivalencias en LISTAS."""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        yellow = PatternFill('solid', fgColor='FFF2CC')
        book = Workbook()
        sheet = book.active
        sheet.title = 'INSTRUCCIONES'
        for text in (
                self.env._('Libro de carga de APU y presupuesto (Planificación de obra).'),
                self.env._('Celdas amarillas: datos. Celdas grises: fórmulas.'),
                self.env._('OBRA: campo y valor. INSUMOS: un recurso por fila con código único. '
                           'APU y APU_DETALLE: la receta de cada partida tipo. PRESUPUESTO: las '
                           'partidas de la obra. LISTAS: valores válidos y equivalencias de '
                           'unidades.'),
                self.env._('Cargar en Odoo: cotización › Importar libro de APU y presupuesto.')):
            sheet.append([text])
        sheet = book.create_sheet('OBRA')
        for label in ('Obra', 'Cliente', 'Moneda', 'Tipo de contrato', 'Formato de impresión',
                      'Gastos generales %', 'Imprevistos %', 'Utilidad %', 'Descuento %', 'IGV %',
                      'Fecha', 'Versión'):
            sheet.append([label, None])
            sheet.cell(row=sheet.max_row, column=2).fill = yellow
        for name in ('INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO'):
            sheet = book.create_sheet(name)
            sheet.append([aliases[0] for _key, aliases, _required in COLUMNS[name]])
            for cell in sheet[1]:
                cell.font = Font(bold=True)
        sheet = book.create_sheet('LISTAS')
        sheet.append(['Tipo de insumo', None, 'Modalidad', None, 'Escrito como', 'Unidad'])
        kinds = ['Material', 'Mano de obra', 'Equipo', 'Subcontrato', 'Herramienta %MO',
                 'Servicio']
        modes = ['Personal propio', 'Contrata solo de mano de obra', 'Contrata a todo costo']
        aliases = self.env['construction.uom.alias'].search([])
        for index in range(max(len(kinds), len(modes), len(aliases))):
            alias = aliases[index] if index < len(aliases) else None
            sheet.append([kinds[index] if index < len(kinds) else None, None,
                          modes[index] if index < len(modes) else None, None,
                          alias.name if alias else None, alias.uom_id.name if alias else None])
        output = io.BytesIO()
        book.save(output)
        return output.getvalue()

    def action_download_template(self):
        self.ensure_one()
        attachment = self.env['ir.attachment'].create({
            'name': 'Libro_APU_presupuesto.xlsx', 'raw': self._template_workbook(),
            'res_model': self._name, 'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/%s?download=true' % attachment.id}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_construction_import_book(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': self.env._(
            'Importar libro de APU y presupuesto'),
            'res_model': 'construction.budget.book.wizard', 'view_mode': 'form',
            'target': 'new', 'context': {'default_sale_order_id': self.id}}
