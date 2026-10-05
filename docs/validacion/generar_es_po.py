#!/usr/bin/env python3
"""Genera ``i18n/es.po`` de un módulo cuyos textos de origen ya están en español.

En un modelo NUEVO, Odoo traduce los campos heredados de los mixins
(actividades, seguidores, analítica, «Creado el»…) solo con el ``.po`` del
propio módulo: sin él, esas etiquetas salen en inglés aunque la interfaz esté
en español. Este script toma la plantilla exportada y la rellena con las
traducciones oficiales de los módulos de origen (``es_419`` y luego ``es``).
También ajusta las mayúsculas (solo la primera letra) y añade los valores de
selección heredados (``activity_state``…), cuyos xmlids son de otro módulo.

Uso:
    odoo-bin i18n export -c cfg/my/pe.cfg -d ol_pe_v19 <módulo> -o /tmp/<módulo>.pot
    python docs/validacion/generar_es_po.py <módulo> /tmp/<módulo>.pot <ruta_del_módulo>/i18n/es.po \\
        [--selecciones xmlid1,xmlid2,...]
    odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u <módulo> --i18n-overwrite --stop-after-init

Notas (ver memoria «Etiquetas en español»):
- No dejar el ``.pot`` en ``i18n/``: Odoo fusiona el ``.po`` con él y descarta
  las entradas que el ``.pot`` no tiene (las selecciones de otros módulos).
- Cada entrada necesita ``#. module: <módulo>`` o el lector la ignora.
"""
import argparse
import glob
import re
from pathlib import Path

import polib

ODOO = Path(__file__).resolve().parents[4]          # ~/odoo/ce19
PRIORITY = ['mail', 'analytic', 'base', 'base_tier_validation', 'rating', 'sms',
            'portal', 'website_mail', 'stock', 'purchase', 'project', 'uom', 'product']
OCC_RE = re.compile(r'model:ir\.model\.fields(?:\.selection)?,(\w+):\w+\.(?:field|selection)_\w+?__(\w+)')

# Traducciones oficiales con mayúsculas intermedias o términos que no
# encajan: se fuerzan estas.
FIX = {
    'Hide Reviews': 'Ocultar revisiones',
    'Next Review': 'Siguiente revisión',
    'Validated Message': 'Mensaje de validación',
    'To Validate Message': 'Mensaje por validar',
    'Rejected Message': 'Mensaje de rechazo',
    'Has Comment': 'Tiene comentario',
    'Transfer': 'Transferencia',
}
SELECTION_LABELS = {
    'activity_state': {'overdue': 'Overdue', 'today': 'Today', 'planned': 'Planned'},
    'activity_exception_decoration': {'warning': 'Alert', 'danger': 'Error'},
    'validation_status': {'no': 'Without validation', 'waiting': 'Waiting',
                          'pending': 'Pending', 'rejected': 'Rejected',
                          'validated': 'Validated'},
}


def official_translations():
    dirs = {}
    for pattern in ('addons/*/i18n', 'odoo/addons/*/i18n', 'ee19/*/i18n',
                    'apps/oca/*/*/i18n', 'myodoo/ol_new_apps/*/*/i18n'):
        for d in glob.glob(str(ODOO / pattern)):
            dirs.setdefault(d.split('/')[-2], d)
    order = [m for m in PRIORITY if m in dirs] + sorted(m for m in dirs if m not in PRIORITY)
    by_field, by_msgid = {}, {}
    for module in order:
        for lang in ('es_419', 'es'):
            path = Path(dirs[module]) / f'{lang}.po'
            if not path.exists():
                continue
            try:
                po = polib.pofile(str(path))
            except Exception:  # noqa: BLE001 - .po dañado de terceros
                continue
            for e in po:
                if not e.msgstr or e.obsolete:
                    continue
                by_msgid.setdefault(e.msgid, e.msgstr)
                for occ, _line in e.occurrences:
                    m = OCC_RE.match(occ)
                    if m:
                        by_field.setdefault((m.group(1), m.group(2), e.msgid), e.msgstr)
    return by_field, by_msgid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('module')
    ap.add_argument('pot')
    ap.add_argument('out')
    ap.add_argument('--selecciones', default='',
                    help='xmlids de selecciones heredadas (mail.selection__<modelo>__<campo>__<valor>), separados por comas')
    args = ap.parse_args()

    by_field, by_msgid = official_translations()
    out = polib.POFile()
    out.metadata = {'Project-Id-Version': 'Odoo Server 19.0', 'MIME-Version': '1.0',
                    'Content-Type': 'text/plain; charset=UTF-8',
                    'Content-Transfer-Encoding': '', 'Language': 'es',
                    'Plural-Forms': 'nplurals=2; plural=(n != 1);'}
    out.header = (f'Traducción al español de {args.module}.\n'
                  'Los textos propios ya están en español; aquí se traducen los campos\n'
                  'heredados de los mixins. Generado con docs/validacion/generar_es_po.py.')
    comment = f'module: {args.module}'
    for e in polib.pofile(args.pot):
        msgstr = ''
        for occ, _line in e.occurrences:
            m = OCC_RE.match(occ)
            if m and (m.group(1), m.group(2), e.msgid) in by_field:
                msgstr = by_field[(m.group(1), m.group(2), e.msgid)]
                break
        msgstr = FIX.get(e.msgid) or msgstr or by_msgid.get(e.msgid, '')
        if msgstr and msgstr != e.msgid:
            out.append(polib.POEntry(msgid=e.msgid, msgstr=msgstr, occurrences=e.occurrences,
                                     flags=e.flags, comment=comment, tcomment=e.tcomment))
    for xmlid in filter(None, args.selecciones.split(',')):
        m = re.match(r'(\w+)\.selection__\w+?__(activity_state|activity_exception_decoration|validation_status)__(\w+)$', xmlid)
        if not m:
            continue
        msgid = SELECTION_LABELS[m.group(2)][m.group(3)]
        occ = (f'model:ir.model.fields.selection,name:{xmlid}', '')
        entry = out.find(msgid)
        if entry:
            if occ not in entry.occurrences:
                entry.occurrences.append(occ)
        elif by_msgid.get(msgid):
            out.append(polib.POEntry(msgid=msgid, msgstr=by_msgid[msgid],
                                     occurrences=[occ], comment=comment))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out)
    print(f'{args.out}: {len(out)} entradas')


if __name__ == '__main__':
    main()
