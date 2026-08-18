# -*- coding: utf-8 -*-
"""Exportación a Excel de los registros del SIRE.

El TXT es el archivo legal, pero es ilegible a simple vista: 41 columnas sin
cabecera separadas por pipes. Antes de presentarlo hay que revisarlo, y para
eso se añade un botón «XLSX» junto al de TXT en los tres informes, con las
mismas líneas y una cabecera por nombre de campo.
"""
from odoo import _, api, models

# Informe → (código de libro, etiqueta del botón)
SIRE_XLSX_BOOKS = {
    '08040002': ('080400', 'XLSX RCE 8.4'),
    '08050000': ('080500', 'XLSX RCE 8.5'),
    '14040002': ('140400', 'XLSX RVIE 14.4'),
}


class L10nPeSireXlsxExport(models.AbstractModel):
    _inherit = 'l10n_pe.tax.ple.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options,
                                            previous_options=previous_options)
        book = SIRE_XLSX_BOOKS.get(self._get_report_number())
        if not book:
            return
        options.setdefault('buttons', []).append({
            'name': _(book[1]),
            'sequence': 30,
            'action': 'export_file',
            'action_param': 'l10n_pe_sire_export_to_xlsx',
            'file_export_type': _('XLSX'),
        })

    @api.model
    def l10n_pe_sire_export_to_xlsx(self, options):
        """Mismas líneas que el TXT, en una hoja de cálculo con cabeceras."""
        book_code, _label = SIRE_XLSX_BOOKS[self._get_report_number()]
        result = self.export_to_txt(options)
        content = result['file_content'].decode() if result['file_content'] else ''
        rows = [line.rstrip('|').split('|')
                for line in content.split('\r\n') if line.strip()]

        date_from = options['date']['date_from']
        year, month = str(date_from)[:4], str(date_from)[5:7]
        xlsx = self.env['l10n_pe.ple.mixin']._ple_xlsx(
            book_code, rows, self.env.company, year, month)
        return {
            'file_name': result['file_name'],
            'file_content': xlsx,
            'file_type': 'xlsx',
        }
