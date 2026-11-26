# -*- coding: utf-8 -*-
import json

from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.ir_actions_report import PREVIEW_SCOPE_PARAM

REPORT = 'base.report_irmodulereference'


@tagged('post_install', '-at_install')
class TestReportPreviewConfig(TransactionCase):
    """Qué reportes se abren en el navegador según el ajuste general y el reporte."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env['ir.actions.report']._get_report_from_name(REPORT)
        cls.module = cls.env['ir.module.module'].search([('name', '=', 'base')])

    def _scope(self, value):
        self.env['ir.config_parameter'].set_param(PREVIEW_SCOPE_PARAM, value)
        self.report.invalidate_recordset(['al_preview_in_browser'])

    def test_default_scope_previews_every_pdf(self):
        self.env['ir.config_parameter'].search(
            [('key', '=', PREVIEW_SCOPE_PARAM)]).unlink()
        self.report.invalidate_recordset(['al_preview_in_browser'])
        self.assertEqual(self.report.al_preview_mode, 'default')
        self.assertTrue(self.report.al_preview_in_browser)

    def test_scope_selected_only_marked_reports(self):
        self._scope('selected')
        self.assertFalse(self.report.al_preview_in_browser)
        self.report.al_preview_mode = 'preview'
        self.assertTrue(self.report.al_preview_in_browser)

    def test_scope_all_except_download(self):
        self._scope('all')
        self.assertTrue(self.report.al_preview_in_browser)
        self.report.al_preview_mode = 'download'
        self.assertFalse(self.report.al_preview_in_browser)

    def test_only_pdf_reports(self):
        self._scope('all')
        self.report.write({'report_type': 'qweb-html', 'al_preview_mode': 'preview'})
        self.assertFalse(self.report.al_preview_in_browser)

    def test_settings_write_the_parameter(self):
        self.env['res.config.settings'].create(
            {'al_report_preview_scope': 'selected'}).execute()
        self.assertEqual(
            self.env['ir.config_parameter'].get_param(PREVIEW_SCOPE_PARAM), 'selected')

    def test_report_action_carries_the_flag(self):
        self._scope('selected')
        action = self.report.report_action(self.module.ids, config=False)
        self.assertIs(action['al_preview_in_browser'], False)
        self.report.al_preview_mode = 'preview'
        action = self.report.report_action(self.module.ids, config=False)
        self.assertIs(action['al_preview_in_browser'], True)

    def test_layout_configurator_keeps_the_flag(self):
        """Sin diseño de documento, la acción del reporte viaja en el asistente."""
        self._scope('all')
        self.env.company.external_report_layout_id = False
        action = self.report.with_user(self.env.ref('base.user_admin')).report_action(
            self.module.ids)
        nested = action['context']['report_action']
        self.assertIs(nested['al_preview_in_browser'], True)

    def test_loaded_action_carries_the_flag(self):
        """El menú Imprimir carga la acción por id: la marca debe ser legible."""
        self._scope('all')
        self.assertIn('al_preview_in_browser', self.report._get_readable_fields())
        action = self.report._get_action_dict()
        self.assertIs(action['al_preview_in_browser'], True)


@tagged('post_install', '-at_install')
class TestReportPreviewRoute(HttpCase):
    """Cabeceras de la vista previa y de la descarga nativa.

    En modo test el motor PDF devuelve HTML; basta para revisar cabeceras.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = cls.env['ir.module.module'].search([('name', '=', 'base')])
        # La ruta es de solo lectura y este reporte crea definiciones de
        # propiedades en su primer uso: se calienta aquí.
        cls.env['ir.actions.report']._render_qweb_html(REPORT, cls.module.ids)

    def _dispositions(self, response):
        return response.raw.headers.getlist('Content-Disposition')

    def test_preview_is_inline_with_filename(self):
        self.authenticate('admin', 'admin')
        response = self.url_open(
            f'/report/pdf/{REPORT}/{self.module.id}',
            params={'al_preview': '1', 'context': json.dumps({'lang': 'en_US'})})
        self.assertEqual(response.status_code, 200)
        dispositions = self._dispositions(response)
        self.assertEqual(len(dispositions), 1)
        self.assertTrue(dispositions[0].startswith('inline'))
        self.assertIn('.pdf', dispositions[0])

    def test_native_route_untouched(self):
        self.authenticate('admin', 'admin')
        response = self.url_open(f'/report/pdf/{REPORT}/{self.module.id}')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._dispositions(response))

    def test_download_keeps_a_single_attachment_header(self):
        self.authenticate('admin', 'admin')
        data = json.dumps([f'/report/pdf/{REPORT}/{self.module.id}', 'qweb-pdf'])
        response = self.url_open('/report/download', params={'data': data, 'context': '{}'})
        self.assertEqual(response.status_code, 200)
        dispositions = self._dispositions(response)
        self.assertEqual(len(dispositions), 1)
        self.assertTrue(dispositions[0].startswith('attachment'))

    def test_preview_requires_login(self):
        response = self.url_open(
            f'/report/pdf/{REPORT}/{self.module.id}', params={'al_preview': '1'},
            allow_redirects=False)
        self.assertNotEqual(response.status_code, 200)
