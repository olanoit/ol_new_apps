# -*- coding: utf-8 -*-
"""Migración 19.0.4.0.0: reemplazo del campo mágico `active` por `enabled`.

El campo `active` archivaba la conexión y la ocultaba de las vistas. Se
sustituye por `enabled` (booleano normal) para poder deshabilitar una conexión
sin que desaparezca de la lista. Se copian los valores previos de `active`.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # La columna huérfana `active` sobrevive al retiro del campo; si existe,
    # copiamos su valor a `enabled`.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l10n_pe_api_connection' AND column_name = 'active'
    """)
    if cr.fetchone():
        cr.execute("UPDATE l10n_pe_api_connection SET enabled = active")
        _logger.info('l10n_pe_vat_sunat: valores de active copiados a enabled.')
