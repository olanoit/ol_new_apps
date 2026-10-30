# -*- coding: utf-8 -*-
"""Genera ANEXO_CASOS.md con cada caso validado a partir de resultados/*.json.

    python3 generar_anexo.py

Una fase «<fase>_<sufijo>» que repite casos de «<fase>» (mismo módulo y
título) reemplaza el resultado original: se muestra el de la repetición y
se anota la corrida en que falló primero.
"""
import glob
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
ORDEN = [
    ('fase0_navegador', 'Fase 0 · Cliente web en navegador'),
    ('contabilidad_a', 'Fase 1A · Contabilidad: base, impuestos y reportes'),
    ('contabilidad_b', 'Fase 1B · Contabilidad: cobros, pagos, bancos y cierre'),
    ('facturacion_tpv', 'Fases 2 y 3 · Facturación electrónica y TPV'),
    ('inventario_farmacia', 'Fases 4 y 7 · Inventario, farmacia e industrias'),
    ('proyectos', 'Fase 5 · Proyectos y construcción'),
    ('planillas_tools', 'Fases 6 y 8 · Planillas y herramientas'),
]
REPETICIONES = {'proyectos': ['proyectos_ingreso']}
ICONO = {'OK': '✅', 'AVISO': '⚠️', 'FALLA': '❌', 'OMITIDO': '⏭️'}


def cargar(fase):
    with open(os.path.join(DIR, 'resultados', '%s.json' % fase)) as fh:
        return json.load(fh)['casos']


def casos_de(fase):
    casos = cargar(fase)
    for rep in REPETICIONES.get(fase, []):
        repetidos = {(c['modulo'], c['titulo']): c for c in cargar(rep)}
        for i, c in enumerate(casos):
            nuevo = repetidos.get((c['modulo'], c['titulo']))
            if nuevo:
                nuevo = dict(nuevo, repeticion='%s (en «%s» quedó %s)' % (rep, fase, c['estado']))
                casos[i] = nuevo
    return casos


def celda(texto):
    return str(texto or '').replace('|', '\\|').replace('\n', ' ')


def main():
    out = ['# Anexo · Casos validados en Odoo 20', '',
           'Generado por `generar_anexo.py` desde `resultados/*.json`. Cada caso es una',
           'ejecución real sobre `ce20_db_ol`; los registros listados quedaron en la base',
           '(nombres con prefijo `QA20`).', '']
    resumen = []
    cuerpo = []
    for fase, titulo in ORDEN:
        casos = casos_de(fase)
        cuenta = {}
        for c in casos:
            cuenta[c['estado']] = cuenta.get(c['estado'], 0) + 1
        checks = sum(len(c['checks']) for c in casos)
        resumen.append('| %s | %d | %d | %s |' % (
            titulo, len({c['modulo'] for c in casos}), len(casos),
            ' · '.join('%s %d' % (ICONO[k], v) for k, v in sorted(cuenta.items())) + ' · %d comprobaciones' % checks))
        cuerpo += ['', '## %s' % titulo, '']
        modulo = None
        for c in casos:
            if c['modulo'] != modulo:
                modulo = c['modulo']
                cuerpo += ['', '### `%s`' % modulo, '']
            cuerpo.append('#### %s %s' % (ICONO[c['estado']], c['titulo']))
            cuerpo.append('')
            if c.get('pasos'):
                cuerpo += ['**Pasos en pantalla:** %s' % c['pasos'], '']
            if c.get('repeticion'):
                cuerpo += ['*Resultado de la repetición %s.*' % c['repeticion'], '']
            cuerpo += ['| Estado | Comprobación | Detalle |', '|---|---|---|']
            for k in c['checks']:
                cuerpo.append('| %s | %s | %s |' % (ICONO[k['estado']], celda(k['titulo']), celda(k['detalle'])[:300]))
            if c.get('registros'):
                regs = ', '.join('`%s/%s` %s' % (r['modelo'], r['id'], celda(r['nombre'])[:60]) for r in c['registros'][:12])
                if len(c['registros']) > 12:
                    regs += ' … (+%d)' % (len(c['registros']) - 12)
                cuerpo += ['', '**Registros:** ' + regs]
            cuerpo.append('')
    out += ['| Bloque | Módulos | Casos | Resultado |', '|---|---:|---:|---|'] + resumen + cuerpo
    with open(os.path.join(DIR, 'ANEXO_CASOS.md'), 'w') as fh:
        fh.write('\n'.join(out) + '\n')
    print('\n'.join(resumen))


if __name__ == '__main__':
    main()
