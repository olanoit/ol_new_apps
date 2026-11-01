# -*- coding: utf-8 -*-
"""Prueba de punta a punta del paquete 1.13 (dentro del 1.16) con un libro real.

Lee un libro «Maestro de planificación», lo analiza como «Validar», lo importa
en una obra temporal y entrega las cifras que piden los criterios de
aceptación:

* M113-01: errores y avisos del análisis, por pestaña;
* M113-07: indicadores de INICIO (muebles, módulos a armar, ML, piezas y
  costo de materiales) y conteos por piso, como CONTROL;
* M113-09: la ficha de una tipología (pisos, módulos, ML, piezas, costo por
  unidad y por sub etapa, costo en la obra, controversias de ancho y módulos
  sin medida de OT);
* M113-08: lo que dejaría «Copiar piso a otros pisos» (ambientes nuevos y
  números de departamento).

Al final DESHACE todo (rollback): no deja la obra, los productos ni nada en la
base. Los datos del libro no se escriben en el repositorio.

Uso (base de pruebas o, con permiso, una base de desarrollo):

    cd /home/och/odoo/ce19
    AL_BOOK=/ruta/libro.xlsx AL_CARD="<código de tipología>" \\
    AL_COPY_FROM="<piso de origen>" AL_COPY_TO="3-9" \\
    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d test_pe_creval --no-http \\
        < myodoo/ol_new_apps/docs/planificador/pruebas/libro_real_1_13.py

En el servidor, con ``bash /root/shell_dev.sh <contenedor> <base> < script``
y las variables exportadas dentro del contenedor (``docker exec -e``).
"""
import base64
import os
import re
from collections import defaultdict

BOOK = os.environ.get('AL_BOOK')
CARD = os.environ.get('AL_CARD', '')
COPY_FROM = os.environ.get('AL_COPY_FROM', '')
COPY_TO = os.environ.get('AL_COPY_TO', '')


def title(text):
    print('\n== %s' % text)


def parse_floors(text):
    """«3-9», «3, 5, 7» o «3-5, 8» → [3, 4, 5, 8] (como el panel)."""
    result = []
    for part in re.split(r'[,;]', text or ''):
        match = re.match(r'^\s*(-?\d+)\s*(?:-|a|al)\s*(-?\d+)\s*$', part, re.I)
        if match:
            first, last = sorted((int(match.group(1)), int(match.group(2))))
            result.extend(range(first, last + 1))
        elif re.match(r'^\s*-?\d+\s*$', part):
            result.append(int(part))
    return list(dict.fromkeys(result))


def renumber(text, source, target):
    """El número del piso al inicio del primer número (201 → 301)."""
    source = str(source)

    def change(match):
        digits = match.group(0)
        if digits.startswith(source) and len(digits) > len(source):
            return str(target) + digits[len(source):]
        return str(target) if digits == source else digits
    return re.sub(r'\d+', change, str(text or ''), count=1)


def floor_key(row):
    floor = str(row.get('floor') or '').strip()
    group = str(row.get('group') or '').strip()
    return '%s / %s' % (group, floor) if group and floor else floor


assert BOOK and os.path.exists(BOOK), 'Indique el libro en AL_BOOK.'
content = base64.b64encode(open(BOOK, 'rb').read())
site = env['project.project'].create({
    'name': 'Prueba con libro real (temporal)', 'is_construction_site': True})
wizard = env['construction.master.import.wizard'].create({
    'project_id': site.id, 'file': content, 'filename': os.path.basename(BOOK),
    'create_missing_products': True})

title('M113-01 · análisis («Validar»)')
data = wizard._analyze()
print('Errores que impiden importar: %s' % len(data['errors']))
for error in data['errors'][:20]:
    print('  - %s' % error)
by_sheet = defaultdict(lambda: [0, 0])
for sheet, _row, _col, _message, kind in data.get('issues', []):
    by_sheet[sheet][0 if kind == 'error' else 1] += 1
for sheet, (errors, warnings) in sorted(by_sheet.items()):
    print('  %-18s %4s errores %4s avisos' % (sheet, errors, warnings))
for key, values in data['warnings'].items():
    print('  aviso %-28s %s' % (key, len(values)))
print('Estadísticas: %s' % dict(data.get('stats') or {}))

sheets, _errors = wizard._read_workbook()
if data['errors']:
    print('\nEl libro tiene errores: no se importa.')
