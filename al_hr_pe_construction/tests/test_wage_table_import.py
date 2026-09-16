# -*- coding: utf-8 -*-
"""Importación de la tabla del convenio desde su PDF.

El PDF de prueba imita al de la FTCCP con un convenio 2027 ficticio cuyos
importes semanales cuadran con las fórmulas del módulo:

    operario 92.00 → CONAF 12.88, ONP 106.68, neto 755.08
    oficial  72.00 → CONAF 10.08, ONP  82.37, neto 595.15
    peón     64.50 → CONAF  9.03, ONP  73.79, neto 538.78
"""
import base64
import io
from datetime import date
from unittest.mock import patch

from reportlab.pdfgen import canvas

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.hr_construction_wage_import import L10nPeHrConstructionWageTable
from ..tools import wage_table_pdf

URL = 'https://example.com/tabla-salarial-2027.pdf'
ROWS = (
    ('OPERARIO', '92.00', '552.00', '32', '29.44', '176.64', '106.68', '12.88', '755.08'),
    ('OFICIAL', '72.00', '432.00', '30', '21.60', '129.60', '82.37', '10.08', '595.15'),
    ('PEÓN', '64.50', '387.00', '30', '19.35', '116.10', '73.79', '9.03', '538.78'),
)


def build_pdf(rows=ROWS, validity='Vigente del 01.01.2027 al 31.12.2027'):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 800
    lines = ['TABLA SALARIAL SIN BENEFICIOS SOCIALES',
             'Resolución Ministerial N° 123-2026-TR (%s)' % validity]
    for name, wage, week, buc, buc_day, buc_week, onp, conaf, net in rows:
        lines += [
            name,
            'Jornal Básico %s * 6 días %s' % (wage, week),
            'BUC %s %% %s * 6 días %s' % (buc, buc_day, buc_week),
            'Bonif. por Movilidad 9.00 * 6 días 54.00',
            'Descuento ONP 13%% %s' % onp,
            'Descuento CONAF. 2%% %s' % conaf,
            'Pago Neto Semanal %s' % net,
        ]
    for line in lines:
        pdf.drawString(40, y, line)
        y -= 18
    pdf.save()
    return buffer.getvalue()


