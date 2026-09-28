# -*- coding: utf-8 -*-
"""Quita el «Domingo de Resurrección» de los feriados cargados.

No es feriado legal en el Perú (son 16 al año: D.Leg. 713 y leyes
posteriores). Los datos van con ``noupdate``, así que retirar el registro
del XML no lo borra de las bases ya instaladas. Se borra por xmlid y solo
si sigue siendo ese domingo: un registro que el usuario haya reutilizado
para otra fecha no se toca. Al borrarlo se van también, en cascada, los
descansos que ya se hubieran creado en los calendarios.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

EASTER_XMLIDS = (
    'h_2026_04_05', 'h_2027_03_28', 'h_2028_04_16', 'h_2029_04_01',
    'h_2030_04_21', 'h_2031_04_13', 'h_2032_03_28', 'h_2033_04_17',
    'h_2034_04_09', 'h_2035_03_25',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    holidays = env['pe.public.holiday']
    for xmlid in EASTER_XMLIDS:
        record = env.ref('al_hr_pe_public_holidays.%s' % xmlid,
                         raise_if_not_found=False)
        # Domingo de Pascua: weekday() == 6.
        if record and record.date and record.date.weekday() == 6:
            holidays |= record
    if holidays:
        count = len(holidays)
        holidays.unlink()
        _logger.info('al_hr_pe_public_holidays: %s domingos de Resurrección '
                     'retirados de los feriados.', count)
