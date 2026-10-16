# -*- coding: utf-8 -*-
"""Lectura de las hojas de proyección de materiales de Allcenter (v1.8,
M17-18), sin Odoo: devuelve datos que el asistente valida y escribe.

Formato leído en el Drive de Allcenter (16-oct-2026):

* Pestaña resumen «… POR PISO»: fila de etapas (PRODUCCIÓN, ARMADO,
  INSTALACIÓN, ACABADOS) sobre cada columna de material, fila de nombres
  cortos, fila de códigos y fila de nombres completos («DESCRIPCION…»). Luego
  «PISO 01» y una fila por unidad: «COCINA 04_DEP 104» con su cantidad, o
  agrupaciones sin departamento (ductos por piso, estacionamientos por
  sótano, una tipología con cantidad).
* Cocinas: una pestaña por tipología («COCINA 04») y un bloque «MODULO:» por
  módulo: nombres y códigos de los materiales, filas de piezas (cantidad,
  largo, ancho, tipo de pieza, descripción y consumo por material) y la fila
  «Total». La marca «MODULO ALTO» separa los módulos altos de los bajos.
* Closet, baño, lavandería, ducto y estacionamiento: una pestaña con un
  bloque por tipología completa («CL-01»).

Anomalías que se detectan (avisos): columnas de material fuera del rango del
resumen (los tarugos de las cajoneras), la fila de etapas corrida una
columna y totales de módulo que no cuadran con sus piezas (fórmula
desplazada).
"""
import re
import unicodedata
from collections import defaultdict

STAGE_WORDS = {
    'PRODUCCION': 'production', 'ARMADO': 'assembly', 'INSTALACION': 'installation',
    'ACABADO': 'finishing', 'ACABADOS': 'finishing', 'LIMPIEZA': 'cleaning',
}
SKIP_SHEETS = {'CODIGOS', 'FORMULARIO', 'LEEME', 'RESUMEN'}
FAMILY_WORDS = [
    ('COCINA', 'kitchen'), ('CLOSET', 'closet'), ('BANO', 'bathroom'),
    ('LAVANDERIA', 'laundry'), ('DUCTO', 'duct'), ('ESTACIONAMIENTO', 'other'),
]