else:
    wizard.action_import()
    site.invalidate_recordset()
    typologies = env['construction.typology'].search([('project_id', '=', site.id)])
    spaces = env['project.task'].search([('project_id', '=', site.id),
                                         ('construction_level', '=', 'space')])

    def unit_costs(typology):
        """Costo de materiales de un ambiente, total y por sub etapa."""
        by_stage = defaultdict(float)
        for line in typology.sudo().bom_id.bom_line_ids:
            cost = line.product_qty * line.product_id.standard_price
            by_stage[line.construction_consumption_stage or ''] += cost
        return sum(by_stage.values()), by_stage

    def modules_to_assemble(typology):
        return len(typology.module_line_ids.filtered(
            lambda m: m.special_kind != 'plinth' and 'ZOCALO' not in (
                '%s %s' % (m.code or '', m.name or '')).upper().replace('Ó', 'O')))

    title('M113-07 · INICIO')
    count = defaultdict(int)
    for space in spaces:
        count[space.construction_typology_id] += 1
    pieces = sum(p.qty for t in typologies for m in t.module_line_ids for p in m.piece_ids)
    print('Muebles (ambientes): %s' % len(spaces))
    print('Módulos a armar: %s' % sum(modules_to_assemble(t) * n for t, n in count.items()))
    print('ML total: %.2f' % sum(t.ml_total * n for t, n in count.items()))
    print('Piezas por juego de tipologías: %s' % pieces)
    print('Costo de materiales en la obra: %.2f' % sum(
        unit_costs(t)[0] * n for t, n in count.items() if t))
    print('Tipologías: %s · sin tipología: %s' % (len(typologies), count.get(
        env['construction.typology'], 0)))

    title('CONTROL · por piso (ambientes, módulos a armar, ML)')
    site.action_construction_open_spreadsheet()
    document = env['documents.document'].search([('construction_project_id', '=', site.id)],
                                                limit=1)
    for key, n_spaces, modules, ml in document.construction_control_counts():
        print('  %-30s %4s %5s %8.2f' % (key, n_spaces, modules, ml))

    if CARD:
        title('M113-09 · FICHA de %s' % CARD)
        typology = typologies.filtered(lambda t: t.code == CARD)
        if not typology:
            print('No existe la tipología %s.' % CARD)
        else:
            mine = spaces.filtered(lambda s: s.construction_typology_id == typology)
            floors = set()
            for space in mine:
                parent = space.parent_id
                while parent and parent.construction_level != 'floor':
                    parent = parent.parent_id
                if parent:
                    floors.add(parent.name)
            floors = sorted(floors)
            total, by_stage = unit_costs(typology)
            print('En la obra: %s · pisos: %s' % (len(mine), ', '.join(floors) or '—'))
            print('Módulos: %s · ML bajo %.2f · alto %.2f · completo %.2f' % (
                len(typology.module_line_ids), typology.ml_low, typology.ml_high,
                typology.ml_full))
            print('Piezas: %s' % sum(p.qty for m in typology.module_line_ids
                                     for p in m.piece_ids))
            print('Costo por unidad: %.2f · en la obra: %.2f' % (total, total * len(mine)))
            for stage, amount in sorted(by_stage.items()):
                print('  sub etapa %-20s %.2f' % (stage or '(sin etapa)', amount))
            for module in typology.module_line_ids:
                widths = [p.length_mm for p in module.piece_ids
                          if (p.piece_type or '').upper() in ('BASE', 'TAPA', 'TECHO')]
                piece_width = max(widths) if widths else 0
                if not module.width_mm:
                    print('  %-10s Sin medida de OT' % module.code)
                elif piece_width and piece_width != module.width_mm:
                    print('  %-10s Controversia de ancho: OT %s frente a piezas %s' % (
                        module.code, module.width_mm, piece_width))

if COPY_FROM and COPY_TO:
    title('M113-08 · Copiar piso %s a %s' % (COPY_FROM, COPY_TO))
    tree = sheets.get('ARBOL') or []
    source = [row for row in tree if floor_key(row).lower() == COPY_FROM.strip().lower()]
    number = re.search(r'\d+', str(source[0].get('floor'))) if source else None
    if not number:
        print('El piso %s no está en ARBOL o no tiene número.' % COPY_FROM)
    else:
        start = int(number.group(0))
        existing = {floor_key(row).lower() for row in tree}
        created, skipped, examples = 0, [], []
        for target in [n for n in parse_floors(COPY_TO) if n != start]:
            floor = renumber(source[0].get('floor'), start, target)
            group = str(source[0].get('group') or '').strip()
            key = ('%s / %s' % (group, floor) if group else floor).lower()
            if key in existing:
                skipped.append(floor)
                continue
            created += len(source)
            examples.append(renumber(source[0].get('apartment'), start, target))
        print('Ambientes del piso de origen: %s' % len(source))
        print('Ambientes nuevos: %s · pisos con ambientes (no se copian): %s' % (
            created, ', '.join(skipped) or '—'))
        print('Primer departamento de cada piso nuevo: %s' % ', '.join(examples))

env.cr.rollback()
print('\nListo: todo se deshizo (rollback).')
