# -*- coding: utf-8 -*-
"""Excel de revisión de los libros PLE que genera la localización oficial.

La localización de Enterprise entrega solo el TXT de Caja y Bancos (1.1,
1.2), del Libro 3, del Diario y el Mayor (5.1, 5.3, 6.1) y del inventario
permanente (12.1, 13.1). Aquí se añade, junto a cada botón TXT, uno XLSX con
las mismas líneas: se llama a la exportación oficial y su TXT se vuelca en la
hoja con el formato del módulo v18 y los encabezados del Anexo 2 de SUNAT.
Así el Excel nunca puede decir algo distinto del archivo que se presenta.
"""
import base64
import io
import re
import zipfile

from werkzeug.urls import url_encode

from odoo import _, api, fields, models

# Nombre de cada TXT del Libro 3 dentro del ZIP: LE + RUC + AAAAMMDD + código.
LIB_FILENAME = re.compile(r'^LE\d{11}\d{8}(\d{6})')


def _period(options):
    date_from = fields.Date.to_date(options['date']['date_from'])
    return date_from.year, '%02d' % date_from.month


class L10nPeGeneralLedgerXlsx(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if self.env.company.account_fiscal_country_id.code != 'PE':
            return
        for name, sequence, method in (
                (_('XLSX 5.1'), 31, 'l10n_pe_export_ple_51_to_xlsx'),
                (_('XLSX 5.3'), 36, 'l10n_pe_export_ple_53_to_xlsx'),
                (_('XLSX 6.1'), 41, 'l10n_pe_export_ple_61_to_xlsx'),
                (_('XLSX Inventario y Balance'), 46, 'l10n_pe_export_lib_to_xlsx')):
            options['buttons'].append({
                'name': name,
                'sequence': sequence,
                'action': 'export_file',
                'action_param': method,
                'file_export_type': _('XLSX'),
            })

    @api.model
    def _l10n_pe_txt_result_to_xlsx(self, result, book_code, options):
        year, month = _period(options)
        Mixin = self.env['l10n_pe.ple.mixin']
        return {
            'file_name': result['file_name'],
            'file_content': Mixin._ple_xlsx(
                book_code, Mixin._ple_txt_rows(result['file_content']),
                self.env.company, year, month),
            'file_type': 'xlsx',
        }

    @api.model
    def l10n_pe_export_ple_51_to_xlsx(self, options):
        return self._l10n_pe_txt_result_to_xlsx(
            self.l10n_pe_export_ple_51_to_txt(options), '050100', options)

    @api.model
    def l10n_pe_export_ple_53_to_xlsx(self, options):
        return self._l10n_pe_txt_result_to_xlsx(
            self.l10n_pe_export_ple_53_to_txt(options), '050300', options)

    @api.model
    def l10n_pe_export_ple_61_to_xlsx(self, options):
        return self._l10n_pe_txt_result_to_xlsx(
            self.l10n_pe_export_ple_61_to_txt(options), '060100', options)

    @api.model
    def l10n_pe_export_lib_to_xlsx(self, options):
        """El Libro 3 sale en un ZIP con un TXT por formato: aquí, un solo
        XLSX con una hoja por formato, en el mismo orden."""
        result = self.l10n_pe_export_lib_to_txt(options)
        Mixin = self.env['l10n_pe.ple.mixin']
        books = []
        with zipfile.ZipFile(io.BytesIO(result['file_content'])) as archive:
            for name in archive.namelist():
                match = LIB_FILENAME.match(name)
                if match:
                    books.append((match.group(1), Mixin._ple_txt_rows(archive.read(name))))
        date_to = fields.Date.to_date(options['date']['date_to'])
        return {
            'file_name': result['file_name'],
            'file_content': Mixin._ple_xlsx_books(
                books, self.env.company, date_to.year, '%02d' % date_to.month),
            'file_type': 'xlsx',
        }


class L10nPeCashFlowXlsx(models.AbstractModel):
    _inherit = 'account.cash.flow.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if self.env.company.account_fiscal_country_id.code != 'PE':
            return
        for name, sequence, method in (
                (_('XLSX PLE 1.1 (Efectivo)'), 21, 'l10n_pe_export_ple_11_to_xlsx'),
                (_('XLSX PLE 1.2 (Banco)'), 26, 'l10n_pe_export_ple_12_to_xlsx')):
            options.setdefault('buttons', []).append({
                'name': name,
                'sequence': sequence,
                'action': 'export_file',
                'action_param': method,
                'file_export_type': _('XLSX'),
            })

    def l10n_pe_export_ple_11_to_xlsx(self, options):
        return self.env['account.general.ledger.report.handler']._l10n_pe_txt_result_to_xlsx(
            self.l10n_pe_export_ple_11_to_txt(options), '010100', options)

    def l10n_pe_export_ple_12_to_xlsx(self, options):
        return self.env['account.general.ledger.report.handler']._l10n_pe_txt_result_to_xlsx(
            self.l10n_pe_export_ple_12_to_txt(options), '010200', options)


class L10nPeStockPleWizardXlsx(models.TransientModel):
    _inherit = 'l10n_pe.stock.ple.wizard'

    def get_ple_xlsx_12_1(self):
        return self._get_ple_xlsx('1201', '120100')

    def get_ple_xlsx_13_1(self):
        return self._get_ple_xlsx('1301', '130100')

    def _get_ple_xlsx(self, report_number, book_code):
        self.ensure_one()
        Mixin = self.env['l10n_pe.ple.mixin']
        content = self._get_ple_report_content(report_number)
        has_data = '1' if content else '0'
        xlsx = Mixin._ple_xlsx(
            book_code, Mixin._ple_txt_rows(content), self.env.company,
            self.date_from.year, '%02d' % self.date_from.month)
        self.write({
            'report_data': base64.b64encode(xlsx),
            'report_filename': 'LE%s%s%02d00%s00001%s11.xlsx' % (
                self.env.company.vat, self.date_from.year, self.date_from.month,
                report_number, has_data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?' + url_encode({
                'model': self._name,
                'id': self.id,
                'filename_field': 'report_filename',
                'field': 'report_data',
                'download': 'true',
            }),
            'target': 'new',
        }
