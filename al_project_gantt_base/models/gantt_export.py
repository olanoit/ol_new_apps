# -*- coding: utf-8 -*-
"""Exportación del diagrama a Excel y PDF.

Ambos formatos se generan **en el servidor**, a partir de los mismos datos que
dibuja la pantalla. La exportación que trae dhtmlxGantt se descartó a propósito:
funciona contra un servicio en la nube del fabricante, es decir, enviaría la
planificación del cliente a un tercero.

`build_matrix()` prepara una estructura común —filas de tareas en el orden del
árbol y columnas de periodo— que consumen tanto el XLSX como la plantilla QWeb
del PDF, para que los dos formatos digan exactamente lo mismo.
"""
import base64
import io
import logging
from datetime import date, datetime, timedelta

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:  # pragma: no cover - entorno sin la librería
    xlsxwriter = None

#: Escalas admitidas y su paso, en días.
SCALES = {
    'day': 1,
    'week': 7,
    'month': 30,
    'quarter': 91,
}

#: Tope de columnas de periodo: más allá el documento deja de ser legible.
MAX_PERIODS = 60


class GanttExport(models.AbstractModel):
    _inherit = 'al.gantt.data'

    # ------------------------------------------------------------------
    # Estructura común
    # ------------------------------------------------------------------
    @api.model
    def build_matrix(self, project_ids=None, options=None):
        """Filas ordenadas como el árbol y columnas de periodo.

        :return: ``{rows, periods, scale, payload, title, generated_on}``
        """
        options = dict(options or {})
        payload = self.get_data(project_ids=project_ids, options=options)
        tasks = payload['tasks']
        scale = options.get('scale') if options.get('scale') in SCALES else 'week'

        rows = self._ordered_rows(payload)
        periods, scale = self._build_periods(tasks, scale)
        for row in rows:
            row['cells'] = self._row_cells(row, periods)

        return {
            'rows': rows,
            'periods': periods,
            'scale': scale,
            'payload': payload,
            'title': self._export_title(payload),
            'generated_on': self.env.cr.now(),
        }

    @api.model
    def _export_title(self, payload):
        names = [project['name'] for project in payload['projects']]
        if not names:
            return _("Diagrama de Gantt")
        if len(names) == 1:
            return _("Gantt: %s", names[0])
        return _("Gantt: %(first)s y %(count)s proyecto(s) más",
                 first=names[0], count=len(names) - 1)

    @api.model
    def _ordered_rows(self, payload):
        """Aplana el árbol (proyecto → tarea → subtarea) con nivel y código EDT."""
        by_parent = {}
        for task in payload['tasks']:
            by_parent.setdefault(task['parent_id'] or 0, []).append(task)

        tasks_by_project = {}
        for task in by_parent.get(0, []):
            tasks_by_project.setdefault(task['project_id'], []).append(task)

        rows = []

        def walk(task, level, prefix, index):
            code = f"{prefix}.{index}" if prefix else str(index)
            rows.append({
                'id': task['id'],
                'code': code,
                'level': level,
                'name': task['name'],
                'project_name': task['project_name'],
                'start': task['start'],
                'end': task['end'],
                'state': task['state'],
                'stage': task['stage_name'] or '',
                'users': ", ".join(user['name'] for user in task['user_ids']),
                'progress': task['progress'],
                'allocated_hours': task['allocated_hours'],
                'color': task['color'],
                'critical': task.get('critical', False),
                'slack_hours': task.get('slack_hours'),
                'baseline_variance': task.get('baseline_variance_days'),
                'is_project': False,
            })
            for child_index, child in enumerate(by_parent.get(task['id'], []), start=1):
                walk(child, level + 1, code, child_index)

        multi_project = len(payload['projects']) > 1
        for project in payload['projects']:
            children = tasks_by_project.get(project['id'], [])
            if not children:
                continue
            if multi_project:
                rows.append({
                    'id': f"p{project['id']}", 'code': '', 'level': 0,
                    'name': project['name'], 'project_name': project['name'],
                    'start': project['date_start'], 'end': project['date_end'],
                    'state': '', 'stage': '', 'users': '', 'progress': 0.0,
                    'allocated_hours': 0.0, 'color': '#4c4c4c', 'critical': False,
                    'slack_hours': None, 'baseline_variance': None, 'is_project': True,
                })
            for index, task in enumerate(children, start=1):
                walk(task, 1 if multi_project else 0, '', index)
        return rows

    @api.model
    def _to_date(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).replace('Z', '')
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return None

    @api.model
    def _build_periods(self, tasks, scale):
        """Columnas de tiempo que cubren el plan, agrandando la escala si hace
        falta para no pasar de `MAX_PERIODS` columnas."""
        starts = [self._to_date(task['start']) for task in tasks if task['start']]
        ends = [self._to_date(task['end']) for task in tasks if task['end']]
        starts = [value for value in starts if value]
        ends = [value for value in ends if value]
        if not starts or not ends:
            return [], scale

        first, last = min(starts), max(ends)
        order = ['day', 'week', 'month', 'quarter']
        index = order.index(scale)
        while index < len(order) - 1:
            step = SCALES[order[index]]
            if ((last - first).days // step) + 1 <= MAX_PERIODS:
                break
            index += 1
        scale = order[index]
        step = SCALES[scale]

        periods = []
        cursor = self._period_start(first, scale)
        while cursor <= last and len(periods) < MAX_PERIODS:
            end = self._period_end(cursor, scale)
            periods.append({
                'start': cursor,
                'end': end,
                'label': self._period_label(cursor, scale),
                'group': self._period_group(cursor, scale),
            })
            cursor = end + timedelta(days=1)
        return periods, scale

    @api.model
    def _period_start(self, value, scale):
        if scale == 'week':
            return value - timedelta(days=value.weekday())
        if scale == 'month':
            return value.replace(day=1)
        if scale == 'quarter':
            first_month = 3 * ((value.month - 1) // 3) + 1
            return value.replace(month=first_month, day=1)
        return value

    @api.model
    def _period_end(self, value, scale):
        if scale == 'day':
            return value
        if scale == 'week':
            return value + timedelta(days=6)
        if scale == 'month':
            next_month = value.replace(day=28) + timedelta(days=4)
            return next_month.replace(day=1) - timedelta(days=1)
        # trimestre
        month = value.month + 2
        year = value.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        last_day = date(year, month, 28) + timedelta(days=4)
        return last_day.replace(day=1) - timedelta(days=1)

    @api.model
    def _period_label(self, value, scale):
        if scale == 'day':
            return value.strftime('%d')
        if scale == 'week':
            return f"S{value.isocalendar().week:02d}"
        if scale == 'month':
            return value.strftime('%m')
        return f"T{(value.month - 1) // 3 + 1}"

    @api.model
    def _period_group(self, value, scale):
        """Cabecera superior: mes o año, según la escala."""
        if scale in ('day', 'week'):
            return value.strftime('%m/%Y')
        return str(value.year)

    @api.model
    def _row_cells(self, row, periods):
        """Para cada periodo, si la barra de la tarea lo ocupa."""
        start = self._to_date(row['start'])
        end = self._to_date(row['end'])
        if not start or not end:
            return [False] * len(periods)
        return [period['start'] <= end and period['end'] >= start for period in periods]

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    @api.model
    def export_xlsx(self, project_ids=None, options=None):
        """Libro con dos hojas: el detalle de tareas y el diagrama dibujado."""
        if xlsxwriter is None:
            raise UserError(_("Falta la librería xlsxwriter para exportar a Excel."))

        matrix = self.build_matrix(project_ids, options)
        buffer = io.BytesIO()
        book = xlsxwriter.Workbook(buffer, {'in_memory': True, 'default_date_format': 'dd/mm/yyyy'})
        self._xlsx_tasks_sheet(book, matrix)
        self._xlsx_chart_sheet(book, matrix)
        book.close()
        return buffer.getvalue()

    @api.model
    def _xlsx_formats(self, book):
        return {
            'title': book.add_format({'bold': True, 'font_size': 14}),
            'meta': book.add_format({'font_size': 9, 'font_color': '#5b6570'}),
            'header': book.add_format({
                'bold': True, 'bg_color': '#f1f3f5', 'border': 1, 'align': 'center',
                'valign': 'vcenter', 'text_wrap': True,
            }),
            'cell': book.add_format({'border': 1, 'font_size': 10, 'valign': 'vcenter'}),
            'date': book.add_format({'border': 1, 'font_size': 10, 'num_format': 'dd/mm/yyyy'}),
            'number': book.add_format({'border': 1, 'font_size': 10, 'num_format': '0.##'}),
            'percent': book.add_format({'border': 1, 'font_size': 10, 'num_format': '0%'}),
            'project': book.add_format({'bold': True, 'border': 1, 'bg_color': '#e9ecef', 'font_size': 10}),
            'critical': book.add_format({'border': 1, 'font_size': 10, 'font_color': '#c0392b', 'bold': True}),
        }

    @api.model
    def _xlsx_tasks_sheet(self, book, matrix):
        formats = self._xlsx_formats(book)
        sheet = book.add_worksheet(_("Tareas"))
        sheet.freeze_panes(4, 2)

        sheet.write(0, 0, matrix['title'], formats['title'])
        sheet.write(1, 0, _("Generado el %s", matrix['generated_on'].strftime('%d/%m/%Y %H:%M')),
                    formats['meta'])

        headers = [
            (_("EDT"), 8), (_("Tarea"), 46), (_("Proyecto"), 24), (_("Inicio"), 12),
            (_("Fin"), 12), (_("Días"), 7), (_("Personas asignadas"), 26), (_("Etapa"), 16),
            (_("Avance"), 9), (_("Horas"), 8), (_("Holgura (h)"), 11), (_("Desvío (d)"), 11),
        ]
        for column, (label, width) in enumerate(headers):
            sheet.write(3, column, label, formats['header'])
            sheet.set_column(column, column, width)

        for index, row in enumerate(matrix['rows'], start=4):
            base = formats['project'] if row['is_project'] else formats['cell']
            name_format = formats['critical'] if row['critical'] and not row['is_project'] else base
            start = self._to_date(row['start'])
            end = self._to_date(row['end'])
            days = (end - start).days + 1 if start and end else None

            sheet.write(index, 0, row['code'], base)
            sheet.write(index, 1, f"{'    ' * row['level']}{row['name']}", name_format)
            sheet.write(index, 2, row['project_name'] or '', base)
            sheet.write_datetime(index, 3, start, formats['date']) if start else sheet.write(index, 3, '', base)
            sheet.write_datetime(index, 4, end, formats['date']) if end else sheet.write(index, 4, '', base)
            sheet.write(index, 5, days if days is not None else '', formats['number'])
            sheet.write(index, 6, row['users'], base)
            sheet.write(index, 7, row['stage'], base)
            sheet.write(index, 8, (row['progress'] or 0) / 100.0, formats['percent'])
            sheet.write(index, 9, row['allocated_hours'] or 0, formats['number'])
            sheet.write(index, 10, row['slack_hours'] if row['slack_hours'] is not None else '',
                        formats['number'])
            sheet.write(index, 11, row['baseline_variance'] if row['baseline_variance'] is not None else '',
                        formats['number'])

    @api.model
    def _xlsx_chart_sheet(self, book, matrix):
        """El diagrama propiamente dicho: una columna por periodo y la barra
        pintada con el color del estado de la tarea."""
        formats = self._xlsx_formats(book)
        sheet = book.add_worksheet(_("Diagrama"))
        sheet.freeze_panes(5, 2)
        sheet.set_column(0, 0, 8)
        sheet.set_column(1, 1, 42)

        sheet.write(0, 0, matrix['title'], formats['title'])
        sheet.write(1, 0, _("Escala: %s", matrix['scale']), formats['meta'])

        periods = matrix['periods']
        # Cabecera de dos niveles: grupo (mes o año) y periodo.
        group_start = 0
        for index, period in enumerate(periods):
            column = 2 + index
            sheet.set_column(column, column, 3.6)
            sheet.write(4, column, period['label'], formats['header'])
            is_last = index == len(periods) - 1
            if is_last or periods[index + 1]['group'] != period['group']:
                first_column = 2 + group_start
                if first_column == column:
                    sheet.write(3, column, period['group'], formats['header'])
                else:
                    sheet.merge_range(3, first_column, 3, column, period['group'], formats['header'])
                group_start = index + 1

        sheet.write(3, 0, _("EDT"), formats['header'])
        sheet.write(3, 1, _("Tarea"), formats['header'])
        sheet.write(4, 0, '', formats['header'])
        sheet.write(4, 1, '', formats['header'])

        bar_cache = {}
        for index, row in enumerate(matrix['rows'], start=5):
            base = formats['project'] if row['is_project'] else formats['cell']
            sheet.write(index, 0, row['code'], base)
            sheet.write(index, 1, f"{'    ' * row['level']}{row['name']}", base)
            color = row['color'] or '#714b67'
            if color not in bar_cache:
                bar_cache[color] = book.add_format({'bg_color': color, 'border': 1})
            for cell_index, filled in enumerate(row['cells']):
                sheet.write(index, 2 + cell_index, '',
                            bar_cache[color] if filled else formats['cell'])

    @api.model
    def export_xlsx_base64(self, project_ids=None, options=None):
        """Igual que `export_xlsx`, en base64 (para clientes que no descargan)."""
        return base64.b64encode(self.export_xlsx(project_ids, options)).decode()
