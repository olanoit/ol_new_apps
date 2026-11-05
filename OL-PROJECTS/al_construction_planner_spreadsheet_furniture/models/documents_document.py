# -*- coding: utf-8 -*-
import base64
import json
from io import BytesIO

from markupsafe import Markup, escape

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import (
    SHEETS, norm, sheet_key,
)
from odoo.addons.al_construction_planner_spreadsheet.models.project_project import (
    FURNITURE_LAYOUT,
)
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_keys import KEYS_SHEET

from .construction_sheet_parameter import PARAMETERS_SHEET
from .sale_order import LOCKED_PHASES, SALE_PHASES
from .sale_sheet import (
    FINISHES_SHEET, OBRA_ROW, OBRA_SHEET, RATES_SHEET, SALE_COLUMNS, SALE_ROWS, SUMMARY_SHEET,
)
from .project_project import (
    CALCULATED, DEFAULT_ROWS, FIXED_LISTS, GROUP_HEADER, HEADER_STYLE, PRODUCT_PICK, _col,
)

# Pestañas que arma la plantilla: «Actualizar a la plantilla vigente» no las
# copia de la hoja anterior (las demás, como FUENTES, sí).
SALE_BRING_HEADERS = {
    'TIPOLOGIAS': {'code': 'Código', 'name': 'Nombre', 'family': 'Familia', 'ml_low': 'ML bajo',
                   'ml_high': 'ML alto'},
    'ARBOL': {'group': 'Agrupador', 'floor': 'Piso', 'apartment': 'Departamento',
              'space': 'Ambiente', 'typology': 'Tipología', 'unit_type': 'Tipo de unidad'},
    'CONTRATOS': {'name': 'Contrato', 'partner': 'Cliente', 'advance': 'Adelanto %',
                  'guarantee': 'Fondo de garantía %', 'milestone_template': 'Plantilla de hitos',
                  'discount_factor': 'Factor de descuento', 'invoice_form': 'Forma de la factura'},
    'VENTA': {'contract': 'Contrato', 'typology': 'Tipología', 'price': 'Precio por ambiente'},
    'OBRA': {'key': 'Dato', 'value': 'Valor'},
    'ACABADOS DE OBRA': {'code': 'Código del cliente (calc.)', 'description': 'Descripción (calc.)',
                         'kind': 'Tipo de acabado (calc.)',
                         'material': 'Material de referencia (calc.)'},
    'VENDIDO': {'typology': 'Tipología', 'partida': 'Partida', 'group': 'Grupo', 'ml': 'ML vendidos',
                'structure': 'Acabado estructura', 'fronts': 'Acabado frentes',
                'price': 'Precio por ambiente', 'spaces': 'Ambientes',
                'departments': 'Departamentos'},
}
TEMPLATE_ONLY_SHEETS = ('INICIO', 'LEEME', 'RESUMEN', 'REFERENCIAS', '_LISTAS', 'FICHA',
                        'PROGRAMA', 'CONTROL', 'ERRORES', KEYS_SHEET)


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    construction_sheet_kind = fields.Selection(selection_add=[('sale', 'Hoja de venta')])
    # Paquete 1.17, M117-16: la fase la cambian la cotización y «Nueva versión».
    construction_sale_phase = fields.Selection(
        SALE_PHASES, string='Fase de la hoja de venta', readonly=True, copy=False)
    construction_sale_version = fields.Integer(string='Versión de la hoja de venta', default=1,
                                               readonly=True, copy=False)
    # M117-16, punto 5: la hoja bloqueada no se escribe; al abrirse ya en edición
    # escribe la versión y la fila de cambios, y lo limpia.
    # M117-22: la versión de la venta que ya trajo la hoja de planificación.
    construction_sale_brought = fields.Char(string='Venta traída', readonly=True, copy=False)
    construction_sale_pending = fields.Char(string='Versión por escribir', readonly=True,
                                            copy=False)

    def _get_spreadsheet_metadata(self, access_token=None):
        data = super()._get_spreadsheet_metadata(access_token)
        if data.get('construction_sheet_kind') == 'sale':
            data['construction_sale_phase'] = self.sudo().construction_sale_phase or ''
            data['construction_sale_pending'] = self.sudo().construction_sale_pending or ''
            if self.sudo().construction_sale_order_id:
                data['construction_sale_obra'] = \
                    self.sudo().construction_sale_order_id._construction_sale_obra_values()
            # Una hoja enviada, adjudicada o perdida es de solo lectura.
            if data['construction_sale_phase'] in LOCKED_PHASES:
                data['isReadonly'] = True
            order_sudo = self.sudo().construction_sale_order_id
            if order_sudo:
                # M117-15, punto 7: los valores iniciales vigentes.
                data['construction_parameter_current'] = self.env[
                    'construction.sheet.parameter']._construction_current_values(
                    'sale', order_sudo.company_id, order_sudo._construction_sale_sheet_overrides())
        if data.get('construction_sheet_kind') == 'furniture':
            # M113-08: la ayuda de cada columna para el panel Planificación.
            data['construction_column_help'] = self._construction_column_help()
            # M117-15, punto 7: los valores iniciales vigentes.
            # sudo: solo se leen los valores iniciales de la compañía de la obra.
            document_sudo = self.sudo()
            data['construction_parameter_current'] = self.env[
                'construction.sheet.parameter']._construction_current_values(
                'planning', document_sudo.construction_project_id.company_id or self.env.company)
            # M117-22: la hoja nace con la venta.
            source = document_sudo._construction_sale_source()
            data['construction_sale_available'] = bool(source)
            data['construction_sale_bring_pending'] = bool(source) \
                and not document_sudo.construction_sale_brought
        return data

    def _construction_column_help(self):
        """``{pestaña: {clave o encabezado: [encabezado, ayuda, obligatoria,
        valores]}}`` de las pestañas del maestro (SHEETS) y sus columnas
        calculadas."""
        result = {}
        for name, (_description, columns) in SHEETS.items():
            sheet = result.setdefault(name, {})
            for key, header, required, help_text in columns:
                sheet[key] = [header, help_text, bool(required),
                              FIXED_LISTS.get((name, key), [])]
            if name in PRODUCT_PICK:
                sheet['categ_group'] = [GROUP_HEADER, self.env._(
                    'Elija el grupo y después la categoría: la lista de productos muestra solo '
                    'los de esa categoría, con los materiales de la obra primero.'), False, []]
                sheet['product_name'] = [sheet.get('product_name', ['Producto'])[0], self.env._(
                    'Escriba parte del nombre: la lista filtra al escribir. Se muestra «nombre · '
                    'unidad · código».'), False, []]
            for header, _formula in CALCULATED.get(name, []):
                sheet[header] = [header, self.env._(
                    'Columna calculada (gris): no se escribe.'), False, []]
        return result

    def construction_open_link(self, kind):
        """Enlaces del panel Planificación (M113-08): la obra o el árbol de
        recursos de su plan vigente."""
        self.ensure_one()
        project = self.construction_project_id
        if not project:
            raise UserError(self.env._('La hoja no está vinculada a una obra.'))
        if kind == 'tree':
            return project.action_construction_open_tree()
        return {'type': 'ir.actions.act_window', 'res_model': 'project.project',
                'res_id': project.id, 'view_mode': 'form', 'views': [(False, 'form')]}

    def construction_sheet_upgrade(self, sheets):
        """«Actualizar a la plantilla vigente» (paquete 1.13, M113-07 a 11 en
        las hojas ya creadas): guarda una versión y rehace la hoja con la
        plantilla de hoy (INICIO, FICHA, PROGRAMA, CONTROL, columnas
        calculadas, listas, MATERIALES OBRA) y los datos de la hoja anterior.

        :param sheets: ``{'master': {pestaña: {'rows': [[valor]], 'keys':
            {clave: columna}, 'formula_cols': [columna]}}, 'other': {pestaña:
            {'cells': {ref: contenido}}}}``, lo que lee la hoja en el navegador.
        :return: la acción que abre la hoja actualizada.
        """
        self.ensure_one()
        if self.construction_sheet_kind == 'sale':
            return self._construction_upgrade_sale(sheets)
        if self.construction_sheet_kind != 'furniture' or not self.construction_project_id:
            raise UserError(self.env._('Solo el maestro de mobiliario se actualiza así.'))
        project = self.construction_project_id
        master = (sheets or {}).get('master') or {}
        others = (sheets or {}).get('other') or {}
        needed = max([len(spec.get('rows') or []) for spec in master.values()] + [0])
        rows = max(project.construction_spreadsheet_rows or DEFAULT_ROWS,
                   self.construction_sheet_rows, int(needed * 1.1) + 1, 10)
        self._construction_copy_version(self.env._('Antes de actualizar a la plantilla vigente'))
        data = project._construction_spreadsheet_data(rows)
        layout = project._construction_sheet_layout()
        by_name = {sheet['name']: sheet for sheet in data['sheets']}
        for name, spec in master.items():
            sheet = by_name.get(name)
            if not sheet or name not in layout['sheets']:
                continue
            self._construction_upgrade_master(sheet, layout['sheets'][name], name, spec)
        # M117-15, punto 10: los parámetros nuevos llegan; los valores y motivos
        # ya escritos se conservan.
        self._construction_upgrade_parameters(by_name.get(PARAMETERS_SHEET),
                                              others.get(PARAMETERS_SHEET))
        position = 0
        for name, spec in others.items():
            if name in by_name or name in TEMPLATE_ONLY_SHEETS or name.startswith('_'):
                continue
            position += 1
            data['sheets'].append({
                'id': 'sheet_copy_%s' % position, 'name': name,
                'colNumber': 26, 'rowNumber': max(100, len(spec.get('cells') or {}) + 10),
                'cells': {ref: str(content) for ref, content in (spec.get('cells') or {}).items()
                          if content not in (None, '', False)},
            })
        self.write({
            'datas': base64.b64encode(json.dumps(data).encode()),
            'construction_sheet_rows': rows,
            'construction_sheet_layout': FURNITURE_LAYOUT,
        })
        self._delete_collaborative_data()
        self.construction_project_id.sudo().message_post(
            author_id=self.env.user.partner_id.id, body=self.env._(
                'Hoja de trabajo actualizada a la plantilla vigente (versión anterior guardada).'))
        return self.action_open_spreadsheet()

    @staticmethod
    def _construction_upgrade_parameters(sheet, old):
        """Copia a la pestaña nueva el valor y el motivo de cada clave."""
        if not sheet or not old:
            return
        cells = old.get('cells') or {}
        by_key = {}
        for ref, key in cells.items():
            if ref.startswith('G') and ref[1:].isdigit() and ref != 'G1':
                by_key[key] = ref[1:]
        for ref, key in list(sheet['cells'].items()):
            if not (ref.startswith('G') and ref[1:].isdigit()) or key not in by_key:
                continue
            row, old_row = ref[1:], by_key[key]
            for letter in 'CFH':
                value = cells.get('%s%s' % (letter, old_row))
                if value not in (None, '', False):
                    sheet['cells']['%s%s' % (letter, row)] = str(value)
                elif letter != 'F':
                    sheet['cells'].pop('%s%s' % (letter, row), None)

    @staticmethod
    def _construction_upgrade_master(sheet, info, name, spec):
        """Escribe en la pestaña ``sheet`` de la plantilla las filas de la hoja
        anterior: cada clave en su columna; las columnas que no son del maestro
        ni fórmulas, a la derecha."""
        rows = spec.get('rows') or []
        if len(rows) < 2:
            return
        header = [norm(text) for text in rows[0]]
        old_keys = {key: int(col) for key, col in (spec.get('keys') or {}).items()
                    if isinstance(col, (int, float))}
        formula_cols = set(spec.get('formula_cols') or [])
        letters = dict(info['letters'])
        headers = dict(info['columns'])
        if name == 'MODULOS':
            # M117-24: la clase es calculada; una hoja anterior la tenía de dato.
            letters.pop('module_class', None)
        # El código del producto es fórmula desde «Producto»: no se copia.
        pick = PRODUCT_PICK.get(name)
        if pick:
            letters.pop('product_code', None)
        mapping = {}
        for key, letter in letters.items():
            col = old_keys.get(key)
            if col is None:
                texts = [norm(key), norm(headers.get(key, ''))]
                col = next((index for index, text in enumerate(header) if text in texts), None)
            if col is not None and col not in formula_cols:
                mapping[letter] = col
        used = set(mapping.values()) | formula_cols
        old_code = old_keys.get('product_code')
        if old_code is None and pick:
            old_code = next((index for index, text in enumerate(header)
                             if text in (norm('product_code'), norm('Código del producto'))),
                            None)
        extras = [index for index, text in enumerate(rows[0])
                  if index not in used and index != old_code and str(text or '').strip()]
        cells = sheet['cells']
        first_extra = len(info['headers'])
        for offset, index in enumerate(extras):
            ref = '%s1' % _col(first_extra + offset)
            cells[ref] = str(rows[0][index])
            sheet.setdefault('styles', {})[ref] = HEADER_STYLE
        for number, values in enumerate(rows[1:], start=2):
            for letter, col in mapping.items():
                value = values[col] if col < len(values) else ''
                if value not in (None, '', False):
                    cells['%s%s' % (letter, number)] = str(value)
            # Una hoja anterior al «nombre · unidad · código» trae solo el
            # código: el producto lo toma y la fórmula lo lee igual.
            if pick and old_code is not None and 'product_name' in letters:
                ref = '%s%s' % (letters['product_name'], number)
                code = values[old_code] if old_code < len(values) else ''
                if ref not in cells and code not in (None, '', False):
                    cells[ref] = str(code)
            for offset, index in enumerate(extras):
                value = values[index] if index < len(values) else ''
                if value not in (None, '', False):
                    cells['%s%s' % (_col(first_extra + offset), number)] = str(value)

    def _construction_send_sheet_names(self):
        """Solo las pestañas del maestro y _CLAVES (paquete 1.13, M113-02)."""
        if self.construction_sheet_kind == 'sale':
            return list(SALE_COLUMNS) + [OBRA_SHEET, PARAMETERS_SHEET, SUMMARY_SHEET]
        if self.construction_sheet_kind == 'budget':
            return super()._construction_send_sheet_names()
        return list(SHEETS) + [KEYS_SHEET, PARAMETERS_SHEET, 'VENDIDO', 'ACABADOS DE OBRA']

    def _construction_furniture_workbook(self, sheets):
        """Libro .xlsx (bytes) con las pestañas del maestro de la hoja."""
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.remove(workbook.active)
        for name, rows in (sheets or {}).items():
            if not sheet_key(name):
                continue
            worksheet = workbook.create_sheet(name[:31])
            for row in rows or []:
                worksheet.append([None if value in ('', False) else value for value in row])
        if not workbook.worksheets:
            raise UserError(self.env._('La hoja no tiene ninguna pestaña del maestro.'))
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    def _construction_furniture_wizard(self, sheets, send=False):
        self.ensure_one()
        return self.env['construction.master.import.wizard'].create({
            'project_id': self.construction_project_id.id,
            'file': base64.b64encode(self._construction_furniture_workbook(sheets)),
            'filename': '%s.xlsx' % self.name,
            # Los productos nuevos de la hoja (PRODUCTOS NUEVOS) se crean.
            'create_missing_products': True,
            # M113-11: al importar, guarda la versión enviada de la hoja.
            'spreadsheet_id': self.id if send else False,
        })

    def _construction_send_furniture(self, sheets):
        """Lleva las pestañas del maestro al asistente «Importar maestro y
        ETO» de la obra de la hoja (v1.5, M15-15)."""
        self.ensure_one()
        wizard = self._construction_furniture_wizard(sheets, send=True)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Importar maestro y ETO'),
            'res_model': wizard._name,
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def _construction_validate_furniture(self, sheets):
        """«Validar» del maestro (paquete 1.13, M113-03): el análisis del
        importador, sin escribir, como filas de ERRORES."""
        self.ensure_one()
        if self.construction_sheet_kind == 'sale':
            return self._construction_validate_sale(sheets)
        wizard = self._construction_furniture_wizard(sheets)
        try:
            data = wizard._analyze()
            issues = wizard._construction_issues(data)
        finally:
            wizard.unlink()
        # M117-15, punto 8.
        issues = list(issues) + self.env['construction.sheet.parameter']._construction_issues(
            sheets.get(PARAMETERS_SHEET), 'planning',
            self.construction_project_id.company_id or self.env.company)
        return issues + self._construction_sold_issues(sheets)

    def _construction_sold_issues(self, sheets):
        """M117-22: precio distinto del vendido, y piezas sin tablero (una fila por
        pieza, hasta 200 con una final «y N más»)."""
        sold = {}
        for row in (sheets.get('VENDIDO') or [])[1:]:
            if row and row[0] and len(row) > 6 and row[6] not in ('', None):
                sold[str(row[0])] = row[6]
        issues = []
        if not sold:
            return issues
        for number, row in enumerate(sheets.get('VENTA') or [], start=1):
            if number == 1 or len(row) < 3 or not row[1]:
                continue
            target = sold.get(str(row[1]))
            try:
                differs = target is not None and abs(float(row[2]) - float(target)) > 0.005
            except (TypeError, ValueError):
                differs = False
            if differs:
                issues.append(('VENTA', number, 'Precio por ambiente', self.env._(
                    '%(typology)s: precio distinto del vendido (%(sold)s).',
                    typology=row[1], sold=target), 'warning'))
        pieces = sheets.get('PIEZAS') or []
        if pieces:
            header = list(pieces[0])
            typology_col = header.index('typology') if 'typology' in header else None
            product_col = header.index('product_name') if 'product_name' in header else None
            pending = [number for number, row in enumerate(pieces, start=1)
                       if number > 1 and typology_col is not None and product_col is not None
                       and len(row) > typology_col and row[typology_col]
                       and not (len(row) > product_col and row[product_col])]
            limit = 200
            for number in pending[:limit]:
                issues.append(('PIEZAS', number, 'Producto', self.env._(
                    'Pieza sin tablero: acepte la propuesta o elíjalo.'), 'warning'))
            if len(pending) > limit:
                issues.append(('PIEZAS', '', 'Producto', self.env._(
                    'y %s más', len(pending) - limit), 'warning'))
        return issues

    # ------------------------------------------------------------------
    # «Traer la venta» (M117-22)
    # ------------------------------------------------------------------
    def _construction_sale_source(self):
        """La cotización con hoja de venta adjudicada de la obra de esta hoja."""
        self.ensure_one()
        # Quien planifica puede no tener acceso a la cotización: solo se lee lo
        # que la hoja de venta le pasó.
        order_sudo = self.sudo().construction_project_id.construction_sale_order_id
        if not order_sudo.construction_sale_summary:
            return order_sudo.browse()
        document_sudo = order_sudo._construction_sale_sheet()
        return order_sudo if document_sudo.construction_sale_phase == 'awarded' \
            else order_sudo.browse()

    @staticmethod
    def _construction_tree_rows_from_sale(summary):
        """Cada rango de EDIFICIO en una fila por piso, departamento y ambiente."""
        factor = summary.get('dpto_factor') or 100
        prefixes = dict(item.split('=', 1) for item in (summary.get('pisos_nombre') or '').split(';')
                        if '=' in item)
        rows = []
        for item in summary.get('building', []):
            duplex = str(item.get('duplex') or '') in ('2', '2.0')
            position = int(float(item.get('position') or 0))
            first, last = item.get('from'), item.get('to')
            try:
                floors = range(int(float(first)), int(float(last)) + 1)
            except (TypeError, ValueError):
                floors = None
            unit = 'Nivel de dúplex' if duplex else (item.get('unit_type') or '')
            if floors is None:
                apartment = '%s%02d' % (prefixes.get(first, ''), position)
                rows.append([item.get('group') or '', str(first), 'Dpto %s' % apartment,
                             item.get('space'), item.get('typology') or '', unit])
                continue
            for floor in floors:
                apartment = int(floor * factor + position)
                rows.append([item.get('group') or '', 'Piso %02d' % (floor + 1 if duplex else floor),
                             'Dpto %s' % apartment, item.get('space'),
                             item.get('typology') or '', unit])
        return rows

    def construction_sale_bring(self):
        """Lo que la venta escribe en cada pestaña: ``{'tabs': {pestaña: {'keys',
        'match', 'headers', 'rows'}}, 'warnings': [...], 'version': 'N2'}``."""
        self.ensure_one()
        order_sudo = self._construction_sale_source()
        if not order_sudo:
            raise UserError(self.env._(
                'La obra no tiene una hoja de venta adjudicada con su resumen en la cotización.'))
        summary = order_sudo._construction_sale_summary_data()
        project = self.construction_project_id
        obra = summary.get('obra', {})
        factor = 1.0 if summary.get('prices_without_tax', True) else 1.0 + (summary.get('igv') or 0.0)
        contract = self.env._('Venta %s', order_sudo.name)
        total = sum(item.get('subtotal') or 0.0 for item in summary.get('partidas', []))
        discount = 1 - (summary.get('discount') or 0.0) / total if total else 1.0
        number = lambda value: ('%s' % round(value, 6)) if value else ''

        def headers(name):
            return {key: [text] for key, text in SALE_BRING_HEADERS[name].items()}

        tabs = {
            'TIPOLOGIAS': {'keys': ['code', 'name', 'family', 'ml_low', 'ml_high'], 'match': ['code'],
                           'rows': [[t['code'], t.get('name') or '', t.get('partida') or '',
                                     number(t.get('ml_low')), number(t.get('ml_high'))]
                                    for t in summary.get('typologies', [])]},
            'ARBOL': {'keys': ['group', 'floor', 'apartment', 'space', 'typology', 'unit_type'],
                      'match': ['group', 'floor', 'apartment', 'space'],
                      'rows': self._construction_tree_rows_from_sale(summary)},
            'CONTRATOS': {'keys': ['name', 'partner', 'advance', 'guarantee', 'milestone_template',
                                   'discount_factor', 'invoice_form'], 'match': ['name'],
                          'keep_extra': True,
                          'rows': [[contract, obra.get('Cliente') or '',
                                    str(obra.get('Adelanto %') or ''),
                                    str(obra.get('Fondo de garantía %') or ''),
                                    order_sudo.company_id.construction_sale_milestone_template or '',
                                    '%.6f' % discount, {
                                        'by_partida': 'Por partida',
                                        'single': 'Una línea por valorización',
                                    }.get(order_sudo.company_id.construction_invoice_form, '')]]},
            'VENTA': {'keys': ['contract', 'typology', 'price'], 'match': ['contract', 'typology'],
                      'rows': [[contract, t['code'], number((t.get('price') or 0.0) / factor)]
                               for t in summary.get('typologies', [])]},
            'OBRA': {'keys': ['key', 'value'], 'match': ['key'], 'keep_extra': True, 'rows': [
                ['Cliente', obra.get('Cliente') or ''], ['Inicio', str(obra.get('Inicio') or '')],
                ['Fin', str(obra.get('Fin') or '')],
                ['Adelanto %', str(obra.get('Adelanto %') or '')],
                ['Fondo de garantía %', str(obra.get('Fondo de garantía %') or '')],
                ['Hoja de venta', '%s · %s' % (order_sudo.name, summary.get('version') or '')],
                ['Venta traída el', fields.Date.context_today(self).strftime('%d/%m/%Y')],
                ['Inicio de la venta', str(obra.get('Inicio') or '')],
                ['Fin de la venta', str(obra.get('Fin') or '')],
                ['Subtotal de la cotización', number(summary.get('order_subtotal'))],
                ['Departamentos vendidos', number(summary.get('departments_total'))],
            ]},
            'ACABADOS DE OBRA': {
                'keys': ['code', 'description', 'kind', 'material'], 'match': ['code'],
                'rows': [[item['code'], item.get('description') or '', item.get('kind') or '',
                          item.get('material') or ''] for item in summary.get('finishes', [])]},
            'VENDIDO': {
                'keys': ['typology', 'partida', 'group', 'ml', 'structure', 'fronts', 'price',
                         'spaces', 'departments'], 'match': ['typology', 'group'],
                'keep_extra': True,
                'rows': [[item.get('typology'), item.get('partida') or '', item.get('group') or '',
                          number(item.get('ml')), item.get('structure') or '',
                          item.get('fronts') or '', number((item.get('price') or 0.0) / factor),
                          number(item.get('spaces')), item.get('departments') or '']
                         for item in summary.get('sold', [])]},
        }
        for name, tab in tabs.items():
            tab['headers'] = headers(name)
        measured = {t['code'] for t in summary.get('typologies', [])}
        missing = sorted({item.get('typology') for item in summary.get('building', [])
                          if item.get('typology') and item['typology'] not in measured})
        warnings = [self.env._('%s sin metrado', code) for code in missing]
        return {'tabs': tabs, 'warnings': warnings, 'version': summary.get('version') or '',
                'project': project.display_name}

    def construction_sale_bring_done(self, version):
        self.ensure_one()
        self.construction_sale_brought = version or True
        return True

    def construction_sale_new_version(self):
        """«Nueva versión» (M117-16, punto 5): guarda la vigente como copia con su
        PDF, sube la versión y abre la hoja para seguir cotizando. Desde «Adjudicada»
        queda «Adicional en curso»; si no, «Venta en curso»."""
        self.ensure_one()
        phase = self.construction_sale_phase
        if phase not in ('sent', 'awarded'):
            raise UserError(self.env._('Solo una hoja enviada o adjudicada abre una versión nueva.'))
        version = self.construction_sale_version
        copy, _message = self._construction_copy_version(
            self.env._('Versión N%s de la cotización', version))
        self._construction_sale_version_pdf(copy, version)
        today = fields.Date.context_today(self)
        self.write({
            'construction_sale_version': version + 1,
            'construction_sale_phase': 'additional' if phase == 'awarded' else 'in_progress',
            'construction_sale_pending': json.dumps(
                {'version': 'N%s' % (version + 1), 'date': today.strftime('%d/%m/%Y')}),
        })
        return self.action_open_spreadsheet()

    def _construction_sale_version_pdf(self, copy, version):
        """El PDF de la versión que se cierra, junto a su copia."""
        order = self.construction_sale_order_id
        if not order.construction_sale_summary:
            return
        report = self.env.ref(
            'al_construction_planner_spreadsheet_furniture.action_report_sale_sheet_quotation')
        pdf, _kind = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report, order.ids)
        self.env['ir.attachment'].create({
            'name': 'Cotizacion_%s_N%s.pdf' % (order.name, version),
            'datas': base64.b64encode(pdf), 'res_model': copy._name, 'res_id': copy.id,
            'mimetype': 'application/pdf'})

    def construction_sale_pending_done(self):
        """La hoja ya escribió la versión y la fila de cambios."""
        self.ensure_one()
        self.construction_sale_pending = False
        return True

    def construction_sale_pass_preview(self, summary):
        self.ensure_one()
        return self.construction_sale_order_id.construction_sale_pass_preview(summary)

    def construction_sale_pass(self, summary):
        self.ensure_one()
        return self.construction_sale_order_id.construction_sale_pass(summary)

    def construction_sale_add_rows(self, sheets):
        """«Ampliar filas» de la hoja de venta: la rehace con 300 filas más, con
        los datos que escribió el analista."""
        self.ensure_one()
        rows = (self.construction_sheet_rows or SALE_ROWS) + SALE_ROWS
        return self._construction_upgrade_sale(sheets, rows=rows)

    def construction_sale_rates(self):
        """«Traer tarifario»: las líneas vigentes para la cotización de la hoja."""
        self.ensure_one()
        return [line._sheet_row() for line in
                self.sudo().construction_sale_order_id._construction_sale_rates()]

    def construction_sale_propose_rates(self, rows):
        """«Proponer alta en el tarifario» (M117-19, punto 7): una actividad con
        los datos de cada ítem que no está en el catálogo."""
        self.ensure_one()
        order = self.construction_sale_order_id
        lines = ''.join('<li>%s · %s · %s</li>' % tuple(
            escape(str(value or '')) for value in row[:3]) for row in rows or [])
        user = order.company_id.construction_planning_user_id or order.user_id or self.env.user
        order.activity_schedule(
            'mail.mail_activity_data_todo', user_id=user.id,
            summary=self.env._('Proponer alta en el tarifario'),
            note=Markup('<ul>%s</ul>') % Markup(lines))
        return True

    def action_construction_download_sale_template(self):
        """«Descargar formato de carga» de la hoja de venta: un libro con sus
        propias pestañas, solo con las columnas de dato (M117-16, punto 2)."""
        self.ensure_one()
        from openpyxl import Workbook
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = OBRA_SHEET
        worksheet.append(['Dato', 'Valor'])
        for name in OBRA_ROW:
            worksheet.append([name, None])
        worksheet = workbook.create_sheet(PARAMETERS_SHEET)
        worksheet.append(['Parámetro', 'Valor', 'Clave', 'Motivo del cambio'])
        for name, columns in SALE_COLUMNS.items():
            worksheet = workbook.create_sheet(name)
            worksheet.append([column[1] for column in columns if not column[4]])
        output = BytesIO()
        workbook.save(output)
        attachment = self.env['ir.attachment'].create({
            'name': 'formato_hoja_de_venta.xlsx', 'datas': base64.b64encode(output.getvalue()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name, 'res_id': self.id})
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/%s?download=true' % attachment.id}

    def _construction_upgrade_sale(self, sheets, rows=None):
        """«Actualizar a la plantilla vigente» de la hoja de venta: rehace la
        hoja con la plantilla de hoy y copia lo que escribió el analista, celda por
        celda, con su contenido (una suma escrita sigue siendo suma)."""
        self.ensure_one()
        order = self.construction_sale_order_id
        if not order:
            raise UserError(self.env._('La hoja de venta no tiene cotización.'))
        self._construction_copy_version(self.env._('Antes de actualizar a la plantilla vigente'))
        rows = rows or self.construction_sheet_rows or SALE_ROWS
        data = order._construction_sale_sheet_data(rows=rows)
        by_name = {sheet['name']: sheet for sheet in data['sheets']}
        others = (sheets or {}).get('other') or {}
        for name, columns in SALE_COLUMNS.items():
            target = by_name[name]['cells']
            data_letters = {chr(65 + index) for index, column in enumerate(columns)
                            if not column[4]}
            # El id del tarifario es «(calc.)», pero lo escribe «Traer tarifario».
            if name == RATES_SHEET:
                data_letters.add('L')
            if name == FINISHES_SHEET:
                data_letters |= set('IJK')
            for ref, content in (others.get(name, {}).get('cells') or {}).items():
                letter = ''.join(char for char in ref if char.isalpha())
                row = int(ref[len(letter):])
                if row > 1 and letter in data_letters:
                    target[ref] = str(content)
        obra = by_name[OBRA_SHEET]['cells']
        for ref, content in (others.get(OBRA_SHEET, {}).get('cells') or {}).items():
            letter = ''.join(char for char in ref if char.isalpha())
            row = int(ref[len(letter):])
            if row > 1 and letter in 'BDEFGH':
                obra[ref] = str(content)
        self._construction_upgrade_parameters(by_name[PARAMETERS_SHEET],
                                              others.get(PARAMETERS_SHEET))
        self.write({'datas': base64.b64encode(json.dumps(data).encode()),
                    'construction_sheet_rows': rows})
        self._delete_collaborative_data()
        return self.action_open_spreadsheet()

    def _construction_validate_sale(self, sheets):
        """Errores y avisos de la hoja de venta (M117-16, punto 2). Las reglas de
        fila ya las calculó la hoja en sus columnas Aviso: aquí se repiten."""
        self.ensure_one()
        issues = []

        def by_key(name):
            columns = [column[0] for column in SALE_COLUMNS[name]]
            result = []
            for number, row in enumerate(sheets.get(name) or [], start=1):
                if number > 1:
                    result.append((number, dict(zip(columns, row))))
            return result

        obra = {row[0]: row[1] if len(row) > 1 else '' for row in sheets.get(OBRA_SHEET) or []
                if row}
        for name in ('Proyecto', 'Cliente', 'Código de cotización'):
            if obra.get(name) in (None, '', False):
                issues.append((OBRA_SHEET, OBRA_ROW[name], 'Valor', self.env._(
                    '%s está vacío.', name), 'error'))
        building = by_key('EDIFICIO')
        errors = {'Se cruza con otra fila': 'error', 'Tipología sin metrado': 'error',
                  'Ambiente fuera de la lista': 'warning',
                  'Ítem que no está en PRECIOS': 'error', 'Partida distinta en el bloque': 'error',
                  'Tipología que no está en EDIFICIO': 'warning', 'Vale la del plano': 'warning'}
        for name, rows in (('EDIFICIO', building), ('METRADO', by_key('METRADO'))):
            for number, row in rows:
                message = row.get('warning')
                if message in errors:
                    issues.append((name, number, 'Aviso (calc.)', message, errors[message]))
        for number, row in by_key('TARIFARIO'):
            if row.get('status') in ('Ya no está', 'Fuera del tarifario'):
                issues.append(('TARIFARIO', number, 'En el catálogo (calc.)', self.env._(
                    '%(item)s: %(status)s.', item=row.get('item'), status=row.get('status')),
                    'warning'))
        names, finishes = {}, set()
        for number, row in by_key('ACABADOS'):
            if row.get('code'):
                finishes.add(row['code'])
        cost_used = False
        for number, row in by_key('PRECIOS'):
            used = row.get('name_used')
            if used:
                if used in names:
                    issues.append(('PRECIOS', number, 'Nombre usado (calc.)', self.env._(
                        '%s está repetido: escriba un nombre en la obra.', used), 'error'))
                names[used] = number
            for key in ('structure', 'fronts'):
                if row.get(key) and row[key] not in finishes:
                    issues.append(('PRECIOS', number, key, self.env._(
                        'El acabado %s no existe en ACABADOS.', row[key]), 'error'))
            if row.get('rounded') not in (None, '', False) and row.get('agreed') not in (
                    None, '', False) and row['agreed'] != row['rounded']:
                issues.append(('PRECIOS', number, 'Precio acordado', self.env._(
                    '%s: precio acordado distinto del redondeado.', used), 'warning'))
            if row.get('cost') not in (None, '', False):
                cost_used = True
        order_sudo = self.sudo().construction_sale_order_id
        company = order_sudo.company_id or self.env.company
        issues += self.env['construction.sheet.parameter']._construction_issues(
            sheets.get(PARAMETERS_SHEET), 'sale', company,
            used=('factor_costo',) if cost_used else ())
        return issues

    def action_construction_download_template(self):
        """«Descargar formato de carga» del menú del maestro (M113-03): el
        mismo de «Importar maestro y ETO»."""
        self.ensure_one()
        return self.env['construction.master.import.wizard'].action_download_template()

    # ------------------------------------------------------------------
    # Importar Excel a la hoja (paquete 1.13, M113-04/05)
    # ------------------------------------------------------------------
    def construction_sheet_extension(self, rows):
        """Celdas, reglas y formato condicional para ampliar el maestro a
        ``rows`` filas de datos (las mismas fórmulas y listas de la plantilla).

        :return: ``{'rows': n, 'sheets': {pestaña: {'cells', 'rules',
            'conditional', 'row_number'}}, 'summary': celdas de RESUMEN,
            'pivots': {id: fila final}}``; vacío si la hoja es anterior al
            paquete 1.16 o ya tiene esas filas.
        """
        self.ensure_one()
        current = self.construction_sheet_rows
        project = self.construction_project_id
        if not current or rows <= current or self.construction_sheet_kind != 'furniture':
            return {}
        # M117-02: las columnas y _LISTAS de una hoja anterior están en otro
        # orden; la ampliación escribiría en las celdas equivocadas.
        if self.construction_sheet_layout < FURNITURE_LAYOUT:
            return {'needs_upgrade': True}
        layout = project._construction_sheet_layout()
        parts = project._construction_row_parts(layout, current + 2, rows + 1)
        result = {'rows': rows, 'sheets': {}, 'pivots': {}}
        for name, part in parts.items():
            part['row_number'] = rows + 50
            result['sheets'][name] = part
        result['sheets']['_LISTAS']['row_number'] = project._construction_helper_row(
            layout, 'BOM', 'prod', rows + 1) + 10
        summary_cells, _styles, pivots = project._construction_summary(layout, rows, {})
        result['summary'] = summary_cells
        result['pivots'] = {pivot_id: pivot['dataSet']['zone']['bottom']
                            for pivot_id, pivot in pivots.items()}
        self.construction_sheet_rows = rows
        return result

    def construction_sheet_import_done(self, filename, sheets, errors, warnings):
        """Deja en el historial de la obra la importación de un Excel a la
        hoja (M113-04)."""
        self.ensure_one()
        # M113-11: importada (o validada, si el análisis no dejó errores).
        self._construction_set_state(
            'validated' if not errors else 'imported',
            construction_import_filename=filename or False,
            construction_import_date=fields.Datetime.now(),
            construction_import_errors=errors or 0)
        # sudo: quien planifica puede no tener escritura en la obra; solo se
        # deja el mensaje con él como autor.
        project_sudo = self.construction_project_id.sudo()
        project_sudo.message_post(author_id=self.env.user.partner_id.id, body=self.env._(
            'Excel importado a la hoja de trabajo (%(file)s): %(sheets)s pestañas, %(errors)s '
            'errores y %(warnings)s avisos al validar.', file=filename or '—', sheets=sheets,
            errors=errors, warnings=warnings))
        return True

    # ------------------------------------------------------------------
    # CONTROL y «Traer de Odoo» (paquete 1.13, M113-11)
    # ------------------------------------------------------------------
    def construction_control_counts(self):
        """Lo que tiene el planificador por piso: ``[[piso, muebles, módulos a
        armar, ML]]``. El piso lleva su agrupador («Torre A / Piso 3»), como
        la columna «Piso (calc.)» de ARBOL; los muebles son los ambientes; los
        módulos, los de la tipología de cada ambiente sin zócalos; los ML, el
        total de la tipología (M116-10)."""
        self.ensure_one()
        project = self.construction_project_id
        spaces = self.env['project.task'].search([
            ('project_id', '=', project.id), ('construction_level', '=', 'space')])
        totals = {}
        modules_by_typology = {}
        for space in spaces:
            groups, floor, parent = [], False, space.parent_id
            while parent:
                if parent.construction_level == 'floor' and not floor:
                    floor = parent.name
                elif parent.construction_level == 'group':
                    groups.insert(0, parent.name)
                parent = parent.parent_id
            key = ' / '.join(groups + [floor or ''])
            typology = space.construction_typology_id
            if typology not in modules_by_typology:
                modules_by_typology[typology] = len(typology.module_line_ids.filtered(
                    lambda module: not module.type_id.not_counted))
            row = totals.setdefault(key, [key, 0, 0, 0.0])
            row[1] += 1
            row[2] += modules_by_typology[typology]
            row[3] += typology.ml_total
        return [[key, spaces_count, modules, round(ml, 2)]
                for key, spaces_count, modules, ml in totals.values()]

    def construction_furniture_odoo_rows(self):
        """«Traer de Odoo» del maestro: las pestañas con lo que tiene la obra,
        en el formato de «Importar Excel a la hoja» (filas por clave). La
        versión se guarda al confirmar la vista previa (M117-07)."""
        self.ensure_one()
        project = self.construction_project_id
        env = self.env

        def label(record, field):
            value = record[field]
            if not value:
                return ''
            return dict(record._fields[field]._description_selection(env)).get(value, value)

        def number(value):
            return ('%s' % round(value, 4)).rstrip('0').rstrip('.') if value else ''

        stage_labels = {stage.code: stage._label() for stage in
                        env['construction.stage'].with_context(active_test=False).search([])}
        typologies = env['construction.typology'].search([('project_id', '=', project.id)])
        sheets = {}

        def add(name, keys, rows):
            if rows:
                sheets[name] = {'keys': keys, 'rows': rows, 'extra_headers': [],
                                'extra_rows': [[] for _row in rows],
                                'headers': {key: [header] for key, header, _r, _h in
                                            SHEETS[name][1] if key in keys}}

        add('TIPOLOGIAS', ['code', 'name', 'family', 'product', 'ml_low', 'ml_high', 'variant_of',
                           'aliases'], [[
                t.code or '', t.name or '', label(t, 'family'), t.product_tmpl_id.name or '',
                '' if any(t.module_line_ids.mapped('width_mm')) else number(t.ml_low),
                '' if any(t.module_line_ids.mapped('width_mm')) else number(t.ml_high),
                t.variant_of_id.code or '', '; '.join(t.alias_ids.mapped('name'))]
            for t in typologies])
        add('MUEBLES', ['typology', 'name', 'ml_group', 'ml'], [[
            f.typology_id.code, f.name, label(f, 'ml_group'), number(f.ml)]
            for t in typologies for f in t.furniture_line_ids])
        add('MODULOS', ['typology', 'sequence', 'code', 'type', 'width', 'ml_group', 'activity',
                        'furniture', 'name', 'module_class', 'join_method'], [[
            m.typology_id.code, str(m.sequence), m.code or '', m.type_id.name or label(m, 'module_type'),
            str(m.width_mm or ''), label(m, 'ml_group'), m.assembly_activity_id.code or '',
            m.furniture_id.name or '', m.name or '', label(m, 'module_class'),
            label(m, 'join_method')] for t in typologies for m in t.module_line_ids])
        add('ACTIVIDADES', ['typology', 'activity', 'qty'], [[
            line.typology_id.code, line.activity_id.code or '', number(line.qty)]
            for t in typologies for line in t.activity_line_ids])
        # BOM: la receta de cada módulo (con «Módulo») y, de la receta de la
        # tipología, lo que no está en los módulos: el importador junta las
        # líneas de los módulos en la receta de la tipología.
        # sudo: el planificador lee la BOM de la tipología, que no administra.
        bom_rows = []
        for typology in typologies:
            by_module = False
            for module in typology.module_line_ids:
                for material in module.material_ids:
                    by_module = True
                    bom_rows.append([typology.code, material.product_id.default_code or '',
                                     material.product_id.name or '', number(material.qty),
                                     material.uom_id.name or '',
                                     stage_labels.get(material.stage, ''), module.code])
            # M117-07: con recetas por módulo, la receta de la tipología es su
            # suma redondeada a la precisión de la unidad. La diferencia es
            # redondeo y una línea sin módulo no llega al plan.
            if by_module:
                continue
            for line in typology.sudo().bom_id.bom_line_ids:
                if line.product_uom_id.is_zero(line.product_qty):
                    continue
                stage = line.construction_consumption_stage or False
                bom_rows.append([typology.code, line.product_id.default_code or '',
                                 line.product_id.name or '', number(line.product_qty),
                                 line.product_uom_id.name or '',
                                 stage_labels.get(stage, ''), ''])
        add('BOM', ['typology', 'product_code', 'product_name', 'qty', 'uom', 'stage', 'module'],
            bom_rows)
        add('PIEZAS', ['typology', 'module', 'qty', 'length', 'width', 'piece_type', 'color',
                       'product_code', 'edges'], [[
            t.code, m.code, number(p.qty), number(p.length_mm), number(p.width_mm),
            p.piece_type or '', p.color or '', p.product_id.default_code or '', p.edges or '']
            for t in typologies for m in t.module_line_ids for p in m.piece_ids])
        add('ARBOL', ['group', 'floor', 'apartment', 'space', 'typology', 'unit_type'],
            self._construction_tree_rows(project, label))
        rate_lists = env['construction.rate.list'].search([('project_id', '=', project.id)])
        add('TARIFAS', ['activity', 'price', 'retention', 'family'], [[
            line.activity_id.code or '', number(line.price), number(line.retention_pct),
            label(rate_list, 'family')] for rate_list in rate_lists for line in rate_list.line_ids])
        if not sheets:
            raise UserError(env._('La obra aún no tiene tipologías ni árbol en el planificador.'))
        # El producto como lo elige la hoja y su categoría (M113-06).
        wizard = env['construction.spreadsheet.import.wizard'].new({'document_id': self.id})
        data = wizard._prepare({'sheets': sheets, 'other': {}})
        return {'filename': env._('datos de Odoo'), 'mode': 'replace', 'expand_rows': True,
                'keep_extra': False, 'sheets': data['sheets'], 'other': {},
                'added_products': data['added_products']}

    def _construction_tree_rows(self, project, label):
        """Filas de ARBOL: agrupador, piso, departamento, ambiente, tipología y
        tipo de unidad de cada ambiente de la obra, en el orden del árbol."""
        rows = []
        spaces = self.env['project.task'].search([
            ('project_id', '=', project.id), ('construction_level', '=', 'space')],
            order='id')
        for space in spaces:
            groups, floor, apartment, parent = [], False, False, space.parent_id
            while parent:
                if parent.construction_level == 'apartment' and not apartment:
                    apartment = parent
                elif parent.construction_level == 'floor' and not floor:
                    floor = parent
                elif parent.construction_level == 'group':
                    groups.insert(0, parent.name)
                parent = parent.parent_id
            unit_type = label(apartment, 'construction_unit_type') if apartment and \
                'construction_unit_type' in apartment._fields else ''
            rows.append([' / '.join(groups), floor.name if floor else '',
                         apartment.name if apartment else '', space.name,
                         space.construction_typology_id.code or '', unit_type])
        return rows
