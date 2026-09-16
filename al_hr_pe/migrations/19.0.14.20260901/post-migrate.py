# -*- coding: utf-8 -*-
"""UIT 2026: S/ 5,500 (D.S. N.° 301-2025-EF).

Los datos venían con el valor de 2025 (5,350) y son ``noupdate``, así que
actualizar el módulo no los corrige. Solo se cambia si sigue con el valor
erróneo: una UIT ya corregida a mano no se toca.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE l10n_pe_hr_uit
           SET amount = 5500, write_date = now() AT TIME ZONE 'UTC'
         WHERE year = 2026 AND amount = 5350
    """)
    if cr.rowcount:
        _logger.info('al_hr_pe: UIT 2026 corregida de 5350 a 5500.')
