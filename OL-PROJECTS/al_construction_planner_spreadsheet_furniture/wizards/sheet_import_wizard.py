# -*- coding: utf-8 -*-
"""«Importar Excel a la hoja» (paquete 1.13, M113-04).

Lee un libro con el formato del maestro y lo lleva a las pestañas de la hoja
de trabajo, sin tocar sus fórmulas. El servidor lee el libro, lo analiza con
el importador del maestro (sin escribir en la obra) y prepara las filas por
clave de columna; la hoja las escribe en el navegador (columna de cada clave,
desde _CLAVES o el encabezado) y amplía sus filas si no alcanzan.
"""
import base64
import datetime
import logging
from io import BytesIO

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import (
    SHEETS, norm, sheet_key,
)

from ..models.construction_sheet_parameter import (
    COL_KEY, COL_REASON, COL_VALUE, PARAMETERS_SHEET,
)
from ..models.documents_document import TEMPLATE_ONLY_SHEETS
from ..models.sale_sheet import OBRA_PRELOADED, OBRA_ROW, OBRA_SHEET, SALE_COLUMNS, SALE_ROWS
from ..models.project_project import (
    CATEGORY_SEPARATOR, PICK_SEPARATOR, WORK_MATERIALS_SHEET, category_parts,
)

_logger = logging.getLogger(__name__)

# Pestañas del libro que no se copian aunque no sean del maestro.
SKIPPED_SHEETS = ('LEEME', 'README', 'INSTRUCCIONES')
# Paquete 1.17, M117-03: pestañas que arma la plantilla o el sistema. Traerlas
# como valores fijos dejaría la hoja con las listas y los datos de otra obra.
PLAN_TEMPLATE_SHEETS = TEMPLATE_ONLY_SHEETS + ('VENDIDO',)
# Pestañas de la hoja de venta: un libro suyo no se mezcla con la planificación.
SALE_SHEETS = ('EDIFICIO', 'ACABADOS', 'TARIFARIO', 'PRECIOS', 'METRADO', 'RESUMEN VENTA')
# En la hoja de venta se ignora lo que es de la planificación.
PLAN_DATA_SHEETS = tuple(name.upper() for name in SHEETS if name != 'OBRA') + (
    'MATERIALES OBRA', 'ACABADOS DE OBRA', 'VENDIDO', 'FICHA', 'PROGRAMA', 'CONTROL')


def _other_sheet_action(title):
    """Qué hace la importación con una pestaña que no es del maestro: ``skip``,
    ``template``, ``sale`` o ``copy``."""
    name = norm(title).upper()
    if name in SKIPPED_SHEETS:
        return 'skip'
    if name.startswith('_') or name in {norm(sheet).upper() for sheet in PLAN_TEMPLATE_SHEETS}:
        return 'template'
    return 'sale' if name in SALE_SHEETS else 'copy'


def _cell(value):
    """Texto de una celda para la hoja (o-spreadsheet guarda texto)."""
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        return value.date().isoformat() if not value.time() else value.isoformat(' ')
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() if isinstance(value, str) else str(value)


