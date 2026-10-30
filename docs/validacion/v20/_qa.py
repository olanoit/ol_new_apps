# -*- coding: utf-8 -*-
"""Utilidades comunes de la validación funcional en Odoo 20.

Se antepone a cada script de fase (ver run_qa.sh). Cada caso registra
OK / AVISO / FALLA / OMITIDO con el detalle y los registros creados;
al final _fin.py vuelca el resultado a resultados/<fase>.json y hace
commit (los registros quedan en la base para revisarlos en pantalla).
"""
import json
import os
import traceback

from odoo import Command, fields  # noqa: F401
from odoo.tools import float_compare

QA_PREFIX = 'QA20'
QA = {'fase': os.environ.get('QA_FASE', 'sin_fase'), 'casos': []}
OK, WARN, FAIL, SKIP = 'OK', 'AVISO', 'FALLA', 'OMITIDO'
_CUR = {}

company = env['res.company'].search([('partner_id.country_id.code', '=', 'PE')], limit=1) or env.company
env = env(context=dict(env.context, allowed_company_ids=[company.id], tracking_disable=True))


def caso(modulo, titulo, pasos=''):
    """Abre un caso de prueba de `modulo`."""
    global _CUR
    _CUR = dict(modulo=modulo, titulo=titulo, pasos=pasos, checks=[], registros=[], error=None)
    QA['casos'].append(_CUR)
    print('\n== [%s] %s' % (modulo, titulo))
    return _CUR


def registro(rec, nota=''):
    """Anota un registro creado (modelo, id, nombre) como evidencia."""
    for r in rec:
        _CUR['registros'].append({'modelo': r._name, 'id': r.id, 'nombre': r.display_name, 'nota': nota})
    return rec


def _log(level, titulo, detalle=''):
    _CUR['checks'].append({'estado': level, 'titulo': titulo, 'detalle': str(detalle)})
    print('  %-7s %s%s' % (level, titulo, ' — %s' % detalle if detalle else ''))


def check(cond, titulo, detalle=''):
    _log(OK if cond else FAIL, titulo, detalle)
    return bool(cond)


def igual(valor, esperado, titulo, decimales=2):
    if isinstance(esperado, (int, float)) and isinstance(valor, (int, float)):
        ok = float_compare(valor, esperado, precision_digits=decimales) == 0
    else:
        ok = valor == esperado
    _log(OK if ok else FAIL, titulo, 'esperado %r, obtenido %r' % (esperado, valor))
    return ok


def aviso(titulo, detalle=''):
    _log(WARN, titulo, detalle)


def omitido(titulo, detalle=''):
    _log(SKIP, titulo, detalle)


def ejecutar(fn):
    """Ejecuta un caso en un savepoint: si revienta, se registra FALLA y se sigue."""
    try:
        with env.cr.savepoint():
            fn()
    except Exception as exc:  # noqa: BLE001
        _CUR['error'] = '%s: %s' % (type(exc).__name__, exc)
        _log(FAIL, '%s lanzó una excepción' % fn.__name__, _CUR['error'])
        traceback.print_exc(limit=6)
        _CUR['registros'] = []  # el savepoint deshizo lo creado


def qa_name(texto):
    return '%s %s' % (QA_PREFIX, texto)
