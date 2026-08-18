# -*- coding: utf-8 -*-
"""Sustituye el motor de consulta de los informes SIRE de ``l10n_pe_reports``.

El original construye la consulta a mano e inyecta el ``WHERE`` del ORM sobre un
``FROM`` escrito literalmente, de modo que cualquier condición del dominio que
el ORM resuelva con JOIN produce SQL inválido y los tres informes fallan con
``UndefinedTable``. Ver ``docs/tecport/BUG_EE_RCE_SQL.md``.

Aquí se devuelve exactamente la misma estructura —``[(clave, columnas), …]``
cuando hay agrupación, o un único diccionario cuando no la hay— pero obtenida
con el ORM, de modo que los informes también funcionan en pantalla.
"""
from odoo import api, models

# Número de informe → tipo de libro.
PLE_REPORT_BOOKS = {
    '08040002': 'purchase',        # RCE 8.4, compras domiciliadas
    '08050000': 'purchase_nd',     # RCE 8.5, no domiciliados
    '14040002': 'sale',            # RVIE 14.4, ventas
}

# Claves del diccionario de columnas, con su valor cuando no hay movimientos.
PLE_EMPTY_COLUMNS = (
    'document_type', 'date', 'customer_vat', 'customer', 'amount_total',
    'invoice_date', 'base_exp', 'base_igv', 'tax_igv', 'base_exo', 'base_ina',
    'tax_isc', 'base_ivap', 'tax_ivap', 'vat_icbper', 'vat_igv_g_ng',
    'vat_igv_ng', 'base_free', 'vat_other', 'base_withholdings',
)


class L10nPePleReportHandler(models.AbstractModel):
    _inherit = 'l10n_pe.tax.ple.report.handler'

    # ------------------------------------------------------------------
    # Motor de datos
    # ------------------------------------------------------------------
    def _get_ple_report_data(self, options, current_groupby):
        book = PLE_REPORT_BOOKS.get(self._get_report_number())
        if not book:
            # Informe no cubierto por esta sustitución: se deja el original.
            return super()._get_ple_report_data(options, current_groupby)

        moves = self._l10n_pe_ple_moves(options, book)
        group_ids = self.env['l10n_pe.rce.extractor']._rce_tax_group_ids(
            self.env.company)
        rows = [(move.id, self._l10n_pe_ple_columns(move, group_ids))
                for move in moves]

        if not current_groupby:
            return rows[0][1] if rows else dict.fromkeys(PLE_EMPTY_COLUMNS)
        return rows

    @api.model
    def _l10n_pe_ple_moves(self, options, book):
        """Comprobantes del periodo según el libro de que se trate."""
        extractor = self.env['l10n_pe.rce.extractor']
        company = self.env.company
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        if book == 'sale':
            return extractor._rvie_moves(company, date_from, date_to)
        return extractor._rce_moves(company, date_from, date_to,
                                    non_domiciled=book == 'purchase_nd')

    # ------------------------------------------------------------------
    # Columnas
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_ple_columns(self, move, group_ids):
        """Diccionario de columnas con la forma que espera ``l10n_pe_reports``."""
        extractor = self.env['l10n_pe.rce.extractor']
        amounts = extractor._rce_amounts(move, group_ids)
        partner = move.partner_id.commercial_partner_id
        identification = partner.l10n_latam_identification_type_id
        mod_date, mod_type, _serie, _folio = \
            extractor._rce_modified_document(move)
        origin = move.reversed_entry_id or move.debit_origin_id
        dua = move.l10n_pe_dua_invoice_id if 'l10n_pe_dua_invoice_id' in move._fields \
            else move.browse()

        return {
            'move_name': move.name,
            'invoice_date': move.invoice_date,
            'date': move.date,
            'date_due': move.invoice_date_due,
            'document_type': move.l10n_latam_document_type_id.code or '',
            'partner_lit': identification.name,
            'partner_lit_code': identification.l10n_pe_vat_code or '',
            'id_number': partner.vat or '',
            'customer_vat': partner.vat or '',
            'customer': partner.name or '',
            'amount_total': extractor._rce_total(move),
            'currency': move.currency_id.name,
            'rate': extractor._rce_exchange_rate(move),
            'base_igv': amounts.get('base_igv', 0.0),
            'tax_igv': amounts.get('tax_igv', 0.0),
            'base_igv_g_ng': amounts.get('base_igv_g_ng', 0.0),
            'vat_igv_g_ng': amounts.get('tax_igv_g_ng', 0.0),
            'base_igv_ng': amounts.get('base_igv_ng', 0.0),
            'vat_igv_ng': amounts.get('tax_igv_ng', 0.0),
            'base_exo': amounts.get('base_exo', 0.0),
            'base_ina': amounts.get('base_ina', 0.0),
            'base_ivap': amounts.get('base_ivap', 0.0),
            'base_exp': amounts.get('base_exp', 0.0),
            'tax_ivap': amounts.get('tax_ivap', 0.0),
            'vat_icbper': amounts.get('tax_icbper', 0.0),
            'tax_isc': amounts.get('tax_isc', 0.0),
            'base_free': amounts.get('base_gra', 0.0),
            'vat_other': amounts.get('tax_other', 0.0),
            'base_withholdings': amounts.get('tax_ret', 0.0),
            'detraction_date': self._l10n_pe_ple_field(move, 'l10n_pe_detraction_date'),
            'detraction_number': self._l10n_pe_ple_field(move, 'l10n_pe_detraction_number'),
            'emission_date_related': mod_date,
            'document_type_related': mod_type,
            'related_document': origin.name if origin else '',
            'status': move.state,
            'edi_state': move.edi_state if 'edi_state' in move._fields else False,
            'invoice_dua_name': dua.name if dua else '',
            'invoice_dua_document_type': (
                dua.l10n_latam_document_type_id.code or '') if dua else '',
            'invoice_dua_date': dua.invoice_date if dua else False,
            'partner_country_code': partner.country_id.l10n_pe_code or '',
            'partner_street': partner.street or '',
            'partner_country_agreement_code':
                partner.country_id.l10n_pe_agreement_code or '',
            'usage_type_code': self._l10n_pe_ple_usage_code(move),
            'service_modality': self._l10n_pe_ple_field(move, 'l10n_pe_service_modality'),
            'company_vat': (move.company_id.vat or '').strip(),
            'company_name': move.company_id.name,
        }

    @api.model
    def _l10n_pe_ple_field(self, move, name):
        """Lee un campo que puede no existir si falta el módulo que lo aporta."""
        return move[name] if name in move._fields else False

    @api.model
    def _l10n_pe_ple_usage_code(self, move):
        usage = self._l10n_pe_ple_field(move, 'l10n_pe_usage_type_id')
        return usage.code if usage else ''
