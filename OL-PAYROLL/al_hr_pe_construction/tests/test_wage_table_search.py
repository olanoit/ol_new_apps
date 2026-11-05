# -*- coding: utf-8 -*-
"""Búsqueda de la tabla por página, frecuencia, registro y alerta por falta de tabla."""
from datetime import date, datetime
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.hr_construction_wage_import import (
    L10nPeHrConstructionWageTable as TableClass,
    WageTablePageNotFound,
    same_url,
)
from ..tools.wage_table_links import find_links
from .test_wage_table_import import build_pdf

FTCCP = 'https://www.ftccperu.com/index.php/es/formacion/biblioteca'
FTCCP_PAGE = """<html><body>
  <a href="/images/TABLAS%20SALARIALES%20PDF/Tabla%20Salarial%202022-2023.pdf">Clic</a>
  <a href="/media/attachments/2025/12/30/tablas-salariales-2026-construccion-civil.pdf">Clic</a>
  <a href="/media/attachments/2026/12/09/tablas-salariales-2027-construccion-civil.pdf">Clic</a>
  <a href="/media/attachments/2027/01/05/derechos-laborales-construccion-civil-2027.pdf">Clic</a>
  <a href="/media/attachments/2026/12/09/rm-120-2026-tr.pdf">Clic</a>
  <a href="/index.php/es/noticias">Noticias</a></body></html>"""
NEW_PDF = 'https://www.ftccperu.com/media/attachments/2026/12/09/tablas-salariales-2027-construccion-civil.pdf'
CAPECO = 'https://www.capeco.org/'
CAPECO_HOME = """<a href="https://capeco.org/documentos-de-la-convencion-colectiva-2026-del-sector-construccion/">Vieja</a>
  <a href="https://capeco.org/documentos-de-la-convencion-colectiva-2027-del-sector-construccion/">Documentos</a>
  <a href="https://otro.example.com/documentos-de-la-convencion-colectiva-2027/">Ajena</a>"""
CAPECO_PAGE = 'https://capeco.org/documentos-de-la-convencion-colectiva-2027-del-sector-construccion/'
CAPECO_DOCS = """<a href="https://www.capeco.org/descargas/CC2027/RM_100-2026-TR.pdf">Resolución Ministerial</a>
  <a href="https://www.capeco.org/descargas/CC2027/CAPECO_FTCCP 2027 FV.pdf">Tablas Salariales 2027 del Sector</a>"""


@tagged('post_install', '-at_install')
class TestWageTableLinks(TransactionCase):

    def test_ftccp_library(self):
        pdfs, pages = find_links(FTCCP_PAGE, FTCCP, 2027)
        self.assertEqual(pdfs, [NEW_PDF], 'ni las anteriores, ni la cartilla, ni la R.M.')
        self.assertEqual(pages, [])

    def test_year_comes_from_the_name_not_the_folder(self):
        pdfs, _pages = find_links(FTCCP_PAGE, FTCCP, 2026)
        self.assertIn(
            'https://www.ftccperu.com/media/attachments/2025/12/30/'
            'tablas-salariales-2026-construccion-civil.pdf', pdfs)

    def test_capeco_goes_through_its_agreement_page(self):
        pdfs, pages = find_links(CAPECO_HOME, CAPECO, 2027)
        self.assertEqual(pdfs, [])
        self.assertEqual(pages, [CAPECO_PAGE], 'ni la del año pasado ni la de otro dominio')
        pdfs, _pages = find_links(CAPECO_DOCS, CAPECO_PAGE, 2027)
        self.assertEqual(pdfs, ['https://www.capeco.org/descargas/CC2027/CAPECO_FTCCP%202027%20FV.pdf'])

    def test_pdf_without_year_is_kept(self):
        pdfs, _pages = find_links('<a href="/x/tabla-salarial-vigente.pdf">Ver</a>', FTCCP, 2027)
        self.assertEqual(len(pdfs), 1)

    def test_empty_page(self):
        self.assertEqual(find_links('', FTCCP, 2027), ([], []))

    def test_same_url(self):
        self.assertTrue(same_url(
            'https://www.capeco.org/a/Tabla%202026.pdf', 'https://capeco.org/a/Tabla 2026.pdf'))
        self.assertFalse(same_url('https://capeco.org/a.pdf', 'https://capeco.org/b.pdf'))


class _Web:
    """Direcciones de mentira: las que no están dan 404."""

    def __init__(self, pages=None, pdfs=None):
        self.pages = pages or {}
        self.pdfs = pdfs or {}
        self.downloaded = []

    def page(self, model, url):
        self.downloaded.append(url)
        if isinstance(self.pages.get(url), Exception):
            raise self.pages[url]
        if url not in self.pages:
            raise WageTablePageNotFound('%s no existe.' % url)
        return self.pages[url]

    def pdf(self, model, url):
        self.downloaded.append(url)
        if url not in self.pdfs:
            raise UserError('No se pudo descargar %s' % url)
        return self.pdfs[url]


