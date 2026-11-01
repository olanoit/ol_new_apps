# -*- coding: utf-8 -*-
import base64
from io import BytesIO

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import (
    SHEETS, norm, sheet_key,
)
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_keys import KEYS_SHEET


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    def _construction_send_sheet_names(self):
        """Solo las pestañas del maestro y _CLAVES (paquete 1.13, M113-02)."""
        if self.construction_sheet_kind == 'budget':
            return super()._construction_send_sheet_names()
        return list(SHEETS) + [KEYS_SHEET]

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
        wizard = self._construction_furniture_wizard(sheets)
        try:
            data = wizard._analyze()
            issues = wizard._construction_issues(data)
        finally:
            wizard.unlink()
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
                    lambda module: module.special_kind != 'plinth' and 'zocalo' not in norm(
                        '%s %s' % (module.code or '', module.name or ''))))
            row = totals.setdefault(key, [key, 0, 0, 0.0])
            row[1] += 1
            row[2] += modules_by_typology[typology]
            row[3] += typology.ml_total
        return [[key, spaces_count, modules, round(ml, 2)]
                for key, spaces_count, modules, ml in totals.values()]

    def construction_furniture_odoo_rows(self):
        """«Traer de Odoo» del maestro: las pestañas con lo que tiene la obra,
        en el formato de «Importar Excel a la hoja» (filas por clave). Guarda
        una versión de la hoja antes de que la hoja escriba."""
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
            m.typology_id.code, str(m.sequence), m.code or '', label(m, 'module_type'),
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
            in_modules = {}
            for module in typology.module_line_ids:
                for material in module.material_ids:
                    key = (material.product_id, material.stage or False)
                    in_modules[key] = in_modules.get(key, 0.0) + material.qty
                    bom_rows.append([typology.code, material.product_id.default_code or '',
                                     material.product_id.name or '', number(material.qty),
                                     material.uom_id.name or '',
                                     stage_labels.get(material.stage, ''), module.code])
            for line in typology.sudo().bom_id.bom_line_ids:
                stage = line.construction_consumption_stage or False
                qty = line.product_qty - in_modules.get((line.product_id, stage), 0.0)
                if qty <= 1e-6:
                    continue
                bom_rows.append([typology.code, line.product_id.default_code or '',
                                 line.product_id.name or '', number(qty),
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
        self._construction_save_version(env._('Antes de traer los datos de Odoo'))
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