class ConstructionSpreadsheetImportWizard(models.TransientModel):
    _name = 'construction.spreadsheet.import.wizard'
    _description = 'Importar Excel a la hoja de trabajo'

    document_id = fields.Many2one('documents.document', string='Hoja de trabajo', required=True,
                                  ondelete='cascade')
    project_id = fields.Many2one(related='document_id.construction_project_id', string='Obra')
    file = fields.Binary(string='Archivo (.xlsx)', attachment=False)
    filename = fields.Char(string='Nombre del archivo')
    mode = fields.Selection([
        ('replace', 'Reemplaza las pestañas del archivo'),
        ('append', 'Agrega filas al final'),
    ], string='Cómo escribe', default='replace', required=True)
    expand_rows = fields.Boolean(string='Ampliar las filas si no alcanzan', default=True)
    keep_extra = fields.Boolean(string='Conservar columnas y pestañas que no son del maestro',
                                default=True)
    save_version = fields.Boolean(string='Guardar una versión de la hoja antes de escribir',
                                  default=True)
    review_html = fields.Html(string='Revisión', compute='_compute_review', sanitize=False)

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    @api.model
    def _sheet_columns(self, name):
        """[(clave, [textos aceptados])] de una pestaña: las del maestro y las
        que agrega la hoja (Producto, Grupo de categoría)."""
        # M117-03: de MATERIALES OBRA solo el material; lo demás lo calcula la hoja.
        if name == WORK_MATERIALS_SHEET:
            return [('material', ['Material'])]
        columns = [(key, [header]) for key, header, _r, _h in SHEETS[name][1]]
        keys = {key for key, _t in columns}
        if name in ('PIEZAS', 'BOM'):
            if 'product_name' not in keys:
                columns.append(('product_name', ['Producto']))
            columns.append(('categ_group', ['Grupo de categoría']))
        return columns

    def _read_sale_file(self, workbook):
        """M117-16, punto 2: la hoja de venta lee sus propias pestañas por clave y
        no escribe en las calculadas."""
        sheets, other, ignored, parameters, obra = {}, {}, {}, {}, {}
        for worksheet in workbook.worksheets:
            rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
            title = norm(worksheet.title).upper()
            if title in SKIPPED_SHEETS:
                continue
            if title == 'RESUMEN VENTA' or title.startswith('_') or title in {
                    'INICIO', 'REFERENCIAS', 'ERRORES'}:
                ignored[worksheet.title[:31]] = 'template'
            elif title in PLAN_DATA_SHEETS:
                ignored[worksheet.title[:31]] = 'plan'
            elif title == PARAMETERS_SHEET:
                header = [norm(value) for value in (rows[0] if rows else [])]
                key_col = header.index(norm('Clave')) if norm('Clave') in header else (
                    header.index(norm('Clave (calc.)')) if norm('Clave (calc.)') in header
                    else COL_KEY)
                value_col = header.index(norm('Valor')) if norm('Valor') in header else COL_VALUE
                reason_col = header.index(norm('Motivo del cambio')) \
                    if norm('Motivo del cambio') in header else COL_REASON
                parameters = {row[key_col]: [_cell(row[value_col]), _cell(
                    row[reason_col]) if len(row) > reason_col else '']
                    for row in rows[1:] if len(row) > key_col and row[key_col]}
            elif title == OBRA_SHEET:
                for row in rows[1:]:
                    if row and row[0] in OBRA_ROW and row[0] not in OBRA_PRELOADED \
                            and len(row) > 1 and row[1] not in (None, ''):
                        obra[row[0]] = _cell(row[1])
            elif title in SALE_COLUMNS:
                columns = {norm(column[1]): column[0] for column in SALE_COLUMNS[title]
                           if not column[4]}
                header = rows[0] if rows else []
                positions = {columns[norm(text)]: index for index, text in enumerate(header)
                             if norm(text) in columns}
                data = [[_cell(row[index]) if index < len(row) else ''
                         for index in positions.values()] for row in rows[1:]
                        if any(value not in (None, '') for value in row)]
                limit = self.document_id.construction_sheet_rows or SALE_ROWS
                if len(data) > limit:
                    raise UserError(self.env._(
                        '%(sheet)s trae %(rows)s filas y esta hoja admite %(max)s: use Hoja de '
                        'venta › Ampliar filas.', sheet=title, rows=len(data), max=limit))
                sheets[title] = {
                    'keys': list(positions), 'rows': data, 'extra_headers': [], 'extra_rows': [],
                    'headers': {column[0]: [column[1]] for column in SALE_COLUMNS[title]}}
            elif rows:
                other[worksheet.title[:31]] = [[_cell(value) for value in row] for row in rows]
        workbook.close()
        return {'sheets': sheets, 'other': other, 'ignored': ignored, 'parameters': parameters,
                'obra': obra}

    def _read_file(self):
        """``{'sheets': {pestaña: {'keys', 'rows', 'extra_headers',
        'extra_rows'}}, 'other': {pestaña: filas}, 'ignored': {pestaña:
        'template' o 'sale'}}``."""
        self.ensure_one()
        if not self.file:
            return {'sheets': {}, 'other': {}, 'ignored': {}, 'parameters': {}}
        content = self._file_content()
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(BytesIO(base64.b64decode(content)), read_only=True,
                                     data_only=True)
        except Exception as exc:  # noqa: BLE001 - cualquier archivo que no sea un libro
            _logger.info('Libro no válido para la hoja de trabajo: %s', exc)
            raise UserError(self.env._('El archivo no es un libro Excel (.xlsx) válido.')) \
                from exc
        if self.document_id.construction_sheet_kind == 'sale':
            return self._read_sale_file(workbook)
        sheets, other, ignored, parameters = {}, {}, {}, {}
        for worksheet in workbook.worksheets:
            rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
            while rows and not any(value not in (None, '') for value in rows[-1]):
                rows.pop()
            name = sheet_key(worksheet.title)
            if not name and norm(worksheet.title) == norm(WORK_MATERIALS_SHEET):
                name = WORK_MATERIALS_SHEET
            # M117-15: los parámetros se importan por su clave, sin mover filas.
            if not name and norm(worksheet.title) == norm(PARAMETERS_SHEET):
                parameters = {
                    row[COL_KEY]: [_cell(row[COL_VALUE]),
                                   _cell(row[COL_REASON]) if len(row) > COL_REASON else '']
                    for row in rows[1:] if len(row) > COL_KEY and row[COL_KEY]}
                continue
            if not name:
                action = _other_sheet_action(worksheet.title)
                if action in ('template', 'sale'):
                    ignored[worksheet.title[:31]] = action
                elif action == 'copy' and rows:
                    other[worksheet.title[:31]] = [[_cell(v) for v in row] for row in rows]
                continue
            header = rows[0] if rows else []
            by_text = {}
            for key, texts in self._sheet_columns(name):
                for text in [key] + texts:
                    by_text.setdefault(norm(text), key)
            positions, extra = {}, []
            for index, text in enumerate(header):
                key = by_text.get(norm(text))
                if key and key not in positions:
                    positions[key] = index
                # Las columnas calculadas de otra hoja no son trazabilidad: la
                # plantilla ya las calcula.
                elif text not in (None, '') and not str(text).strip().endswith('(calc.)'):
                    extra.append(index)
            keys = list(positions)
            data_rows, extra_rows = [], []
            for row in rows[1:]:
                if not any(value not in (None, '') for value in row):
                    continue
                data_rows.append([_cell(row[positions[key]]) if positions[key] < len(row)
                                  else '' for key in keys])
                extra_rows.append([_cell(row[i]) if i < len(row) else '' for i in extra])
            texts = dict(self._sheet_columns(name))
            sheets[name] = {'keys': keys, 'rows': data_rows,
                            'headers': {key: texts.get(key, [key]) for key in keys},
                            'extra_headers': [_cell(header[i]) for i in extra],
                            'extra_rows': extra_rows}
        workbook.close()
        return {'sheets': sheets, 'other': other, 'ignored': ignored, 'parameters': parameters}

    def _file_content(self):
        """El archivo en base64. En el formulario (registro nuevo) se lee tal
        cual: leerlo con otro contexto le quitaba el archivo al formulario. Ya
        guardado, sin ``bin_size`` (el cliente web relee con el tamaño)."""
        self.ensure_one()
        if not isinstance(self.id, int):
            return self.file
        return self.with_context(bin_size=False).file

    def _company(self):
        return self.project_id.company_id or self.env.company

    def _prepare(self, data):
        """El producto como lo elige la hoja («nombre · unidad · código»), su
        categoría y grupo si el archivo no los trae, y los códigos que no
        están en el maestro en PRODUCTOS NUEVOS."""
        sheets = data['sheets']
        codes = set()
        for name in ('PIEZAS', 'BOM'):
            spec = sheets.get(name)
            if spec and 'product_code' in spec['keys']:
                index = spec['keys'].index('product_code')
                codes |= {row[index] for row in spec['rows'] if row[index]}
        company = self._company()
        products = {}
        for product in self.env['product.product'].with_context(active_test=False).search([
                ('default_code', 'in', list(codes)), ('company_id', 'in', (company.id, False))]):
            products.setdefault(product.default_code, product)
        new_spec = sheets.get('PRODUCTOS NUEVOS')
        new_codes = set()
        if new_spec and 'code' in new_spec['keys']:
            index = new_spec['keys'].index('code')
            new_codes = {row[index] for row in new_spec['rows']}
        added = []
        for name in ('PIEZAS', 'BOM'):
            spec = sheets.get(name)
            if not spec or 'product_code' not in spec['keys']:
                continue
            for key in ('product_name', 'categ', 'categ_group'):
                if key not in spec['keys']:
                    spec['keys'].append(key)
                    spec['headers'][key] = dict(self._sheet_columns(name)).get(key, [key])
                    for row in spec['rows']:
                        row.append('')
            index = {key: i for i, key in enumerate(spec['keys'])}
            for row in spec['rows']:
                code = row[index['product_code']]
                if not code:
                    continue
                product = products.get(code)
                if product:
                    row[index['product_name']] = PICK_SEPARATOR.join(
                        [product.name, product.uom_id.name or '', code])
                    group, short, _last = category_parts(product.categ_id.complete_name)
                    if not row[index['categ']]:
                        row[index['categ']] = short
                    elif CATEGORY_SEPARATOR not in row[index['categ']] and \
                            row[index['categ']] == _last:
                        row[index['categ']] = short
                    if not row[index['categ_group']]:
                        row[index['categ_group']] = group
                    continue
                # Código que no está en el maestro: queda como texto y va a
                # PRODUCTOS NUEVOS con el nombre del archivo.
                name_text = row[index['product_name']]
                row[index['product_name']] = code
                if code not in new_codes:
                    new_codes.add(code)
                    added.append([code, name_text if name_text and name_text != code else code])
        if added:
            spec = sheets.setdefault('PRODUCTOS NUEVOS', {
                'keys': ['code', 'name'], 'rows': [], 'extra_headers': [], 'extra_rows': [],
                'headers': dict(self._sheet_columns('PRODUCTOS NUEVOS'))})
            for key in ('code', 'name'):
                if key not in spec['keys']:
                    spec['keys'].append(key)
                    spec['headers'][key] = dict(self._sheet_columns('PRODUCTOS NUEVOS'))[key]
                    for row in spec['rows']:
                        row.append('')
            index = {key: i for i, key in enumerate(spec['keys'])}
            for code, name in added:
                row = [''] * len(spec['keys'])
                row[index.get('code', 0)] = code
                if 'name' in index:
                    row[index['name']] = name
                spec['rows'].append(row)
                spec['extra_rows'].append([''] * len(spec['extra_headers']))
        data['added_products'] = len(added)
        return data

    def _analysis(self):
        """Errores y avisos del importador del maestro sobre el archivo, sin
        escribir en la obra."""
        self.ensure_one()
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': self.project_id.id, 'file': self._file_content(),
            'filename': self.filename, 'create_missing_products': True})
        # Sin unlink: borrar dentro del cálculo de la revisión limpia la caché
        # y el formulario perdía el archivo; el transitorio se limpia solo.
        data = wizard._analyze()
        return wizard._construction_issues(data)

    @api.depends('file', 'mode', 'keep_extra')
    def _compute_review(self):
        for wizard in self:
            if not wizard.file or not wizard.document_id:
                wizard.review_html = False
                continue
            try:
                data = wizard._read_file()
            except UserError as error:
                wizard.review_html = Markup('<div class="alert alert-danger">%s</div>') % \
                    error.args[0]
                continue
            lines = []
            for name, spec in data['sheets'].items():
                lines.append(Markup(
                    '<tr><td>%s</td><td class="text-end">%s</td><td>%s</td><td>%s</td>'
                    '<td>%s</td></tr>') % (
                    name, len(spec['rows']), len(spec['keys']),
                    ', '.join(h for h in spec['extra_headers'] if h) or '—',
                    self.env._('Importa por clave')))
            for name, rows in data['other'].items():
                lines.append(Markup(
                    '<tr><td>%s</td><td class="text-end">%s</td><td>—</td><td>—</td>'
                    '<td>%s</td></tr>') % (
                    name, max(len(rows) - 1, 0),
                    self.env._('Se copia') if wizard.keep_extra
                    else self.env._('No se copia')))
            if data['parameters']:
                lines.append(Markup(
                    '<tr><td>%s</td><td class="text-end">%s</td><td>2</td><td>—</td>'
                    '<td>%s</td></tr>') % (PARAMETERS_SHEET, len(data['parameters']),
                                           self.env._('Importa por clave')))
            if data.get('obra'):
                lines.append(Markup(
                    '<tr><td>OBRA</td><td class="text-end">%s</td><td>2</td><td>—</td>'
                    '<td>%s</td></tr>') % (len(data['obra']), self.env._('Importa por clave')))
            reasons = {'template': self.env._('Ignorada: es de la plantilla'),
                       'plan': self.env._('Ignorada: es de la hoja de planificación'),
                       'sale': self.env._('Ignorada: es de la hoja de venta')}
            for name, action in data['ignored'].items():
                lines.append(Markup(
                    '<tr class="text-muted"><td>%s</td><td class="text-end">—</td><td>—</td>'
                    '<td>—</td><td>%s</td></tr>') % (name, reasons[action]))
            is_sale = wizard.document_id.construction_sheet_kind == 'sale'
            issues = wizard._analysis() if data['sheets'] and not is_sale else []
            errors = sum(1 for issue in issues if issue[4] == 'error')
            warnings = len(issues) - errors
            wizard.review_html = Markup(
                '<table class="table table-sm o_main_table"><thead><tr><th>%s</th>'
                '<th class="text-end">%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead>'
                '<tbody>%s</tbody></table><p class="%s">%s</p>') % (
                self.env._('Pestaña'), self.env._('Filas'), self.env._('Columnas reconocidas'),
                self.env._('Columnas extra'), self.env._('Acción'), Markup('').join(lines),
                'text-danger' if errors else 'text-muted',
                self.env._('Análisis del maestro: %(errors)s errores · %(warnings)s avisos '
                           '(el detalle queda en ERRORES al importar).',
                           errors=errors, warnings=warnings))

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_review(self):
        """«Solo revisar»: vuelve a mostrar el asistente con la revisión, sin
        cambiar la hoja."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
            'name': self.env._('Importar Excel a la hoja'),
        }

    def action_import(self):
        """Guarda una versión (si se pidió) y entrega a la hoja lo que debe
        escribir; la hoja lo escribe al cerrarse el asistente."""
        self.ensure_one()
        if not self.file:
            raise UserError(self.env._('Suba el archivo .xlsx.'))
        data = self._read_file()
        is_sale = self.document_id.construction_sheet_kind == 'sale'
        if is_sale:
            data['added_products'] = 0
        else:
            data = self._prepare(data)
        if not data['sheets'] and not data['other'] and not data.get('obra') \
                and not data['parameters']:
            raise UserError(self.env._(
                'El archivo no tiene ninguna pestaña del maestro (%s).', ', '.join(SHEETS)))
        if self.save_version:
            self.document_id._construction_save_version(
                self.env._('Antes de importar %s', self.filename or self.env._('un Excel')))
        payload = {
            'filename': self.filename or '',
            'mode': self.mode,
            'expand_rows': self.expand_rows and not is_sale,
            'obra': data.get('obra') or {},
            'sheets': data['sheets'],
            'other': data['other'] if self.keep_extra else {},
            'ignored': list(data['ignored']),
            'parameters': data['parameters'],
            'keep_extra': self.keep_extra,
            'added_products': data['added_products'],
        }
        return {'type': 'ir.actions.act_window_close',
                'infos': {'construction_sheet_import': payload}}