@tagged('post_install', '-at_install')
class TestWageTableImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Table = cls.env['l10n_pe.hr.construction.wage.table']
        cls.operario = cls.env.ref('al_hr_pe_construction.category_operario')
        cls.peon = cls.env.ref('al_hr_pe_construction.category_peon')

    def _find_2027(self):
        return self.Table.with_context(active_test=False).search([
            ('company_id', '=', False), ('date_from', '=', '2027-01-01')])

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def test_parse_generated_pdf(self):
        data = wage_table_pdf.parse_pdf(build_pdf())
        self.assertEqual(data['date_from'], date(2027, 1, 1))
        self.assertEqual(data['date_to'], date(2027, 12, 31))
        self.assertEqual(data['resolution'], 'R.M. N.° 123-2026-TR')
        operario = data['categories']['operario']
        self.assertEqual(operario['daily_wage'], 92.0)
        self.assertEqual(operario['mobility'], 9.0)
        self.assertEqual(operario['buc_percent'], 32.0)
        self.assertEqual(operario['conafovicer_rate'], 2.0)
        self.assertEqual(operario['net'], 755.08)
        self.assertEqual(data['categories']['peon']['daily_wage'], 64.5)

    def test_parse_capeco_layout(self):
        """Texto como lo extrae el PDF de CAPECO: palabras partidas y
        columnas vecinas pegadas a los importes."""
        text = (
            'CUADRO DE REMUNERACIONES JORNALES VIGENTES DEL 01.01.2026 AL 31.12.2026\n'
            'Jornal Básico 89.30  x 6 535.80 DIARIO MENSUAL TOTAL\n'
            'Dominical 89.30 S.N.P. 13% 103.55\n'
            'B.Movilidad(***) 8.60  x 6 51.60 CONAFOV. 2% (**) 12.50 OPERARIO (S/.) 17.01\n'
            'B.U.C. 32% 28.58  x 6 171.46 116.05 Neto Semanal 732.10\n'
            'Jornal Básico 69.75  x 6 418.50\n'
            'Dominical 69.75 S.N.P. 13% 79.79\n'
            'B.Movilidad(***) 8.60  x 6 51.60 CONAFOV. 2% (**) 9.77\n'
            'B.U.C. 30% 20.93  x 6 125.55 Neto Semanal 575.84\n'
            'Jornal Básico 62.80  x 6 376.80\n'
            'Dominical 62.80 S.N.P. 13% 71.84\n'
            'B.Movilidad(***) 8.60  x 6 51.60 CONAFOV. 2% (**) 8.79\n'
            'B.U.C. 30% 18.84  x 6 113.04 Neto Semanal 523.60\n')
        data = wage_table_pdf.parse_text(text)
        self.assertEqual(data['resolution'], '')
        self.assertEqual(
            [data['categories'][key]['daily_wage'] for key in wage_table_pdf.CATEGORIES],
            [89.30, 69.75, 62.80])
        self.assertEqual(data['categories']['oficial']['pension'], 79.79)
        # La tabla 2026 cargada con el módulo cuadra con su propio PDF.
        self.assertEqual(self.Table._l10n_pe_check_parsed(data), [])

    def test_not_a_pdf(self):
        with self.assertRaises(wage_table_pdf.WageTablePdfError):
            wage_table_pdf.parse_pdf(b'<html>no encontrado</html>')

    def test_pdf_without_validity(self):
        with self.assertRaisesRegex(UserError, 'vigencia'):
            self.Table._l10n_pe_create_from_pdf(build_pdf(validity='sin fecha'), URL)

    # ------------------------------------------------------------------
    # Creación
    # ------------------------------------------------------------------
    def test_import_creates_archived_table(self):
        table, created = self.Table._l10n_pe_create_from_pdf(build_pdf(), URL)
        self.assertTrue(created)
        self.assertFalse(table.active)
        self.assertEqual(table.name, 'Convención colectiva 2027')
        self.assertEqual(table.resolution, 'R.M. N.° 123-2026-TR')
        self.assertEqual(table.source_url, URL)
        self.assertEqual(len(table.line_ids), 3)
        line = table.line_ids.filtered(lambda l: l.category_id == self.operario)
        self.assertEqual(line.daily_wage, 92.0)
        self.assertEqual(line.mobility_amount, 9.0)
        # El BUC coincide con la categoría: la línea no lo fija.
        self.assertFalse(line.buc_percent)
        self.assertEqual(line._period_total(6), 874.64)
        self.assertIn('cuadran', table.message_ids[:1].body)
        # Archivada: la planilla sigue usando la tabla vigente.
        self.assertFalse(self.Table._get_table_for_date(date(2027, 3, 1)))

    def test_mismatch_imports_nothing(self):
        rows = list(ROWS)
        rows[1] = rows[1][:8] + ('600.00',)
        with self.assertRaisesRegex(UserError, 'no cuadra'):
            self.Table._l10n_pe_create_from_pdf(build_pdf(rows), URL)
        self.assertFalse(self._find_2027())

    def test_existing_validity_is_not_duplicated(self):
        first, created = self.Table._l10n_pe_create_from_pdf(build_pdf(), URL)
        again, created_again = self.Table._l10n_pe_create_from_pdf(build_pdf(), URL)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first, again)

    def test_conafovicer_rate_warning(self):
        company = self.env['res.company'].create({
            'name': 'Constructora Tasa Distinta',
            'country_id': self.env.ref('base.pe').id,
            'l10n_pe_conafovicer_rate': 1.5,
        })
        table, _created = self.Table._l10n_pe_create_from_pdf(build_pdf(), URL)
        self.assertIn(company.name, table.message_ids[:1].body)

    # ------------------------------------------------------------------
    # Asistente y acción planificada
    # ------------------------------------------------------------------
    def _wizard(self, **vals):
        return self.env['l10n_pe.hr.construction.wage.import'].create(vals)

    def test_wizard_file_opens_the_new_table(self):
        wizard = self._wizard(source='file', pdf_filename='tabla2027.pdf',
                              pdf_file=base64.b64encode(build_pdf()))
        action = wizard.action_import()
        table = self._find_2027()
        self.assertEqual(action['res_id'], table.id)
        self.assertEqual(table.source_url, 'tabla2027.pdf')

    def test_wizard_url_is_watched(self):
        wizard = self._wizard(source='url', url=URL, watched_urls='')
        with patch.object(L10nPeHrConstructionWageTable, '_l10n_pe_download_pdf',
                          return_value=build_pdf()):
            wizard.action_import()
        self.assertEqual(self.Table._l10n_pe_watched_urls(), [URL])

    def test_wizard_rejects_loaded_validity(self):
        self.Table._l10n_pe_create_from_pdf(build_pdf(), URL)
        wizard = self._wizard(source='file', pdf_file=base64.b64encode(build_pdf()))
        with self.assertRaisesRegex(UserError, 'Ya existe'):
            wizard.action_import()

    def test_cron_imports_once_and_schedules_review(self):
        manager = self.env['res.users'].create({
            'name': 'Jefe de planillas', 'login': 'jefe.planillas.cc',
            'group_ids': [(4, self.env.ref('hr_payroll.group_hr_payroll_manager').id)],
        })
        self.env['ir.config_parameter'].set_param(
            'al_hr_pe_construction.wage_table_urls',
            '# comentario\n%s\nhttps://example.com/roto.pdf' % URL)

        def download(model, url):
            if url == URL:
                return build_pdf()
            raise UserError('404')

        with patch.object(L10nPeHrConstructionWageTable, '_l10n_pe_download_pdf',
                          autospec=True, side_effect=download):
            created = self.Table._l10n_pe_check_watched_urls()
            again = self.Table._l10n_pe_check_watched_urls()
        self.assertEqual(len(created), 1)
        self.assertFalse(again)
        activity = created.activity_ids.filtered(lambda a: a.user_id == manager)
        self.assertEqual(activity.summary, 'Revisar y activar la tabla salarial')

    def test_cron_is_registered(self):
        cron = self.env.ref('al_hr_pe_construction.ir_cron_construction_wage_tables')
        self.assertEqual(cron.interval_type, 'months')
        self.assertTrue(self.Table._l10n_pe_watched_urls())
