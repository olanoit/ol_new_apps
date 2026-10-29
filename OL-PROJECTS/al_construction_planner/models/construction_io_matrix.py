# -*- coding: utf-8 -*-
"""Recursos planificados como tabla insumo-producto (v1.8, M18-04).

Filas: los elementos del alcance en el nivel que el usuario elige (módulo,
mueble, ambiente, departamento o piso en mobiliario; partida o subpartida en
construcción). Columnas: los insumos (producto, actividad o rol y su unidad),
agrupados con subtotales por etapa › sub etapa y, dentro, por tipo de
recurso. Celdas: cantidad o monto de lo planificado, lo comprometido, lo
real o el saldo. Respeta la selección del árbol o del cronograma y el filtro
de etapas, y se exporta a Excel con la misma agrupación.

Todo sale de las líneas del plan: una consulta por pedido, sin recorrer el
árbol."""
import io
from collections import defaultdict

from odoo import api, models
from odoo.exceptions import UserError

from .common import can_see_amounts
from .construction_plan_tree import LINE_FIELD

#: Lo que se ve en cada celda: (campo de monto, cantidad).
VALUES = {
    'planned': 'amount_planned',
    'committed': 'amount_committed',
    'actual': 'amount_actual',
    'remaining': 'amount_remaining',
}


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    # ------------------------------------------------------------------
    # Opciones
    # ------------------------------------------------------------------
    def _io_row_levels(self):
        """Niveles por los que se pueden armar las filas: ``[(campo de la
        línea, nombre)]`` de arriba abajo. Con plantilla, sus niveles (Nivel
        1 a 6); sin ella, piso › departamento › ambiente › mueble › módulo."""
        self.ensure_one()
        template = self.project_id.construction_level_template_id
        if template:
            lines = template.line_ids.sorted(lambda l: (l.sequence, l.id))[:6]
            return [('level_%s_id' % depth, line.name)
                    for depth, line in enumerate(lines, start=1)]
        Line = self.env['construction.resource.plan.line']
        return [(field, Line._fields[field].string) for field in LINE_FIELD.values()]

    def get_io_matrix_options(self):
        self.ensure_one()
        self.check_access('read')
        levels = self._io_row_levels()
        space = next((field for field, _name in levels if field == 'space_task_id'), False)
        if not space and self.project_id.construction_level_template_id:
            lines = self.project_id.construction_level_template_id.line_ids.sorted(
                lambda l: (l.sequence, l.id))
            index = next((i for i, line in enumerate(lines[:6], start=1)
                          if line.role == 'space'), len(levels))
            space = 'level_%s_id' % index
        return {
            'levels': [{'field': field, 'name': name} for field, name in levels],
            'default_level': space or (levels[-1][0] if levels else False),
            'values': [
                {'key': 'planned', 'name': self.env._('Planificado')},
                {'key': 'committed', 'name': self.env._('Comprometido')},
                {'key': 'actual', 'name': self.env._('Real')},
                {'key': 'remaining', 'name': self.env._('Saldo')},
            ],
            'stage_tree': self.env['construction.stage']._get_tree(),
            'show_amounts': can_see_amounts(self.env),
        }

    # ------------------------------------------------------------------
    # Matriz
    # ------------------------------------------------------------------
    def get_io_matrix(self, keys=None, filters=None, options=None):
        """Matriz insumo-producto de la selección.

        :param keys: selección del árbol (``['p']`` o ids de tareas); vacía es
            la obra entera.
        :param filters: filtros del árbol (``stages``, ``resource_types``…).
        :param options: ``level`` (campo de la línea que arma las filas),
            ``measure`` (``amount`` o ``qty``) y ``value`` (``planned``,
            ``committed``, ``actual`` o ``remaining``).
        :returns: ``{rows, columns, groups, cells, row_totals, column_totals,
            total, ...}``; las celdas son ``{"fila|columna": valor}``.
        """
        self.ensure_one()
        self.check_access('read')
        options = dict(options or {})
        levels = dict(self._io_row_levels())
        level = options.get('level') if options.get('level') in levels else \
            self.get_io_matrix_options()['default_level']
        measure = 'qty' if options.get('measure') == 'qty' else 'amount'
        if not can_see_amounts(self.env):
            # Visibilidad de montos (v1.8, M18-10): pantalla y Excel en cantidades.
            measure = 'qty'
        value = options.get('value') if options.get('value') in VALUES else 'planned'
        keys = keys or ['p']
        domain = self._tree_selection_line_domain(keys, filters)
        Line = self.env['construction.resource.plan.line']
        stage_tree = self.env['construction.stage']._get_tree(active_only=False)
        stage_info = {node['code']: node for node in stage_tree}
        stage_order = {node['code']: index for index, node in enumerate(stage_tree)}
        lines = Line.search_read(domain, [
            level, 'stage', 'stage_parent', 'resource_type', 'resource_type_id', 'product_id',
            'activity_id', 'product_uom_id', 'qty_planned', 'price_unit_planned',
            'amount_planned', 'amount_committed', 'amount_actual', 'amount_remaining'])
        rows, columns, cells = {}, {}, defaultdict(float)
        types = {rtype.id: rtype for rtype in self.env['construction.resource.type'].with_context(
            active_test=False).search([])}
        no_level = self.env._('Fuera del nivel (%s superior)', levels.get(level, ''))
        for line in lines:
            row_id = line[level][0] if line[level] else 0
            if row_id not in rows:
                rows[row_id] = {'id': row_id,
                                'name': line[level][1] if line[level] else no_level}
            resource = line['activity_id'] or line['product_id']
            uom = line['product_uom_id']
            stage = line['stage'] or False
            rtype_id = line['resource_type_id'][0] if line['resource_type_id'] else 0
            column_key = '%s/%s/%s/%s/%s' % (
                stage or '-', rtype_id, 'a' if line['activity_id'] else 'p',
                resource[0] if resource else 0, uom[0] if uom else 0)
            if column_key not in columns:
                rtype = types.get(rtype_id)
                node = stage_info.get(stage, {})
                parent = stage_info.get(node.get('parent')) if node.get('parent') else None
                columns[column_key] = {
                    'key': column_key,
                    'name': resource[1] if resource else self.env._('Sin recurso'),
                    'uom': uom[1] if uom else '',
                    'stage': stage, 'stage_label': node.get('label') or self.env._('Sin etapa'),
                    'parent': parent['code'] if parent else False,
                    'parent_label': parent['label'] if parent else '',
                    'type_id': rtype_id,
                    'type_label': rtype.name if rtype else self.env._('Sin tipo'),
                    'order': (
                        stage_order.get(parent['code'], -1) if parent else
                        stage_order.get(stage, 10 ** 6),
                        stage_order.get(stage, 10 ** 6),
                        (rtype.sequence, rtype.id) if rtype else (10 ** 6, 0),
                        resource[1] if resource else ''),
                }
            amount = line[VALUES[value]] or 0.0
            if measure == 'qty':
                price = line['price_unit_planned']
                if value == 'planned':
                    amount = line['qty_planned']
                elif value == 'remaining':
                    spent = (line['amount_committed'] + line['amount_actual']) / price if price \
                        else 0.0
                    amount = line['qty_planned'] - spent
                else:
                    amount = amount / price if price else 0.0
            cells['%s|%s' % (row_id, column_key)] += amount
        ordered_columns = sorted(columns.values(), key=lambda c: c['order'])
        for column in ordered_columns:
            column.pop('order')
        ordered_rows = self._io_sort_rows(rows, level)
        groups = self._io_column_groups(ordered_columns)
        row_totals = defaultdict(float)
        column_totals = defaultdict(float)
        for cell_key, amount in cells.items():
            row_id, column_key = cell_key.split('|', 1)
            row_totals[row_id] += amount
            column_totals[column_key] += amount
        digits = 2 if measure == 'amount' else 4
        return {
            'level': level, 'level_name': levels.get(level, ''), 'measure': measure,
            'value': value,
            'rows': ordered_rows,
            'columns': ordered_columns,
            'groups': groups,
            'cells': {key: round(amount, digits) for key, amount in cells.items() if amount},
            'row_totals': {key: round(amount, digits) for key, amount in row_totals.items()},
            'column_totals': {key: round(amount, digits) for key, amount in column_totals.items()},
            'total': round(sum(row_totals.values()), digits),
        }

    def _io_sort_rows(self, rows, level):
        """Filas en el orden del árbol (ruta de la tarea), la de «fuera del
        nivel» al final."""
        tasks = {task.id: task for task in self.env['project.task'].browse(
            [row_id for row_id in rows if row_id]).exists()}

        def key(row):
            task = tasks.get(row['id'])
            if not task:
                return (1, [], '')
            path = [int(i) for i in (task.construction_path or '').split('/') if i]
            return (0, [(t.sequence, t.name or '', t.id) for t in self.env['project.task'].browse(path)],
                    task.name or '')

        result = []
        for row in sorted(rows.values(), key=key):
            task = tasks.get(row['id'])
            if task:
                row['path'] = task._construction_path_name()
            result.append(row)
        return result

    @api.model
    def _io_column_groups(self, columns):
        """Encabezado de varios niveles: etapa padre › etapa › tipo de recurso,
        cada grupo con las claves de sus columnas (para plegarlo y sumar su
        subtotal)."""
        groups = []
        index = {}
        for column in columns:
            path = []
            if column['parent']:
                path.append(('parent', column['parent'], column['parent_label']))
            path.append(('stage', column['stage'] or '-', column['stage_label']))
            path.append(('type', '%s/%s' % (column['stage'] or '-', column['type_id']),
                         column['type_label']))
            parent_key = False
            for depth, (kind, code, label) in enumerate(path):
                key = '%s:%s' % (kind, code)
                if key not in index:
                    index[key] = {'key': key, 'kind': kind, 'label': label, 'depth': depth,
                                  'parent': parent_key, 'columns': []}
                    groups.append(index[key])
                index[key]['columns'].append(column['key'])
                parent_key = key
            column['group'] = parent_key
        return groups

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_open_io_matrix(self):
        """Abre la matriz insumo-producto de este plan (toda la obra)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'al_construction_planner.io_matrix',
            'name': self.env._('Insumo-producto · %s', self.display_name),
            'context': {'construction_plan_id': self.id},
        }

    def action_export_io_matrix(self, keys=None, filters=None, options=None):
        """Exporta la matriz a Excel con la misma agrupación de columnas."""
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError as exc:  # pragma: no cover - dependencia de Odoo
            raise UserError(self.env._('Falta la librería xlsxwriter.')) from exc
        data = self.get_io_matrix(keys, filters, options)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(self.env._('Insumo-producto')[:31])
        bold = workbook.add_format({'bold': True, 'border': 1, 'align': 'center',
                                    'valign': 'vcenter', 'text_wrap': True, 'bg_color': '#EEEEEE'})
        number = workbook.add_format({'num_format': '#,##0.00' if data['measure'] == 'amount'
                                      else '#,##0.0000', 'border': 1})
        total = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'bold': True})
        text = workbook.add_format({'border': 1})
        groups = data['groups']
        # Encabezado fijo: etapa padre, etapa, tipo de recurso e insumo. Una
        # etapa sin padre ocupa las dos primeras filas.
        header_rows = 4
        sheet.merge_range(0, 0, header_rows - 1, 0, data['level_name'], bold)
        positions = {column['key']: index + 1 for index, column in enumerate(data['columns'])}
        kind_row = {'parent': 0, 'stage': 1, 'type': 2}
        for group in groups:
            cols = [positions[key] for key in group['columns']]
            first, last = min(cols), max(cols)
            top = bottom = kind_row[group['kind']]
            if group['kind'] == 'stage' and not group['parent']:
                top = 0
            if (top, first) == (bottom, last):
                sheet.write(top, first, group['label'], bold)
            else:
                sheet.merge_range(top, first, bottom, last, group['label'], bold)
        for column in data['columns']:
            label = column['name'] + (' (%s)' % column['uom'] if column['uom'] else '')
            sheet.write(header_rows - 1, positions[column['key']], label, bold)
        total_col = len(data['columns']) + 1
        sheet.write(header_rows - 1, total_col, self.env._('Total'), bold)
        for offset, row in enumerate(data['rows']):
            line = header_rows + offset
            sheet.write(line, 0, row.get('path') or row['name'], text)
            for column in data['columns']:
                amount = data['cells'].get('%s|%s' % (row['id'], column['key']))
                if amount:
                    sheet.write_number(line, positions[column['key']], amount, number)
            sheet.write_number(line, total_col, data['row_totals'].get(str(row['id']), 0.0), total)
        last = header_rows + len(data['rows'])
        sheet.write(last, 0, self.env._('Total'), bold)
        for column in data['columns']:
            sheet.write_number(last, positions[column['key']],
                               data['column_totals'].get(column['key'], 0.0), total)
        sheet.write_number(last, total_col, data['total'], total)
        sheet.set_column(0, 0, 40)
        sheet.set_column(1, total_col, 14)
        sheet.freeze_panes(header_rows, 1)
        workbook.close()
        attachment = self.env['ir.attachment'].create({
            'name': 'insumo_producto_%s.xlsx' % (self.name or self.id),
            'raw': output.getvalue(),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name, 'res_id': self.id,
        })
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/%s?download=true' % attachment.id}
