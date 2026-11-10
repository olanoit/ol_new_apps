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
from odoo.tools import float_round
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import budget_code_levels, norm

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
        # Paquete 1.16, CR-22 g: el insumo se elige por nombre en la hoja de
        # trabajo; el código se calcula de esta columna (informativa).
        ('pick', ('Insumo: escriba tipo o nombre',), False),
        # Paquete 4 de CREVAL, CR-31: lo entrega el cliente (Sí o vacío).
        ('client_supply', ('Suministro del cliente',), False),
    ],
    # Columnas A a W del libro 6.6 con «Costo unitario sin APU» (CR-18, c y
    # D1), en el orden de la hoja; las de PRESUPUESTO_FORMULAS son fórmulas.
    'PRESUPUESTO': [
        ('item', ('Ítem', 'Item'), False),
        ('specialty', ('Especialidad',), False),
        ('subspecialty', ('Sub-especialidad', 'Subespecialidad'), False),
        ('name', ('Partida',), True),
        ('apu', ('Código del APU', 'Codigo del APU', 'APU'), False),
        ('cost_no_apu', ('Costo unitario sin APU',), False),
        ('uom', ('Unidad',), False),
        ('mode', ('Modalidad de ejecución', 'Modalidad'), False),
        ('qty_real', ('Metrado real',), True),
        ('qty_slack_pct', ('Holgura de metrado (%)', 'Holgura de metrado %'), False),
        ('qty_slack', ('Holgura de metrado (cantidad)', 'Holgura de metrado'), False),
        ('qty_offered', ('Metrado ofertado',), False),
        ('unit_cost', ('Costo unitario',), False),
        ('cost_slack_pct', ('Holgura de costo (%)', 'Holgura de costo %'), False),
        ('cost_slack', ('Holgura de costo (monto)', 'Holgura de costo'), False),
        ('cost_offered', ('Costo unitario ofertado',), False),
        ('margin_pct', ('Margen (%)', 'Margen %'), False),
        ('margin', ('Margen (monto)', 'Margen'), False),
        ('price_unit', ('Precio unitario',), False),
        ('cost_real', ('Costo real',), False),
        ('amount_offered', ('Costo ofertado',), False),
        ('subtotal', ('Parcial de venta',), False),
        ('reserve', ('Reserva por holguras',), False),
        # Paquete 1.16, M116-05: cuenta analítica compartida de los dos
        # primeros niveles (catálogo), al final para no mover las fórmulas.
        ('specialty_catalog', ('Especialidad (catálogo)', 'Especialidad (catalogo)'), False),
        ('subspecialty_catalog', ('Sub-especialidad (catálogo)', 'Sub-especialidad (catalogo)',
                                  'Subespecialidad (catálogo)'), False),
    ],
}
# Columnas de PRESUPUESTO que son fórmulas (gris); la unidad lo es solo con APU.
PRESUPUESTO_FORMULAS = ('qty_offered', 'unit_cost', 'cost_offered', 'price_unit', 'cost_real',
                        'amount_offered', 'subtotal', 'reserve')
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
YES_TEXTS = ('si', 'sí', 'x', '1', 'yes', 'true', 'verdadero')
COLUMN_LABELS = {key: aliases[0] for columns in COLUMNS.values()
                 for key, aliases, _required in columns}
FORMULA_ERRORS = ('#REF!', '#DIV/0!', '#VALUE!', '#N/A', '#NAME?', '#NUM!', '#NULL!')
# Líneas del pie que no son partidas (CR-12): nombre de la línea y signo.
FOOTER_LINES = (
    ('overhead_pct', 'Gastos generales', 1),
    ('contingency_pct', 'Imprevistos', 1),
    ('profit_pct', 'Utilidad', 1),
    ('discount_pct', 'Descuento', -1),
)


def _date(value):
    """Fecha de una celda (fecha, número de serie de la hoja o texto)."""
    from datetime import date, datetime, timedelta
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and value > 0:
        return date(1899, 12, 30) + timedelta(days=int(value))
    text = _text(value)
    for pattern in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return False



