# -*- coding: utf-8 -*-
"""Exportación a Excel y PDF, generadas en el servidor."""
import io
import zipfile
from datetime import timedelta

from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import GanttCommon


@tagged('post_install', '-at_install')
class TestGanttExport(GanttCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.task_a = cls._create_task('A — expediente', day_offset=0, duration_days=10)
        cls.task_b = cls._create_task('B — obra', day_offset=10, duration_days=20)
        cls.task_child = cls._create_task(
            'B.1 — excavación', day_offset=10, duration_days=5, parent_id=cls.task_b.id,
        )
        cls.task_b.depend_on_ids = [(6, 0, cls.task_a.ids)]

    def _matrix(self, options=None):
        return self.env(user=self.gantt_user)['al.gantt.data'].build_matrix(
            [self.project.id], options or {},
        )

    # ------------------------------------------------------------------
    # Matriz común
    # ------------------------------------------------------------------
    def test_rows_follow_the_tree_with_wbs_codes(self):
        matrix = self._matrix()
        codes = {row['name']: row['code'] for row in matrix['rows']}
        self.assertEqual(codes['A — expediente'], '1')
        self.assertEqual(codes['B — obra'], '2')
        self.assertEqual(codes['B.1 — excavación'], '2.1',
                         "La subtarea hereda el código de su padre")
        levels = {row['name']: row['level'] for row in matrix['rows']}
        self.assertEqual(levels['B.1 — excavación'], levels['B — obra'] + 1)

    def test_periods_cover_the_plan(self):
        matrix = self._matrix({'scale': 'week'})
        self.assertTrue(matrix['periods'])
        first = matrix['periods'][0]['start']
        last = matrix['periods'][-1]['end']
        self.assertLessEqual(first, self.base_date.date())
        self.assertGreaterEqual(last, (self.base_date + timedelta(days=30)).date())

    def test_cells_mark_the_bar_span(self):
        matrix = self._matrix({'scale': 'week'})
        row = next(row for row in matrix['rows'] if row['name'] == 'A — expediente')
        self.assertIn(True, row['cells'], "La tarea debe ocupar alguna columna")
        self.assertEqual(len(row['cells']), len(matrix['periods']))

    def test_scale_grows_when_the_plan_is_long(self):
        """Con un plan largo, la escala sube sola para no pasar de 60 columnas."""
        self._create_task('Muy larga', day_offset=0, duration_days=900)
        matrix = self._matrix({'scale': 'day'})
        self.assertNotEqual(matrix['scale'], 'day')
        self.assertLessEqual(len(matrix['periods']), 60)

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    def test_xlsx_has_both_sheets(self):
        content = self.env(user=self.gantt_user)['al.gantt.data'].export_xlsx([self.project.id], {})
        self.assertTrue(content.startswith(b'PK'), "Un XLSX es un ZIP")
        with zipfile.ZipFile(io.BytesIO(content)) as book:
            workbook = book.read('xl/workbook.xml').decode()
            self.assertIn('Tareas', workbook)
            self.assertIn('Diagrama', workbook)
            strings = book.read('xl/sharedStrings.xml').decode()
            self.assertIn('A — expediente', strings)
            self.assertIn('EDT', strings)

    def test_xlsx_respects_filters(self):
        content = self.env(user=self.gantt_user)['al.gantt.data'].export_xlsx(
            [self.project.id], {'states': ['1_canceled']},
        )
        with zipfile.ZipFile(io.BytesIO(content)) as book:
            strings = book.read('xl/sharedStrings.xml').decode()
        self.assertNotIn('A — expediente', strings,
                         "El Excel exporta lo mismo que se está viendo")

    def test_export_requires_the_gantt_group(self):
        plain_user = self.env['res.users'].create({
            'name': 'Sin Gantt', 'login': 'gantt.export.plain@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.env(user=plain_user)['al.gantt.data'].export_xlsx([self.project.id], {})

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    def test_report_renders(self):
        """El informe se compone sin errores.

        En modo test Odoo no llama a wkhtmltopdf y devuelve el HTML; se aceptan
        los dos resultados y se comprueba el contenido, que es lo que importa.
        """
        content, extension = self.env['ir.actions.report']._render_qweb_pdf(
            'al_project_gantt_base.report_gantt', [self.project.id],
            data={'project_ids': [self.project.id], 'options': {'scale': 'week'}},
        )
        self.assertIn(extension, ('pdf', 'html'))
        self.assertGreater(len(content), 1000)
        if extension == 'pdf':
            self.assertTrue(content.startswith(b'%PDF'))
        else:
            html = content.decode()
            self.assertIn('algantt-grid', html)
            self.assertIn('A — expediente', html)

    def test_report_values_include_groups_and_legend(self):
        values = self.env['report.al_project_gantt_base.report_gantt']._get_report_values(
            [self.project.id],
            data={'project_ids': [self.project.id], 'options': {'scale': 'week'}},
        )
        self.assertTrue(values['rows'])
        self.assertTrue(values['periods'])
        self.assertEqual(
            sum(group['count'] for group in values['period_groups']),
            len(values['periods']),
            "Las cabeceras agrupadas deben cubrir todas las columnas",
        )
        self.assertTrue(all(entry['color'] for entry in values['legend']))
