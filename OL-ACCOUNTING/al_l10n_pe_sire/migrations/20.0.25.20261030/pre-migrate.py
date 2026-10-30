# -*- coding: utf-8 -*-
"""La modalidad del servicio, el tipo de renta y el código SUNAT de país pasan
a los campos nativos de l10n_pe_reports: se copian donde estos están vacíos."""


def _has_column(cr, table, column):
    cr.execute("""SELECT 1 FROM information_schema.columns
                   WHERE table_name = %s AND column_name = %s""", [table, column])
    return bool(cr.fetchone())


def migrate(cr, version):
    if _has_column(cr, 'account_move', 'l10n_pe_sire_nd_service_modality') \
            and _has_column(cr, 'account_move', 'l10n_pe_service_modality'):
        cr.execute("""
            UPDATE account_move
               SET l10n_pe_service_modality = l10n_pe_sire_nd_service_modality
             WHERE l10n_pe_sire_nd_service_modality IS NOT NULL
               AND l10n_pe_service_modality IS NULL
        """)
    if _has_column(cr, 'account_move', 'l10n_pe_sire_nd_income_type') \
            and _has_column(cr, 'account_move', 'l10n_pe_usage_type_id'):
        cr.execute("""
            UPDATE account_move move
               SET l10n_pe_usage_type_id = usage.id
              FROM l10n_pe_ple_usage usage
             WHERE usage.code = move.l10n_pe_sire_nd_income_type
               AND move.l10n_pe_usage_type_id IS NULL
        """)
    if _has_column(cr, 'res_country', 'l10n_pe_sire_country_code') \
            and _has_column(cr, 'res_country', 'l10n_pe_code'):
        cr.execute("""
            UPDATE res_country
               SET l10n_pe_code = l10n_pe_sire_country_code
             WHERE COALESCE(l10n_pe_sire_country_code, '') != ''
               AND COALESCE(l10n_pe_code, '') = ''
        """)