def _column_letter(index):
    """Letra de la columna ``index`` (0 → A)."""
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters

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
    can_send = fields.Boolean(readonly=True, help='La revisión no encontró errores.')
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
    def _sheet_rows(self, rows, sheet, errors, broken=None):
        """Filas de una hoja con encabezados: [{clave: valor, '_row': n}].

        Paquete 4 de CREVAL, CR-29: una columna obligatoria que falta da un
        solo error (la hoja queda marcada en ``broken`` para no
        encadenar errores en las que la usan), y toda celda con una fórmula
        rota (#REF!…) de la fila se informa, también en las columnas de
        cálculo que el envío no lee."""
        columns = COLUMNS[sheet]
        best = (-1, None, {}, [])
        for position, row in enumerate(rows[:10]):
            names = [norm(_text(cell)) for cell in row]
            index = {}
            for key, aliases, _required in columns:
                # La clave interna de la columna también vale como encabezado:
                # la hoja de trabajo la pone al enviar (paquete 1.16, M116-09).
                for alias in (key,) + tuple(aliases):
                    if norm(alias) in names:
                        index[key] = names.index(norm(alias))
                        break
            if all(key in index for key, _aliases, required in columns if required):
                headers = list(row)
                break
            if len(index) > best[0]:
                best = (len(index), position, index, row)
        else:
            index = best[2]
            for key, aliases, required in columns:
                if required and key not in index:
                    errors.append((sheet, 1, key, self.env._(
                        'Falta la columna obligatoria «%(column)s» en %(sheet)s.',
                        column=aliases[0], sheet=sheet)))
            if broken is not None:
                broken.add(sheet)
            return []
        result = []
        for number, row in enumerate(rows[position + 1:], start=position + 2):
            values = {key: row[i] if i < len(row) else None for key, i in index.items()}
            if not any(_text(value) for value in values.values()):
                continue
            by_column = {i: key for key, i in index.items()}
            for i, value in enumerate(row):
                if isinstance(value, str) and value.strip().upper() in FORMULA_ERRORS:
                    column = by_column.get(i) or (_text(headers[i]) if i < len(headers) else '') \
                        or _column_letter(i)
                    errors.append((sheet, number, column, self.env._(
                        'La fórmula da error (%s): revise si se borró una columna o una '
                        'pestaña que usa.', value.strip())))
            values['_row'] = number
            result.append(values)
        return result

    def _uom(self, text):
        """Unidad de un texto: una equivalencia («Escrito como») o el nombre
        de una unidad de Odoo en cualquiera de los idiomas instalados (CR-18,
        b: la hoja puede traer «Hours» o «Horas»)."""
        text = _text(text)
        if not text:
            return self.env['uom.uom']
        uom = self.env['construction.uom.alias']._find(text, self.company_id)
        if uom:
            return uom
        # Los nombres en todos los idiomas, una vez por transacción.
        names = self.env.cr.cache.get('construction_uom_names')
        if names is None:
            names = {}
            UoM = self.env['uom.uom'].with_context(active_test=False)
            for lang, _name in self.env['res.lang'].get_installed():
                for record in UoM.with_context(lang=lang).search([]):
                    names.setdefault(norm(record.name), record.id)
            self.env.cr.cache['construction_uom_names'] = names
        return self.env['uom.uom'].browse(names.get(norm(text), []))

    def _parse(self, content=None):
        """El libro como datos y la lista de errores y avisos:
        ``(book, errors, warnings)``; cada error es (hoja, fila, columna,
        mensaje)."""
        self.ensure_one()
        sheets = self._load_book(content or base64.b64decode(self.file))
        errors, warnings = [], []
        broken = set()
        for name in ('INSUMOS', 'APU', 'APU_DETALLE', 'PRESUPUESTO'):
            if name not in sheets:
                errors.append((name, 0, '', self.env._('Falta la hoja %s.', name)))
        if errors:
            return {}, errors, warnings
        book = {'obra': {}, 'aliases': [], 'insumos': {}, 'apus': {}, 'partidas': [],
                'titles': {}}
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

        for row in self._sheet_rows(sheets['INSUMOS'], 'INSUMOS', errors, broken):
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
        for row in self._sheet_rows(sheets['APU'], 'APU', errors, broken):
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
        for row in self._sheet_rows(sheets['APU_DETALLE'], 'APU_DETALLE', errors, broken):
            apu, code = _text(row.get('apu')), _text(row.get('code'))
            if apu not in book['apus']:
                if 'APU' not in broken:
                    errors.append(('APU_DETALLE', row['_row'], 'apu', self.env._(
                        'El APU %s no existe en la hoja APU.', apu)))
                continue
            if code not in book['insumos']:
                if 'INSUMOS' not in broken:
                    errors.append(('APU_DETALLE', row['_row'], 'code', self.env._(
                        'El insumo %s no existe en la hoja INSUMOS.', code)))
                continue
            book['apus'][apu]['lines'].append({
                'insumo': code, 'crew': _number(row.get('crew')), 'pct': _number(row.get('pct')),
                'qty': _number(row.get('qty')), 'price': _number(row.get('price')),
                'stage': _text(row.get('stage')),
                'client_supply': norm(_text(row.get('client_supply'))) in YES_TEXTS,
                'row': row['_row']})
        items = defaultdict(int)
        for row in self._sheet_rows(sheets['PRESUPUESTO'], 'PRESUPUESTO', errors, broken):
            apu = _text(row.get('apu'))
            if apu and apu not in book['apus']:
                if 'APU' not in broken:
                    errors.append(('PRESUPUESTO', row['_row'], 'apu', self.env._(
                        'El APU %s no existe en la hoja APU.', apu)))
                continue
            item = _text(row.get('item'))
            cost_no_apu = _number(row.get('cost_no_apu'))
            cost_real = _number(row.get('cost_real'))
            # Fila de título (paquete 1.16, M116-11): ítem y nombre, sin APU,
            # unidad, metrado ni costo. Agrupa las filas cuyo código cuelga
            # del suyo (especialidad, sub-especialidad, partida sin APU).
            if item and not apu and not _text(row.get('uom')) and not _number(
                    row.get('qty_real')) and cost_no_apu is None and cost_real is None:
                book['titles'][item] = _text(row.get('name')) or item
                book.setdefault('title_rows', {})[item] = row['_row']
                catalog = _text(row.get('specialty_catalog')) or _text(
                    row.get('subspecialty_catalog'))
                if catalog:
                    book.setdefault('title_catalog', {})[item] = catalog
                continue
            if item:
                items[item] += 1
            mode_text = norm(_text(row.get('mode')))
            # D1: sin receta, el costo lo escribe el presupuestador; nunca se
            # envía un 0 por falta de dato.
            if not apu and cost_no_apu is None and cost_real is None:
                errors.append(('PRESUPUESTO', row['_row'], 'cost_no_apu', self.env._(
                    'Partida %s: sin código de APU ni costo unitario.',
                    item or _text(row.get('name')))))
            book['partidas'].append({
                'cost_no_apu': cost_no_apu,
                'catalog': [_text(row.get('specialty_catalog')),
                            _text(row.get('subspecialty_catalog'))],
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
                'cost_real': cost_real, 'row': row['_row']})
        for item, count in items.items():
            if count > 1:
                warnings.append(self.env._('El ítem %(item)s aparece %(count)s veces.',
                                           item=item, count=count))
        # PLAN (hoja de trabajo, 6.7): modalidad final y fechas por partida.
        book['plan'] = {}
        plan_rows = sheets.get('PLAN', [])
        if plan_rows:
            names = [norm(_text(cell)) for cell in plan_rows[0]]
            index = {key: names.index(norm(header)) for key, header in (
                ('item', 'Ítem'), ('mode', 'Modalidad final'), ('start', 'Inicio'),
                ('end', 'Fin')) if norm(header) in names}
            for number, row in enumerate(plan_rows[1:], start=2):
                item = _text(row[index['item']]) if 'item' in index and \
                    index['item'] < len(row) else ''
                if not item:
                    continue
                mode_text = norm(_text(row[index['mode']])) if 'mode' in index and \
                    index['mode'] < len(row) else ''
                if mode_text and mode_text not in MODES:
                    errors.append(('PLAN', number, 'mode', self.env._(
                        'La modalidad «%s» no es válida.', _text(row[index['mode']]))))
                book['plan'][item] = {
                    'mode': MODES.get(mode_text),
                    'start': _date(row[index['start']]) if 'start' in index and
                    index['start'] < len(row) else False,
                    'end': _date(row[index['end']]) if 'end' in index and
                    index['end'] < len(row) else False,
                }
        # CR-30: el nombre de cada nivel de la ruta, de la fila que lo da (el
        # título o las columnas Especialidad y Sub-especialidad de cualquier
        # partida), para que el nodo sea uno por código.
        level_names = {}
        for partida in book['partidas']:
            codes = budget_code_levels(partida['item'])[:-1]
            for depth, column in enumerate(('specialty', 'subspecialty')):
                if depth < len(codes) and partida[column]:
                    level_names.setdefault(codes[depth], partida[column])
        book['level_names'] = level_names
        # Paquete 4 de CREVAL, CR-29 y CR-30: lo que hoy solo detectaba el
        # envío.
        errors += self._check_contract_activities(book)
        errors += self._check_catalog_accounts(book)
        warnings += self._check_level_names(book)
        unnumbered = [p for p in book['partidas'] if not p['item']]
        if unnumbered:
            warnings.append(self.env._('%s partidas sin número de ítem.', len(unnumbered)))
        if self.target == 'plan' and not self.project_id:
            errors.append(('OBRA', 0, '', self.env._(
                'El destino Plan necesita la obra de la cotización.')))
        # D3: con la cotización confirmada, precio y metrado ofertado van por
        # cambio de obra.
        if self.target == 'budget' and self.sale_order_id._construction_offer_locked() and \
                not self.env.context.get('construction_validate_only'):
            errors.append(('OBRA', 0, '', self.env._(
                'La cotización está confirmada: los cambios de precio o metrado ofertado van por '
                'cambio de obra.')))
        if not errors and book['partidas'] and \
                self.currency_id.is_zero(self._book_direct_cost(book)):
            errors.append(('PRESUPUESTO', 0, '', self.env._('El costo directo de la hoja es 0.')))
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
        self.can_send = not errors
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
            body += self._changes_html(book)
        self.write({'state': 'preview', 'preview_html': body, 'has_warnings': bool(warnings),
                    'accept_warnings': False})
        return self._reopen()

    def _partida_offer(self, book, partida):
        """(costo unitario, metrado ofertado, precio unitario) de la partida
        con las fórmulas de la hoja (CR-18, c)."""
        if partida['cost_real'] is not None and partida['qty_real']:
            cost = partida['cost_real'] / partida['qty_real']
        elif partida['apu']:
            cost = self._apu_unit_cost(book, book['apus'][partida['apu']])
        else:
            cost = partida['cost_no_apu'] or 0.0
        qty = partida['qty_real'] * (1 + partida['qty_slack_pct'] / 100.0) + partida['qty_slack']
        offered = cost * (1 + partida['cost_slack_pct'] / 100.0) + partida['cost_slack']
        price = offered * (1 + partida['margin_pct'] / 100.0) + partida['margin']
        return cost, qty, price

    def _changes_html(self, book):
        """Vista previa por partida (CR-18, e): precio y metrado actuales y
        nuevos; en rojo las que bajan a 0 o cambian más del porcentaje de la
        compañía. Con la cotización confirmada, el cambio de precio o de
        metrado ofertado va por cambio de obra (D3)."""
        order = self.sale_order_id
        locked = order._construction_offer_locked()
        limit = self.company_id.construction_sheet_change_pct or 0.0
        by_item = {line.construction_budget_item: line for line in order.order_line
                   if line.construction_budget_item and not line.display_type}
        uom_digits = self.env['decimal.precision'].precision_get('Product Unit')
        rows, flagged = [], 0

        def changed(old, new):
            if not old:
                return bool(new)
            return abs(new - old) / abs(old) * 100.0 > limit

        for partida in book['partidas']:
            _cost, qty, price = self._partida_offer(book, partida)
            line = by_item.get(partida['item']) if partida['item'] else False
            old_qty = line.product_uom_qty if line else 0.0
            old_price = line.price_unit if line else 0.0
            notes = []
            red = self.currency_id.is_zero(price) or (line and (
                changed(old_price, price) or changed(old_qty, qty)))
            if not line:
                notes.append(self.env._('Nueva') if not locked else
                             self.env._('Nueva: va por cambio de obra'))
            elif locked and (self.currency_id.compare_amounts(old_price, price) or
                             round(old_qty - qty, uom_digits)):
                notes.append(self.env._('Va por cambio de obra'))
            if self.currency_id.is_zero(price):
                notes.append(self.env._('Precio 0'))
            flagged += bool(red)
            rows.append(Markup(
                '<tr class="%s"><td>%s</td><td>%s</td><td class="text-end">%s</td>'
                '<td class="text-end">%s</td><td class="text-end">%s</td>'
                '<td class="text-end">%s</td><td>%s</td></tr>') % (
                'text-danger fw-bold' if red else '', partida['item'] or '', partida['name'],
                round(old_qty, uom_digits) if line else '', round(qty, uom_digits),
                self.currency_id.format(old_price) if line else '',
                self.currency_id.format(price), ', '.join(notes)))
        header = Markup(
            '<p class="mt-2 mb-1">%s</p><table class="table table-sm o_construction_changes">'
            '<thead><tr><th>%s</th><th>%s</th><th class="text-end">%s</th>'
            '<th class="text-end">%s</th><th class="text-end">%s</th><th class="text-end">%s</th>'
            '<th>%s</th></tr></thead><tbody>') % (
            self.env._('%(count)s partidas; %(flagged)s en rojo (bajan a 0 o cambian más de '
                       '%(limit)s %%).', count=len(rows), flagged=flagged, limit=round(limit, 2)),
            self.env._('Ítem'), self.env._('Partida'), self.env._('Metrado actual'),
            self.env._('Metrado nuevo'), self.env._('Precio actual'), self.env._('Precio nuevo'),
            self.env._('Nota'))
        return header + Markup('').join(rows) + Markup('</tbody></table>')

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    def _partida_mode(self, book, partida):
        """Modalidad efectiva de la partida: la de PLAN, la de la fila o la
        del APU."""
        apu = book['apus'].get(partida['apu']) or {}
        return (book.get('plan', {}).get(partida['item']) or {}).get('mode') \
            or partida['mode'] or apu.get('mode') or 'own'

    def _check_contract_activities(self, book):
        """CR-29 a): un APU de una partida en contrata (solo mano de obra o a
        todo costo) necesita la actividad de la contrata: un insumo de tipo
        contrata en su detalle o la actividad que ya tiene la receta en Odoo."""
        Template = self.env['construction.execution.template']
        modes = dict(self.env['project.task']._fields[
            'construction_execution_mode']._description_selection(self.env))
        errors, seen = [], set()
        for partida in book['partidas']:
            code = partida['apu']
            if not code or code in seen or code not in book['apus']:
                continue
            mode = self._partida_mode(book, partida)
            if mode not in ('labor_contract', 'full_contract'):
                continue
            apu = book['apus'][code]
            if any(book['insumos'].get(line['insumo'], {}).get('kind') == 'contract'
                   for line in apu['lines']):
                continue
            existing = Template.search([
                ('code', '=', code), ('company_id', 'in', (self.company_id.id, False)),
                ('project_id', 'in', (self.project_id.id, False))], limit=1)
            if existing.contract_activity_id:
                continue
            seen.add(code)
            errors.append(('APU', apu['row'], 'mode', self.env._(
                'APU %(apu)s (modalidad «%(mode)s», partida %(item)s): falta la actividad de la '
                'contrata. Agregue en APU_DETALLE un insumo de tipo contrata.',
                apu=code, mode=modes.get(mode, mode), item=partida['item'] or partida['name'])))
        return errors

    def _catalog_levels(self):
        """Niveles de la plantilla de la obra en modo Catálogo con plan
        analítico, por profundidad (solo los dos primeros tienen columna de
        catálogo en la hoja)."""
        template = self.project_id.construction_level_template_id
        levels = template.line_ids.sorted(lambda l: (l.sequence, l.id)) if template else []
        return {depth: level for depth, level in enumerate(levels[:2])
                if level.analytic_mode == 'catalog' and level.analytic_plan_id}

    def _check_catalog_accounts(self, book):
        """CR-29 b): con un nivel en modo Catálogo, cada partida necesita la
        cuenta del catálogo de ese nivel, escrita en la columna de catálogo o
        por el nombre del título."""
        levels = self._catalog_levels()
        if not levels:
            return []
        Task = self.env['project.task']
        columns = {0: COLUMN_LABELS['specialty_catalog'],
                   1: COLUMN_LABELS['subspecialty_catalog']}
        errors, seen = [], set()
        for partida in book['partidas']:
            path = self._partida_path(book, partida)
            catalog = self._partida_catalog(book, partida) or [False, False]
            for depth, level in levels.items():
                if depth >= len(path):
                    continue
                code, name = path[depth]
                key = (depth, code or name)
                if key in seen:
                    continue
                if Task._construction_catalog_account(level, catalog[depth]) or \
                        Task._construction_catalog_account(level, name):
                    continue
                seen.add(key)
                examples = self.env['account.analytic.account'].search(
                    [('plan_id', 'child_of', level.analytic_plan_id.id)], limit=3)
                row = book.get('title_rows', {}).get(code) or partida['row']
                errors.append(('PRESUPUESTO', row, columns[depth], self.env._(
                    '%(level)s %(title)s: no tiene cuenta del catálogo «%(plan)s». Escriba en '
                    '«%(column)s» el código o el nombre de una cuenta del plan%(examples)s.',
                    level=level.name, title=' '.join(filter(None, [code, name])) if name != code
                    else code, plan=level.analytic_plan_id.name, column=columns[depth],
                    examples=(' (%s)' % ', '.join(
                        ' · '.join(filter(None, [a.name, a.code])) for a in examples))
                    if examples else '')))
        return errors

    def _check_level_names(self, book):
        """CR-30: dos filas que dan nombres distintos al mismo código de
        nivel (título y columnas Especialidad o Sub-especialidad)."""
        names = defaultdict(set)
        for code, name in book.get('titles', {}).items():
            if name and name != code:
                names[code].add(name)
        for partida in book['partidas']:
            codes = budget_code_levels(partida['item'])[:-1]
            for depth, column in enumerate(('specialty', 'subspecialty')):
                text = partida[column]
                if depth < len(codes) and text:
                    # «3.90 MUROS» y «MUROS» son el mismo nombre.
                    label = text[len(codes[depth]):].strip() \
                        if text.startswith(codes[depth] + ' ') else text
                    title = book.get('titles', {}).get(codes[depth])
                    if title and title != codes[depth]:
                        title = title[len(codes[depth]):].strip() \
                            if title.startswith(codes[depth] + ' ') else title
                    if label and label != title:
                        names[codes[depth]].add(label)
        warnings = []
        for code, labels in sorted(names.items()):
            clean = {label[len(code):].strip() if label.startswith(code + ' ') else label
                     for label in labels}
            if len(clean) > 1:
                warnings.append(self.env._(
                    'El nivel %(code)s tiene nombres distintos en la hoja: %(names)s. Se usa el '
                    'de su fila de título.', code=code, names=' / '.join(sorted(clean))))
        return warnings

    def _partida_direct_cost(self, book, partida):
        """Costo real de la partida con el redondeo de la línea de la
        cotización (CR-27): el costo unitario a «Product Price» y el importe a
        la moneda."""
        Precision = self.env['decimal.precision']
        if partida['cost_real'] is not None and not partida['qty_real']:
            return self.currency_id.round(partida['cost_real'])
        cost = float_round(self._partida_offer(book, partida)[0],
                           precision_digits=Precision.precision_get('Product Price'))
        qty = float_round(partida['qty_real'] or 0.0,
                          precision_digits=Precision.precision_get('Product Unit'))
        return self.currency_id.round(qty * cost)

    def _book_direct_cost(self, book):
        """Costo directo real del libro: por partida, metrado real × costo
        unitario (del «Costo real», del APU o sin APU), con un solo redondeo
        como la línea de la cotización (CR-27)."""
        return sum(self._partida_direct_cost(book, partida) for partida in book['partidas'])

    def _direct_cost_differences(self, book, lines):
        """Partidas cuyo costo real en la cotización no es el del libro
        (CR-27, punto 3)."""
        by_item = {}
        for line in lines:
            if line.construction_budget_item:
                by_item[line.construction_budget_item] = by_item.get(
                    line.construction_budget_item, 0.0) + line.construction_amount_real
        result = []
        for partida in book['partidas']:
            expected = self._partida_direct_cost(book, partida)
            real = by_item.get(partida['item'])
            if real is None or self.currency_id.compare_amounts(real, expected):
                result.append(self.env._(
                    '%(item)s %(name)s: libro %(book)s, cotización %(real)s',
                    item=partida['item'] or '', name=partida['name'] or '',
                    book=self.currency_id.format(expected),
                    real=self.currency_id.format(real or 0.0)))
        return result

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
                'El libro tiene errores; revíselos con «Revisar» antes de enviar.\n%s',
                '\n'.join(message for _sheet, _row, _col, message in errors[:5])))
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
        # El costo directo de la cotización es el de la hoja (máx. 0.01; 6.7
        # y CR-18, e).
        expected = self._book_direct_cost(book)
        compared = real
        if abs(compared - expected) > 0.011:
            differences = self._direct_cost_differences(book, lines)
            raise UserError(self.env._(
                'El costo directo de la cotización (%(real)s) no es el del libro (%(book)s): '
                'se revierte el envío. Revise los costos del APU y el «Costo real».%(detail)s',
                real=self.currency_id.format(compared), book=self.currency_id.format(expected),
                detail=('\n' + self.env._('Partidas con diferencia:') + '\n'
                        + '\n'.join(differences[:15])) if differences else ''))
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
        project = self.project_id
        if text:
            code = Stage._find_by_text(text)
            if code:
                # Una etapa de otro perfil es error de la fila (1.16, M116-01).
                Stage._check_project_code(code, project, what=text)
                return code
        return self.default_stage_id.code or Stage._default_code(project)

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
                # También entre las archivadas (CR-22 a): se reactiva.
                activity = Activity._construction_get_by_code(
                    code, self.company_id, self.project_id)
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
                if line.get('client_supply'):
                    vals['is_client_supply'] = True
                lines.append(vals)
            recipes[code] = {'name': apu['name'], 'uom': apu['uom'], 'lines': lines}
        # Sin obra, las recetas son de la cotización (D4), no de la biblioteca.
        importer = self.env['construction.recipe.import.wizard'].with_context(
            construction_recipe_sale_order_id=self.sale_order_id.id).create({
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
        if order.state == 'cancel':
            raise UserError(self.env._('El presupuesto no entra a una orden anulada.'))
        # D3: con la cotización confirmada (o bloqueada) solo se actualizan
        # receta, modalidad, metrado real y costos; precio, metrado ofertado y
        # el pie van por cambio de obra.
        locked = order._construction_offer_locked()
        if locked and self.target != 'plan':
            raise UserError(self.env._(
                'La cotización está confirmada: los cambios de precio o metrado ofertado van por '
                'cambio de obra.'))
        Line = self.env['sale.order.line']
        if locked:
            return self._apply_costs_only(book, recipes)
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
        existing = order.order_line
        by_item = {line.construction_budget_item: line for line in existing
                   if line.construction_budget_item and not line.display_type}
        by_title = {(line.display_type, norm(line.name)): line for line in existing
                    if line.display_type in ('line_section', 'line_subsection')}
        sequence = 0
        touched = Line
        section_key = subsection_key = None
        for partida in book['partidas']:
            path = self._partida_path(book, partida)
            names = [name for _code, name in path]
            specialty = partida['specialty'] or (names[0] if names else False)
            subspecialty = partida['subspecialty'] or (names[1] if len(names) > 1 else False)
            for display_type, title, key_attr in (
                    ('line_section', specialty, 'section'),
                    ('line_subsection', subspecialty, 'subsection')):
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
            # El costo del libro manda (el «Costo real» de la partida, las
            # fórmulas del APU sin redondear, CR-03, o el costo sin APU, D1).
            cost_apu = self._partida_offer(book, partida)[0]
            label = ' '.join(filter(None, [partida['item'], partida['name']]))
            # La cotización tiene sección y subsección; los títulos más
            # profundos van en la descripción (M116-11, I-12).
            if len(names) > 2:
                label += '\n' + ' › '.join(names[2:])
            values = {
                'name': label, 'sequence': sequence,
                'construction_budget_item': partida['item'] or False,
                'construction_budget_path': path,
                'construction_budget_catalog': self._partida_catalog(book, partida),
                'construction_qty_real': partida['qty_real'],
                'construction_qty_slack_pct': partida['qty_slack_pct'],
                'construction_qty_slack': partida['qty_slack'],
                'construction_cost_apu': cost_apu,
                'construction_cost_slack_pct': partida['cost_slack_pct'],
                'construction_cost_slack': partida['cost_slack'],
                'construction_margin_pct': partida['margin_pct'],
                'construction_margin_amount': partida['margin'],
                'construction_line_role': 'partida',
                'construction_execution_template_id':
                    recipes[partida['apu']].id if partida['apu'] else False,
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
        self._apply_footer(book, sequence)
        return partidas

    @api.model
    def _partida_catalog(self, book, partida):
        """Catálogo de los dos primeros niveles de la ruta (M116-05): el de
        la fila o, si no lo trae, el de la fila de título de ese nivel."""
        codes = budget_code_levels(partida['item'])[:-1]
        titles = book.get('title_catalog', {})
        catalog = []
        for depth in range(2):
            value = (partida.get('catalog') or [None, None])[depth] or (
                titles.get(codes[depth]) if depth < len(codes) else None)
            catalog.append(value or False)
        return catalog if any(catalog) else False

    @api.model
    def _partida_path(self, book, partida):
        """Ruta de la fila en la hoja, sin ella: [[código, nombre]] de cada
        ancestro. Sale del código de la fila; el nombre, de su fila de título
        o, en los dos primeros niveles, de las columnas Especialidad y
        Sub-especialidad. Sin código, esas dos columnas."""
        codes = budget_code_levels(partida['item'])[:-1]
        fallback = [partida['specialty'], partida['subspecialty']]
        if not codes:
            return [[False, name] for name in fallback if name]
        path = []
        for depth, code in enumerate(codes):
            name = book.get('titles', {}).get(code) or (
                fallback[depth] if depth < len(fallback) else False) or \
                book.get('level_names', {}).get(code) or code
            path.append([code, name])
        return path

    def _apply_costs_only(self, book, recipes):
        """Cotización confirmada (D3): receta, metrado real y costos de las
        partidas que ya están; ni precio, ni metrado ofertado, ni el pie."""
        order = self.sale_order_id
        by_item = {line.construction_budget_item: line for line in order.order_line
                   if line.construction_budget_item and not line.display_type}
        lines = self.env['sale.order.line']
        for partida in book['partidas']:
            line = by_item.get(partida['item']) if partida['item'] else False
            if not line:
                continue
            line.with_context(construction_keep_offer=True).write({
                'construction_qty_real': partida['qty_real'],
                'construction_cost_apu': self._partida_offer(book, partida)[0],
                'construction_execution_template_id':
                    recipes[partida['apu']].id if partida['apu'] else False,
            })
            lines |= line
        return lines

    def _apply_footer(self, book, sequence):
        """Gastos generales, imprevistos y utilidad en % de la suma del
        «Parcial de venta» de las partidas; el descuento, en % de partidas más
        esas tres líneas (CR-18, D2). Cada monto se redondea una vez (CR-11)."""
        order = self.sale_order_id
        product = self._partida_product()
        currency = order.currency_id
        lines = order.order_line.filtered(lambda l: not l.display_type and not l.is_downpayment)
        partidas = sum(lines.filtered(
            lambda l: l.construction_line_role == 'partida').mapped('price_subtotal'))
        before_discount = partidas
        for key, label, sign in FOOTER_LINES:
            pct = _number(book['obra'].get(key))
            role = key[:-len('_pct')]
            line = lines.filtered(lambda l, r=role: l.construction_line_role == r)[:1]
            if pct is None or (not pct and not line):
                if line and role != 'discount':
                    before_discount += line.price_subtotal
                continue
            sequence += 1
            base = before_discount if role == 'discount' else partidas
            values = {'name': '%s %s %%' % (label, round(pct, 4)), 'product_uom_qty': 1.0,
                      'sequence': sequence,
                      'price_unit': currency.round(sign * base * pct / 100.0),
                      'construction_line_role': role}
            if line:
                line.write(values)
            else:
                line = self.env['sale.order.line'].create(dict(values, order_id=order.id,
                                                               product_id=product.id))
            if role != 'discount':
                before_discount += line.price_subtotal

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
        task_dates = {}
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
            planned = book.get('plan', {}).get(line.construction_budget_item) or {}
            mode = planned.get('mode') or (partida or {}).get('mode') or (
                recipe.execution_mode if recipe else False)
            dates = {}
            if planned.get('end'):
                dates['date_deadline'] = planned['end']
            if planned.get('start') and 'planned_date_begin' in task._fields:
                dates['planned_date_begin'] = planned['start']
            if dates:
                task_dates[task] = dates
            if mode:
                task.with_context(construction_plan_force=True).construction_execution_mode = mode
            if recipe:
                tasks |= task
        if tasks:
            # «Reemplazar lo generado» (CR-23): borra lo de la receta y sus
            # copias de la versión anterior; conserva lo manual.
            self.env['construction.plan.recipe.wizard'].create({
                'plan_id': plan.id, 'task_ids': [Command.set(tasks.ids)],
                'mode': 'replace'}).action_generate()
        # Las fechas de la pestaña PLAN, después de generar (el plan propone
        # las suyas).
        for task, dates in task_dates.items():
            task.with_context(construction_plan_force=True).write(dates)
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
