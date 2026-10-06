# -*- coding: utf-8 -*-
"""Mínimo del Anexo 1 (½ UIT) con la UIT 2026 de S/ 5,500.

El catálogo es ``noupdate`` y traía 2,675 (½ UIT 2025). Solo se corrige
si sigue con ese valor.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE l10n_pe_detraction_type
           SET min_amount = 2750, write_date = now() AT TIME ZONE 'UTC'
         WHERE code IN ('001', '003') AND min_amount = 2675
    """)
    if cr.rowcount:
        _logger.info('al_l10n_pe_detraction: mínimo del Anexo 1 = S/ 2,750 '
                     'en %s código(s).', cr.rowcount)
