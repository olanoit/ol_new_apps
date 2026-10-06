# -*- coding: utf-8 -*-
"""Combinación ponderada de distribuciones analíticas.

Una distribución de Odoo es ``{"3": 60.0, "7,11": 40.0}``: la clave son ids
de cuenta analítica (varias separadas por coma cuando la línea cruza planes)
y el valor el porcentaje.
"""
from collections import defaultdict


def merge_analytic_distributions(items, precision=2):
    """Combina distribuciones analíticas ponderándolas por importe.

    `items` es un iterable de ``(distribución, peso)``. El resultado es la
    **combinación convexa** de las distribuciones que traen algo: el
    denominador es el peso de las que sí tienen analítica, no el total. Así,
    si cada distribución de origen reparte el 100 % de un plan, la combinada
    también lo reparte, y no rompe los planes marcados como obligatorios
    (``_validate_distribution`` exige exactamente 100 %).

    Los pesos son importes contables, así que se usa su valor absoluto: un
    abono y un cargo del mismo centro de costo pesan lo mismo.
    """
    weighted = [(dist, abs(weight)) for dist, weight in items if dist and weight]
    if not weighted:
        # Sin importes que ponderar (p. ej. líneas de saldo cero): reparto
        # uniforme entre las distribuciones disponibles.
        weighted = [(dist, 1.0) for dist, _weight in items if dist]
    total = sum(weight for _dist, weight in weighted)
    if not total:
        return False

    merged = defaultdict(float)
    for dist, weight in weighted:
        for key, percentage in dist.items():
            merged[key] += percentage * weight / total
    if not merged:
        return False

    rounded = {key: round(value, precision)
               for key, value in merged.items() if round(value, precision)}
    if not rounded:
        return False
    # El redondeo puede dejar 99,99 donde debía haber 100 y hacer fallar un
    # plan obligatorio: el residuo se carga a la clave de mayor peso.
    residue = round(sum(merged.values()) - sum(rounded.values()), precision)
    if residue:
        largest = max(rounded, key=lambda key: abs(rounded[key]))
        rounded[largest] = round(rounded[largest] + residue, precision)
    return rounded