@tagged('post_install', '-at_install')
class TestWageTableSearch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Table = cls.env['l10n_pe.hr.construction.wage.table']
        cls.Check = cls.env['l10n_pe.hr.construction.wage.check']
        cls.Check.search([]).unlink()
        parameters = cls.env['ir.config_parameter']
        parameters.set_param('al_hr_pe_construction.wage_table_pages',
                             '\n'.join((FTCCP, CAPECO)))
        parameters.set_param('al_hr_pe_construction.wage_table_urls', '# ninguna')
        cls.manager = cls.env['res.users'].create({
            'name': 'Jefe de planillas', 'login': 'jefe.busqueda.cc',
            'group_ids': [(4, cls.env.ref('hr_payroll.group_hr_payroll_manager').id)],
        })

    def _run(self, web):
        with patch.object(TableClass, '_l10n_pe_download_pdf', autospec=True,
                          side_effect=web.pdf), \
             patch.object(TableClass, '_l10n_pe_download_page', autospec=True,
                          side_effect=web.page):
            return self.Check._l10n_pe_run()

    def test_new_pdf_on_the_page_is_imported_archived_and_only_once(self):
        web = _Web({FTCCP: FTCCP_PAGE, CAPECO: ''}, {NEW_PDF: build_pdf()})
        check = self._run(web)
        self.assertEqual(check.state, 'imported')
        self.assertEqual(check.target_year, 2027)
        table = check.line_ids.filtered(lambda l: l.result == 'imported').table_id
        self.assertFalse(table.active, 'sigue entrando archivada')
        self.assertEqual(table.source_url, NEW_PDF)
        self.assertEqual(table.date_from, date(2027, 1, 1))
        self.assertIn(self.manager, table.activity_ids.user_id)
        total = self.Table.with_context(active_test=False).search_count([])
        # La misma página con el año ya cubierto: el enlace 2027 ya no es del año buscado.
        again = self._run(web)
        self.assertEqual(again.target_year, 2028)
        self.assertEqual(again.state, 'nothing')
        self.assertEqual(self.Table.with_context(active_test=False).search_count([]), total)

    def test_same_validity_does_not_duplicate_and_fills_the_source(self):
        web = _Web({FTCCP: FTCCP_PAGE, CAPECO: ''}, {NEW_PDF: build_pdf()})
        table = self.Table.create({
            'name': 'Cargada a mano', 'date_from': date(2027, 1, 1), 'date_to': date(2027, 12, 31),
            'active': False})
        self.env['ir.config_parameter'].set_param(
            'al_hr_pe_construction.wage_table_urls', NEW_PDF)
        total = self.Table.with_context(active_test=False).search_count([])
        check = self._run(web)
        self.assertEqual(self.Table.with_context(active_test=False).search_count([]), total)
        backup = check.line_ids.filtered(lambda l: l.kind == 'backup')
        self.assertEqual(backup.result, 'existing')
        self.assertEqual(table.source_url, NEW_PDF)

    def test_capeco_is_followed_one_level(self):
        pdf = 'https://www.capeco.org/descargas/CC2027/CAPECO_FTCCP%202027%20FV.pdf'
        web = _Web({FTCCP: '', CAPECO: CAPECO_HOME, CAPECO_PAGE: CAPECO_DOCS}, {pdf: build_pdf()})
        check = self._run(web)
        self.assertEqual(check.state, 'imported')
        self.assertEqual(check.line_ids.filtered(lambda l: l.result == 'imported').kind, 'pdf')

    def test_page_reached_by_a_link_is_not_checked_twice(self):
        """CAPECO enlaza desde su portada la misma página que se vigila."""
        self.env['ir.config_parameter'].set_param(
            'al_hr_pe_construction.wage_table_pages', '\n'.join((CAPECO, CAPECO_PAGE)))
        web = _Web({CAPECO: CAPECO_HOME, CAPECO_PAGE: ''})
        check = self._run(web)
        self.assertEqual(web.downloaded.count(CAPECO_PAGE), 1)
        self.assertEqual(check.line_ids.mapped('url'), [CAPECO, CAPECO_PAGE])

    def test_backup_is_not_downloaded_twice(self):
        self.env['ir.config_parameter'].set_param(
            'al_hr_pe_construction.wage_table_urls', NEW_PDF.replace('www.', ''))
        web = _Web({FTCCP: FTCCP_PAGE, CAPECO: ''}, {NEW_PDF: build_pdf()})
        check = self._run(web)
        self.assertEqual(web.downloaded.count(NEW_PDF), 1)
        self.assertFalse(check.line_ids.filtered(lambda l: l.kind == 'backup'))

    def test_page_not_published_yet_is_not_an_error(self):
        self.env['ir.config_parameter'].set_param(
            'al_hr_pe_construction.wage_table_pages',
            'https://capeco.org/convencion-{year}/')
        check = self._run(_Web())
        self.assertEqual(check.line_ids.url, 'https://capeco.org/convencion-2027/')
        self.assertEqual(check.line_ids.result, 'not_found')
        self.assertEqual(check.state, 'nothing')

    def test_errors_are_recorded_and_do_not_stop_the_others(self):
        web = _Web({FTCCP: UserError('La página no responde'), CAPECO: ValueError('rara')})
        check = self._run(web)
        self.assertEqual(check.state, 'failed')
        self.assertEqual(check.line_ids.mapped('result'), ['error', 'error'])
        self.assertEqual(check.line_ids[0].message, 'La página no responde')
        self.assertIn('ValueError', check.line_ids[1].message)
        partial = self._run(_Web({FTCCP: '', CAPECO: UserError('Falla')}))
        self.assertEqual(partial.state, 'partial')

    def test_bad_pdf_is_recorded(self):
        web = _Web({FTCCP: FTCCP_PAGE, CAPECO: ''}, {NEW_PDF: b'no es un pdf'})
        check = self._run(web)
        line = check.line_ids.filtered(lambda l: l.kind == 'pdf')
        self.assertEqual(line.result, 'error')
        self.assertTrue(line.message)

    def test_removing_every_address_is_respected(self):
        wizard = self.env['l10n_pe.hr.construction.wage.import'].create(
            {'watched_urls': '', 'watched_pages': ''})
        wizard._save_watched_urls()
        self.assertEqual(self.Table._l10n_pe_watched_urls(), [])
        self.assertEqual(self.Table._l10n_pe_watched_pages(), [])

    def test_search_now_opens_the_record(self):
        with patch.object(TableClass, '_l10n_pe_download_page', autospec=True,
                          side_effect=_Web({FTCCP: '', CAPECO: ''}).page):
            action = self.Check.action_search_now()
        check = self.Check.browse(action['res_id'])
        self.assertEqual(check.trigger, 'manual')

    # ------------------------------------------------------------------
    # Frecuencia
    # ------------------------------------------------------------------
    def _last_run(self, when, state_line='no_news'):
        check = self.Check.create({'date': when})
        check._l10n_pe_log('https://capeco.org/', 'page', state_line)
        return check

    def test_first_run_is_due(self):
        self.assertTrue(self.Check._l10n_pe_is_due(date(2026, 11, 10)))

    def test_monthly_outside_the_window(self):
        self._last_run(datetime(2026, 10, 19))
        self.assertFalse(self.Check._l10n_pe_is_due(date(2026, 10, 30)))
        self.assertTrue(self.Check._l10n_pe_is_due(date(2026, 11, 1)))

    def test_december_first_runs_even_after_a_recent_run(self):
        self._last_run(datetime(2026, 11, 28))
        self.assertTrue(self.Check._l10n_pe_is_due(date(2026, 12, 1)))

    def test_weekly_in_the_window(self):
        self._last_run(datetime(2026, 12, 1))
        self.assertFalse(self.Check._l10n_pe_is_due(date(2026, 12, 7)))
        self.assertTrue(self.Check._l10n_pe_is_due(date(2026, 12, 8)))

    def test_weekly_in_january_counts_from_december(self):
        self._last_run(datetime(2026, 12, 29))
        self.assertFalse(self.Check._l10n_pe_is_due(date(2027, 1, 4)))
        self.assertTrue(self.Check._l10n_pe_is_due(date(2027, 1, 5)))

    def test_failed_run_is_retried(self):
        self._last_run(datetime(2026, 12, 1), 'error')
        self.assertTrue(self.Check._l10n_pe_is_due(date(2026, 12, 2)))

    def test_cron_skips_download_when_not_due_but_checks_coverage(self):
        self._last_run(datetime(2026, 10, 19))
        with freeze_time('2026-10-20'), \
             patch.object(type(self.Check), '_l10n_pe_run', autospec=True) as run, \
             patch.object(type(self.Check), '_l10n_pe_check_coverage', autospec=True) as coverage:
            self.Table._cron_l10n_pe_check_wage_tables()
        run.assert_not_called()
        coverage.assert_called_once()


