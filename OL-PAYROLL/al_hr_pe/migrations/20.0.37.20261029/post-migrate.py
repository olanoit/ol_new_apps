# -*- coding: utf-8 -*-
"""Odoo 20:

- el tipo de documento del trabajador y del derechohabiente pasa de
  ``l10n_latam.identification.type`` (retirado con l10n_latam_base) al
  catálogo ``l10n_pe.hr.document.type``: la columna anterior se traduce por
  el xmlid del tipo de origen y luego se elimina;
- ``res.bank`` desaparece: la entidad SUNAT (T36) del banco pasa a cada
  cuenta bancaria, si la base aún conserva el enlace cuenta → banco.
"""
import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)

OLD_COLUMN = 'l10n_latam_identification_type_id'
# xmlid del tipo latam en 19 → xmlid del tipo en este módulo
MAPPING = {
    ('l10n_pe', 'it_DNI'): 'l10n_pe_hr_document_type_dni',
    ('l10n_latam_base', 'it_fid'): 'l10n_pe_hr_document_type_ce',
    ('l10n_pe', 'it_RUC'): 'l10n_pe_hr_document_type_ruc',
    ('l10n_latam_base', 'it_pass'): 'l10n_pe_hr_document_type_passport',
    ('l10n_pe', 'it_PTP'): 'l10n_pe_hr_document_type_ptp',
}


def migrate(cr, version):
    for table in ('hr_employee', 'l10n_pe_hr_dependent'):
        if not sql.column_exists(cr, table, OLD_COLUMN):
            continue
        for (module, name), new_xmlid in MAPPING.items():
            cr.execute(f"""
                UPDATE {table} t
                   SET l10n_pe_document_type_id = new.res_id
                  FROM ir_model_data old, ir_model_data new
                 WHERE old.module = %s AND old.name = %s
                   AND old.model = 'l10n_latam.identification.type'
                   AND t.{OLD_COLUMN} = old.res_id
                   AND new.module = 'al_hr_pe' AND new.name = %s
                   AND t.l10n_pe_document_type_id IS NULL
            """, [module, name, new_xmlid])
            _logger.info('%s: %s.%s → %s (%s filas)', table, module, name, new_xmlid, cr.rowcount)
        cr.execute(f'ALTER TABLE {table} DROP COLUMN {OLD_COLUMN} CASCADE')

    if sql.column_exists(cr, 'res_partner_bank', 'bank_id') \
            and sql.column_exists(cr, 'res_bank', 'l10n_pe_financial_entity_id'):
        cr.execute("""
            UPDATE res_partner_bank a
               SET l10n_pe_financial_entity_id = b.l10n_pe_financial_entity_id
              FROM res_bank b
             WHERE a.bank_id = b.id AND a.l10n_pe_financial_entity_id IS NULL
        """)
        _logger.info('res_partner_bank: entidad T36 desde el banco (%s filas)', cr.rowcount)
