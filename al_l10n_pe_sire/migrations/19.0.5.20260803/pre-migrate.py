# -*- coding: utf-8 -*-
"""Unicidad del periodo SIRE en base de datos.

Esta versión añade ``unique (company_id, year, month)`` a los periodos RCE y
RVIE. Hasta ahora solo lo garantizaba una restricción Python, que no impide
dos altas simultáneas. Si hubiera duplicados, la restricción no podría
crearse: se avisa en el log con los periodos afectados para depurarlos a
mano (no se borra nada, pueden haberse enviado a SUNAT).
"""
import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)

TABLES = ('l10n_pe_sire_rce', 'l10n_pe_sire_rvie')


def migrate(cr, version):
    for table in TABLES:
        cr.execute(SQL(
            """
            SELECT company_id, year, month, array_agg(id ORDER BY id)
              FROM %s
          GROUP BY company_id, year, month
            HAVING count(*) > 1
            """,
            SQL.identifier(table),
        ))
        for company_id, year, month, ids in cr.fetchall():
            _logger.warning(
                'al_l10n_pe_sire: periodo %s-%s duplicado en %s (compañía %s, '
                'registros %s); la restricción de unicidad no se creará hasta '
                'eliminar los sobrantes.', year, month, table, company_id, ids)