@tagged('post_install', '-at_install')
class TestWageTableAlert(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Table = cls.env['l10n_pe.hr.construction.wage.table']
        cls.Check = cls.env['l10n_pe.hr.construction.wage.check']
        cls.company = cls.env['res.company'].create(
            {'name': 'Obras Alerta S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.Table = cls.env['l10n_pe.hr.construction.wage.table']
        cls.Check = cls.env['l10n_pe.hr.construction.wage.check']
        cls.manager = cls.env['res.users'].create({
            'name': 'Jefe alerta', 'login': 'jefe.alerta.cc',
            'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(4, cls.env.ref('hr_payroll.group_hr_payroll_manager').id)],
        })
        employee = cls.env['hr.employee'].create(
            {'name': 'Operario alerta', 'company_id': cls.company.id})
        employee.version_id.write({
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id':
                cls.env.ref('al_hr_pe_construction.category_operario').id,
        })
        cls.employee = employee
        cls.missing = cls.env.ref('al_hr_pe_construction.activity_wage_table_missing')
        cls.urgent = cls.env.ref('al_hr_pe_construction.activity_wage_table_urgent')

    def _activities(self):
        return self.env['mail.activity'].search([
            ('res_model', '=', self.Table._name), ('user_id', '=', self.manager.id),
            ('activity_type_id', 'in', (self.missing | self.urgent).ids)])

    def _table(self, year, active):
        return self.Table.create({
            'name': 'Convenio %s' % year, 'date_from': date(year, 1, 1),
            'date_to': date(year, 12, 31), 'active': active})

    def test_quiet_before_december(self):
        self.Check._l10n_pe_check_coverage(date(2026, 11, 30))
        self.assertFalse(self._activities())

    def test_december_without_next_year_table(self):
        self.Check._l10n_pe_check_coverage(date(2026, 12, 1))
        activity = self._activities()
        self.assertEqual(activity.activity_type_id, self.missing)
        self.Check._l10n_pe_check_coverage(date(2026, 12, 2))
        self.assertEqual(len(self._activities()), 1, 'no se repite cada día')

    def test_archived_table_is_enough_in_december(self):
        self._table(2027, active=False)
        self.Check._l10n_pe_check_coverage(date(2026, 12, 1))
        self.assertFalse(self._activities())

    def test_activity_closes_when_the_table_arrives(self):
        self.Check._l10n_pe_check_coverage(date(2026, 12, 1))
        self.assertTrue(self._activities())
        self._table(2027, active=False)
        self.Check._l10n_pe_check_coverage(date(2026, 12, 2))
        self.assertFalse(self._activities())

    def test_january_without_active_table_is_urgent(self):
        self._table(2027, active=False)
        self.Check._l10n_pe_check_coverage(date(2027, 1, 1))
        activity = self._activities()
        self.assertEqual(activity.activity_type_id, self.urgent)
        self.assertEqual(activity.activity_type_id.decoration_type, 'danger')
        self.assertEqual(activity.date_deadline, date(2027, 1, 1))
        self.assertIn('archivada', activity.note)

    def test_urgent_replaces_the_december_activity(self):
        self.Check._l10n_pe_check_coverage(date(2026, 12, 31))
        self.Check._l10n_pe_check_coverage(date(2027, 1, 1))
        self.assertEqual(self._activities().activity_type_id, self.urgent)

    def test_no_alert_without_construction_workers(self):
        self.employee.version_id.write({'l10n_pe_labor_regime': 'general'})
        self.env.flush_all()
        self.Check._l10n_pe_check_coverage(date(2027, 1, 1))
        self.assertFalse(self._activities())

    def _payslip(self):
        return self.env['hr.payslip'].create({
            'name': 'Semana enero', 'employee_id': self.employee.id,
            'company_id': self.company.id,
            'struct_id': self.env.ref('al_hr_pe_construction.construction_structure').id,
            'date_from': date(2027, 1, 4), 'date_to': date(2027, 1, 10),
        })

    def test_payslip_warns_when_there_is_no_active_table(self):
        payslip = self._payslip()
        with patch.object(type(self.env.user), '_bus_send', autospec=True) as send:
            payslip.compute_sheet()
        self.assertEqual(payslip, payslip._l10n_pe_wage_table_missing())
        messages = [issue['message'] for issue in (payslip.issues or {}).values()]
        self.assertTrue(any('tabla salarial' in message for message in messages), messages)
        titles = [call.args[2].get('title') for call in send.call_args_list
                  if call.args[1] == 'simple_notification']
        self.assertIn('Falta la tabla salarial de construcción civil', titles)

    def test_payslip_is_quiet_once_the_table_is_active(self):
        payslip = self._payslip()
        self.assertTrue(payslip._l10n_pe_wage_table_missing())
        self._table(2027, active=True)
        self.assertFalse(payslip._l10n_pe_wage_table_missing())
        with patch.object(type(self.env.user), '_bus_send', autospec=True) as send:
            payslip.compute_sheet()
        self.assertFalse([call for call in send.call_args_list
                          if call.args[1] == 'simple_notification'
                          and 'tabla' in str(call.args[2].get('title'))])
        messages = [issue['message'] for issue in (payslip.issues or {}).values()]
        self.assertFalse(any('tabla salarial' in message for message in messages))