def key(text):
    """Texto comparable: sin tildes, mayúsculas, un espacio."""
    text = unicodedata.normalize('NFKD', str(text or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(text.upper().split())


def typology_key(text):
    """Clave de una tipología: «CL -02a´» y «CL 02a» son la misma (CL02A);
    «COCINA 04» y «COCINA 04 » también."""
    return re.sub(r'[^A-Z0-9]', '', key(text))


def code_text(value):
    """Código de producto de una celda (3101010.0 → «3101010»)."""
    if value in (None, ''):
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return '' if key(text) in ('SIN COD', 'SIN CODIGO', '0') else text


def number(value):
    if value in (None, ''):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(',', '.'))
    except ValueError:
        return 0.0


def family_of(text):
    text = key(text)
    for word, family in FAMILY_WORDS:
        if word in text:
            return family
    return False


def width_from_name(name):
    """Ancho en mm al final del nombre: «MOD LAVADERO 800- COCINA 01» → 800."""
    head = re.split(r'\s*-\s*(COCINA|CLOSET|BANO|LAVANDERIA)', key(name))[0]
    numbers = re.findall(r'(\d{3,4})', head)
    return int(numbers[-1]) if numbers else 0


def module_name(name):
    """Nombre del módulo sin el sufijo de la tipología copiada."""
    return re.split(r'\s*-\s*(COCINA|CLOSET|BAÑO|BANO|LAVANDERIA)\b', str(name or '').strip(),
                    flags=re.IGNORECASE)[0].strip()


def _rows(worksheet):
    return [list(row) for row in worksheet.iter_rows(values_only=True)]


def parse_summary(worksheet, warnings):
    """Columnas de material (etapa, nombre corto, código y nombre completo)
    y unidades de la pestaña resumen."""
    rows = _rows(worksheet)
    stage_row = names_row = None
    for index, row in enumerate(rows[:12]):
        stages = [STAGE_WORDS.get(key(v)) for v in row]
        if sum(1 for s in stages if s) >= 3:
            stage_row = index
            names_row = index + 1
            break
    if stage_row is None:
        warnings.append('La pestaña %s no tiene la fila de etapas.' % worksheet.title)
        return {'columns': [], 'units': []}
    names = rows[names_row] if names_row < len(rows) else []
    codes = rows[names_row + 1] if names_row + 1 < len(rows) else []
    full_index = next((i for i in range(names_row + 1, min(names_row + 5, len(rows)))
                       if any('DESCRIPCION' in key(v) for v in rows[i][:3])), names_row + 2)
    full = rows[full_index] if full_index < len(rows) else []
    width = max(len(names), len(full))
    material_cols = [c for c in range(3, width)
                     if (c < len(names) and names[c] not in (None, ''))
                     or (c < len(full) and full[c] not in (None, ''))]
    stages = rows[stage_row]
    # Fila de etapas corrida una columna: la primera etapa no cae sobre la
    # primera columna de material.
    first_stage = next((c for c, v in enumerate(stages) if STAGE_WORDS.get(key(v))), None)
    shift = (first_stage - material_cols[0]) if material_cols and first_stage is not None else 0
    if shift:
        warnings.append(
            'Fila de etapas corrida %s columna(s) en %s: se toma la etapa de la columna corregida.'
            % (shift, worksheet.title))
    columns = []
    last_stage = False
    for c in material_cols:
        raw = stages[c + shift] if 0 <= c + shift < len(stages) else None
        stage = STAGE_WORDS.get(key(raw)) or last_stage
        last_stage = stage
        columns.append({
            'col': c, 'stage': stage,
            'name': str(names[c]).strip() if c < len(names) and names[c] else '',
            'code': code_text(codes[c]) if c < len(codes) else '',
            'full_name': str(full[c]).strip() if c < len(full) and full[c] else '',
        })
    units = []
    floor = False
    for row in rows[full_index + 1:]:
        first, label = row[0] if row else None, row[1] if len(row) > 1 else None
        if first and key(first).startswith(('PISO', 'SOTANO', 'NIVEL', 'TORRE', 'AZOTEA')):
            floor = str(first).strip()
            continue
        if not label or key(label).startswith(('TOTAL', 'CONVERSION')):
            continue
        qty = number(row[2] if len(row) > 2 else 1) or 1.0
        text = str(label).strip()
        typology, _sep, unit = text.partition('_')
        units.append({'floor': floor or 'Sin piso', 'typology': typology.strip(),
                      'unit': unit.strip() or False, 'qty': qty})
    return {'columns': columns, 'units': units}


def parse_blocks(worksheet, warnings):
    """Bloques «MODULO:» de una pestaña: nombre, grupo (bajo o alto),
    columnas de material, piezas y totales."""
    rows = _rows(worksheet)
    blocks = []
    group = 'low'
    index = 0
    while index < len(rows):
        row = rows[index]
        first = key(row[0]) if row else ''
        if first == 'MODULO ALTO':
            group = 'high'
            index += 1
            continue
        if first != 'MODULO:':
            index += 1
            continue
        header = row
        name = str(row[1]).strip() if len(row) > 1 and row[1] else ''
        codes_index = next((i for i in range(index + 1, min(index + 4, len(rows)))
                            if rows[i] and key(rows[i][0]) == 'CANT.'), index + 2)
        codes = rows[codes_index] if codes_index < len(rows) else []
        columns = {}
        for c in range(5, max(len(header), len(codes))):
            name_cell = header[c] if c < len(header) else None
            code = code_text(codes[c]) if c < len(codes) else ''
            if name_cell in (None, '') and not code:
                continue
            columns[c] = {'name': str(name_cell or '').strip(), 'code': code}
        pieces, totals = [], {}
        piece_sums = defaultdict(float)
        cursor = codes_index + 1
        while cursor < len(rows):
            piece = rows[cursor]
            first = key(piece[0]) if piece else ''
            if first == 'TOTAL':
                totals = {c: number(piece[c]) for c in columns if c < len(piece)}
                cursor += 1
                break
            if first in ('MODULO:', 'MODULO ALTO'):
                break
            if piece and isinstance(piece[0], (int, float)) and len(piece) > 3 and piece[3]:
                pieces.append({'qty': number(piece[0]), 'length_mm': number(piece[1]),
                               'width_mm': number(piece[2]), 'piece_type': str(piece[3]).strip(),
                               'color': str(piece[4]).strip() if len(piece) > 4 and piece[4]
                               else ''})
                for c in columns:
                    if c < len(piece):
                        piece_sums[c] += number(piece[c])
            cursor += 1
        blocks.append({'name': name, 'group': group, 'columns': columns, 'pieces': pieces,
                       'totals': totals, 'piece_sums': dict(piece_sums),
                       'sheet': worksheet.title})
        index = cursor
    return blocks


def _col_letter(index):
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def parse_workbook(workbook):
    """``{family, summary, typologies: [{code, name, blocks, sheet}], kind,
    warnings}``. ``kind`` es «tabs» (una pestaña por tipología, cocinas) o
    «blocks» (un bloque por tipología)."""
    warnings = []
    summary_sheet = next((ws for ws in workbook.worksheets if ' POR ' in ' %s ' % key(ws.title)),
                         None)
    summary = parse_summary(summary_sheet, warnings) if summary_sheet else {
        'columns': [], 'units': []}
    if not summary_sheet:
        warnings.append('El libro no tiene la pestaña resumen («… POR PISO»).')
    family = family_of(summary_sheet.title if summary_sheet else '') or family_of(
        ' '.join(ws.title for ws in workbook.worksheets))
    unit_keys = {typology_key(unit['typology']) for unit in summary['units']}
    typologies = []
    for worksheet in workbook.worksheets:
        if worksheet is summary_sheet or key(worksheet.title) in SKIP_SHEETS:
            continue
        blocks = parse_blocks(worksheet, warnings)
        if not blocks:
            continue
        title = worksheet.title.strip()
        if typology_key(title) in unit_keys or len(workbook.worksheets) > 4 and \
                family == 'kitchen':
            typologies.append({'code': title, 'name': title, 'blocks': blocks,
                               'sheet': worksheet.title, 'kind': 'tabs'})
        else:
            for block in blocks:
                typologies.append({'code': module_name(block['name']) or block['name'],
                                   'name': module_name(block['name']) or block['name'],
                                   'blocks': [dict(block, group='block')],
                                   'sheet': worksheet.title, 'kind': 'blocks'})
    # Columnas de los bloques fuera del rango del resumen (tarugos extra).
    summary_names = [name_key(column['name']) for column in summary['columns']]
    reported = set()
    for typology in typologies:
        for block in typology['blocks']:
            for column in block['columns'].values():
                if column['name'] and name_key(column['name']) not in summary_names \
                        and name_key(column['name']) not in reported:
                    reported.add(name_key(column['name']))
                    warnings.append(
                        'Columna «%s» (pestaña %s) fuera del rango que suma el resumen: se '
                        'importa y se revisa su etapa.' % (column['name'], typology['sheet']))
    return {'family': family, 'summary': summary, 'typologies': typologies,
            'warnings': warnings}


def name_key(text):
    """Nombre corto comparable: «BISAGRA 180°» y «BISAGRA  180» son el mismo."""
    return re.sub(r'[^A-Z0-9*]', '', key(text))


def check_totals(parsed, materials):
    """Totales de módulo con fórmula desplazada: la conversión del total
    (planchas, ML con merma) de una columna es la misma en todo el libro; un
    bloque cuya conversión se aparta de la usual tiene la fórmula corrida
    (MOMEN, COCINA - 04: el durolac en m² × 1,1 en vez de planchas)."""
    ratios = defaultdict(list)
    for typology in parsed['typologies']:
        for block in typology['blocks']:
            for c, material_key in block.get('keys', {}).items():
                total, pieces = block['totals'].get(c, 0.0), block['piece_sums'].get(c, 0.0)
                if total > 0 and pieces > 0:
                    ratios[material_key].append((total / pieces, block, c))
    for material_key, values in ratios.items():
        ordered = sorted(r for r, _b, _c in values)
        usual = ordered[len(ordered) // 2]
        for ratio, block, c in values:
            if usual and abs(ratio / usual - 1.0) > 0.05:
                parsed['warnings'].append(
                    'Total con fórmula desplazada en %s, %s, columna %s (%s): convierte ×%s y la '
                    'columna suele convertir ×%s.' % (
                        block['sheet'], module_name(block['name']),
                        materials[material_key]['name'], _col_letter(c), round(ratio, 4),
                        round(usual, 4)))


def match_columns(parsed):
    """Une cada columna de material de los bloques con la del resumen por su
    nombre corto, en orden de aparición (hay dos «tor 4*50»: armado e
    instalación). Devuelve ``{(nombre, ocurrencia): {stage, summary_code,
    full_name, codes:set}}`` y, en cada bloque, ``col → clave``."""
    summary = parsed['summary']['columns']
    by_name = defaultdict(list)
    by_col = {column['col']: column for column in summary}
    for column in summary:
        by_name[name_key(column['name'])].append(column)
    materials = {}
    for typology in parsed['typologies']:
        for block in typology['blocks']:
            seen = defaultdict(int)
            block['keys'] = {}
            for c in sorted(block['columns']):
                column = block['columns'][c]
                name = name_key(column['name']) or 'COL%s' % _col_letter(c)
                occurrence = seen[name]
                seen[name] += 1
                ref = by_name.get(name, [])
                ref = ref[occurrence] if occurrence < len(ref) else None
                if not ref and c - 2 in by_col and not column['name']:
                    # Sin nombre: la columna del resumen en la misma posición
                    # (el resumen empieza dos columnas antes).
                    ref = by_col[c - 2]
                material_key = (name, occurrence)
                item = materials.setdefault(material_key, {
                    'name': column['name'] or name, 'stage': ref['stage'] if ref else (
                        'assembly' if 'TARUGO' in name else
                        by_col[c - 2]['stage'] if c - 2 in by_col else False),
                    'unit_name': name,
                    'summary_code': ref['code'] if ref else '',
                    'full_name': ref['full_name'] if ref else '', 'codes': set(),
                    'in_summary': bool(ref)})
                if column['code']:
                    item['codes'].add(column['code'])
                block['keys'][c] = material_key
    check_totals(parsed, materials)
    return materials
