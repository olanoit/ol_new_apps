# -*- coding: utf-8 -*-
"""Utilidades de cálculo compartidas por la localización de planillas."""
from decimal import ROUND_HALF_UP, Decimal


def custom_round(value, digits=2):
    """Redondeo HALF_UP (criterio SUNAT).

    Python/Odoo redondean por defecto al par (banker's rounding);
    SUNAT exige el redondeo aritmético clásico: 0.005 → 0.01. Portado
    de report_tools v18 — no sustituir por float_round.
    """
    quant = Decimal('1.' + '0' * digits)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def round_half_up(value, ndigits=None):
    """``round`` con el criterio SUNAT, para las fórmulas de las reglas.

    Misma firma que el ``round`` de Python (sin ``ndigits`` devuelve un
    entero), pero 2.675 → 2.68 en vez de 2.67.
    """
    if ndigits is None:
        return int(custom_round(value, 0))
    return custom_round(value, ndigits)
