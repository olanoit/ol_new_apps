# -*- coding: utf-8 -*-
"""Avisa de retenciones sufridas duplicadas antes de la restricción única.

Esta versión exige que el comprobante (compañía, cliente, número) sea
único: registrarlo dos veces duplicaba el crédito del IGV. Si la base ya
tiene duplicados, Odoo no puede crear la restricción; no se borran ni se
renombran porque son números legales: se listan para que contabilidad
anule los sobrantes y vuelva a actualizar el módulo.
"""
import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(SQL("""
        SELECT company_id, partner_id, name, array_agg(id ORDER BY id)
          FROM l10n_pe_retention_received
      GROUP BY company_id, partner_id, name
        HAVING count(*) > 1
    """))
    for company_id, partner_id, name, ids in cr.fetchall():
        _logger.warning(
            'al_l10n_pe_retention: la retención sufrida %s (compañía %s, '
            'cliente %s) está registrada %s veces (ids %s). Anule las '
            'sobrantes: mientras existan no se crea la restricción única.',
            name, company_id, partner_id, len(ids), ids)
