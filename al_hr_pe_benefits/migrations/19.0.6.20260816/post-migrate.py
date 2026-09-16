# -*- coding: utf-8 -*-
"""Tramos de 5ta generados con la UIT 2026 errónea (5,350).

``generate_tramos`` guarda los límites ya multiplicados por la UIT, así que
al corregir la UIT 2026 a 5,500 (migración de ``al_hr_pe``) los tramos
generados antes quedaban en 26,750 / 107,000 / 187,250 / 240,750. Se
recalculan solo los parámetros cuyos cuatro límites son exactamente esos:
una tabla personalizada no se toca.
"""
import logging

_logger = logging.getLogger(__name__)

FACTORS = {1: 5, 2: 20, 3: 35, 4: 45}
OLD_UIT, NEW_UIT = 5350, 5500


def migrate(cr, version):
    cr.execute("SELECT amount FROM l10n_pe_hr_uit WHERE year = 2026")
    row = cr.fetchone()
    if not row or row[0] != NEW_UIT:
        return
    cr.execute("""
        SELECT main_parameter_id, array_agg(range ORDER BY range),
               array_agg("limit" ORDER BY range)
          FROM hr_rate_limit
         WHERE range IN %s
      GROUP BY main_parameter_id
    """, (tuple(FACTORS),))
    stale = [
        parameter_id for parameter_id, ranges, limits in cr.fetchall()
        if ranges == list(FACTORS)
        and limits == [FACTORS[r] * OLD_UIT for r in ranges]
    ]
    for range_, factor in FACTORS.items():
        cr.execute("""
            UPDATE hr_rate_limit SET "limit" = %s
             WHERE main_parameter_id = ANY(%s) AND range = %s
        """, (factor * NEW_UIT, stale, range_))
    if stale:
        _logger.info('al_hr_pe_benefits: tramos de 5ta recalculados con la '
                     'UIT 2026 en %s parámetro(s).', len(stale))
