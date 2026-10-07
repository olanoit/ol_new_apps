# -*- coding: utf-8 -*-
"""Nombres legibles de los registros de planilla.

Las líneas (CTS, gratificación, vacaciones, provisiones…) no tienen campo
``name``: sin esto Odoo las muestra como «hr.cts.line,5» en las migas de
pan, el chatter, los avisos y los campos relacionales.
"""
from odoo.tools import format_date

SEPARATOR = ' · '


def pe_join(*parts):
    """Une las partes no vacías con « · »."""
    return SEPARATOR.join(str(part) for part in parts if part)


def pe_date(env, value):
    return format_date(env, value) if value else ''


def pe_range(env, date_from, date_to):
    """«01/07/2026 – 15/07/2026» (o solo la fecha que exista)."""
    if date_from and date_to:
        return '%s – %s' % (pe_date(env, date_from), pe_date(env, date_to))
    return pe_date(env, date_from or date_to)
