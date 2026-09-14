# -*- coding: utf-8 -*-
"""Libro 7 en pantalla — Registro de Activos Fijos (Formato 7.1).

Hasta ahora el libro solo existía como TXT dentro del asistente «Exportar PLE»,
mientras que el resto de libros (5.x, 1.x, 8.x, 14.x) tienen su informe
contable con los botones TXT/XLSX. Este informe cierra ese hueco con la misma
mecánica: ``account.report`` + handler, columnas del formato físico 7.1
(RS 234-2006/SUNAT) y exportación del archivo legal desde la propia pantalla.

Los datos salen de ``l10n_pe.ple.asset.book``, igual que el asistente, así que
pantalla, TXT y XLSX no pueden descuadrar.
"""
from odoo import _, api, fields, models

from .ple_asset_book import ASSET_71_AMOUNTS

# Botones de exportación: (código de libro, etiqueta, formato, secuencia).
ASSET_REPORT_EXPORTS = (
    ('070100', 'TXT 7.1', 'txt', 30),
    ('070100', 'XLSX 7.1', 'xlsx', 31),
    ('070300', 'TXT 7.3', 'txt', 32),
    ('070400', 'TXT 7.4', 'txt', 33),
)


class L10nPePleAssetReportHandler(models.AbstractModel):
    _name = 'l10n_pe.ple.asset.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'PLE 7.1 - Registro de Activos Fijos'

    # ------------------------------------------------------------------
    # Opciones
    # ------------------------------------------------------------------
    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(
            report, options, previous_options=previous_options)
        options['custom_columns_subheaders'] = [
            {'name': _('Identificación'), 'colspan': 4},
            {'name': _('Valor del activo'), 'colspan': 8},
            {'name': _('Uso y método'), 'colspan': 5},
            {'name': _('Depreciación'), 'colspan': 7},
        ]
        buttons = options.setdefault('buttons', [])
        for book_code, label, file_type, sequence in ASSET_REPORT_EXPORTS:
            buttons.append({
                'name': label,
                'sequence': sequence,
                'action': 'export_file',
                'action_param': 'l10n_pe_asset_export_%s_%s' % (
                    book_code[:4], file_type),
                'file_export_type': file_type.upper(),
            })

    def _caret_options_initializer(self):
        return {
            'l10n_pe_ple_asset': [
                {'name': _('Abrir activo'),
                 'action': 'caret_option_open_record_form'},
            ],
        }

    @api.model
    def _l10n_pe_asset_year(self, options):
        """Libro anual: el ejercicio es el de la fecha final del filtro."""
        return fields.Date.to_date(options['date']['date_to']).year

    # ------------------------------------------------------------------
    # Líneas
    # ------------------------------------------------------------------
    def _dynamic_lines_generator(self, report, options,
                                 all_column_groups_expression_totals,
                                 warnings=None):
        rows = self.env['l10n_pe.ple.asset.book']._asset_71_values(
            self.env.company, self._l10n_pe_asset_year(options))
        if not rows:
            return []

        by_account = {}
        for asset, values in rows:
            by_account.setdefault(asset.account_asset_id, []).append(
                (asset, values))

        currency = self.env.company.currency_id
        grand_total = dict.fromkeys(ASSET_71_AMOUNTS, 0.0)
        lines = []
        for account in sorted(by_account, key=lambda a: a.code or ''):
            group = by_account[account]
            group_total = dict.fromkeys(ASSET_71_AMOUNTS, 0.0)
            for _asset, values in group:
                for key in ASSET_71_AMOUNTS:
                    group_total[key] += values[key]
                    grand_total[key] += values[key]

            account_line_id = report._get_generic_line_id(
                'account.account', account.id)
            lines.append({
                'id': account_line_id,
                'name': '%s %s' % (account.code or '', account.name or ''),
                'level': 1,
                'unfoldable': False,
                'columns': self._l10n_pe_asset_columns(
                    report, options, group_total, currency),
            })
            for asset, values in group:
                name = '%s · %s' % (values['code'], values['name'])
                lines.append({
                    'id': report._get_generic_line_id(
                        'account.asset', asset.id,
                        parent_line_id=account_line_id),
                    'name': name,
                    'title_hover': name,
                    'level': 2,
                    'unfoldable': False,
                    'caret_options': 'l10n_pe_ple_asset',
                    'columns': self._l10n_pe_asset_columns(
                        report, options, values, currency),
                })

        lines.append({
            'id': report._get_generic_line_id(None, None, markup='total'),
            'name': _('Total'),
            'level': 1,
            'unfoldable': False,
            'columns': self._l10n_pe_asset_columns(
                report, options, grand_total, currency),
        })
        return [(0, line) for line in lines]

    @api.model
    def _l10n_pe_asset_columns(self, report, options, values, currency):
        """Una celda por columna; los totales solo rellenan los importes."""
        columns = []
        for column in options['columns']:
            value = values.get(column['expression_label'])
            columns.append(report._build_column_dict(
                value, column if value is not None else None,
                options=options, currency=currency))
        return columns

    # ------------------------------------------------------------------
    # Exportación (botones)
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_asset_export(self, options, book_code, file_type):
        book = self.env['l10n_pe.ple.asset.book']
        company = self.env.company
        year = self._l10n_pe_asset_year(options)
        lines = book._asset_lines(book_code, company, year)
        file_name = book._ple_filename(
            company, book_code, year, has_data=bool(lines))
        if file_type == 'xlsx':
            return {
                'file_name': file_name.rsplit('.', 1)[0] + '.xlsx',
                'file_content': book._ple_xlsx(book_code, lines, company, year),
                'file_type': 'xlsx',
            }
        return {
            'file_name': file_name,
            'file_content': book._ple_content(book_code, lines),
            'file_type': 'txt',
        }

    def l10n_pe_asset_export_0701_txt(self, options):
        return self._l10n_pe_asset_export(options, '070100', 'txt')

    def l10n_pe_asset_export_0701_xlsx(self, options):
        return self._l10n_pe_asset_export(options, '070100', 'xlsx')

    def l10n_pe_asset_export_0703_txt(self, options):
        return self._l10n_pe_asset_export(options, '070300', 'txt')

    def l10n_pe_asset_export_0704_txt(self, options):
        return self._l10n_pe_asset_export(options, '070400', 'txt')
