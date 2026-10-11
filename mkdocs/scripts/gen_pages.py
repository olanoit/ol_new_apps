# -*- coding: utf-8 -*-
"""Genera las partes del sitio que salen del código del repositorio.

El contenido se escribe a mano en ``mkdocs/content/``, organizado como la
documentación de Odoo (``applications/``, ``administration/``,
``developer/``, ``contributing/``). Este script, que corre con el plugin
``mkdocs-gen-files`` en cada construcción (nada de lo que produce se guarda en
git), agrega lo que sale de los módulos:

* ``developer/reference/``: la referencia de cada módulo (ficha desde el
  manifiesto y ``docs/fichas/<módulo>.yml``, ``README.md``, ``CHANGELOG.md``,
  ``docs/**/*.md`` y los fragmentos ``readme/*.md`` de OCA), con enlaces a
  las páginas funcionales que lo documentan (``modulos:`` en su encabezado),
  y una página por área desde ``OL-<ÁREA>/README.md``.
* ``developer/specs/``: las especificaciones de ``docs/<carpeta>/``.
* ``developer/repository.md``: el ``README.md`` raíz.
* ``applications/novedades.md``: las novedades de todas las fichas.
* ``mkdocs/plantillas/*.md``: portada, versiones y etiquetas, con los
  marcadores ``{{ odoo_version }}``, ``{{ areas }}`` y ``{{ cifras }}``.

Los enlaces relativos entre archivos del repositorio se reescriben a la
página del sitio que los contiene; las imágenes y adjuntos (xlsx, pdf, csv)
se copian a ``_media/``, y lo demás (código, carpetas sin página) apunta al
archivo en GitHub en la rama de la versión.
"""
import ast
import logging
import posixpath
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

import mkdocs_gen_files
import yaml

log = logging.getLogger('mkdocs.plugins.gen_pages')

ROOT = Path(__file__).resolve().parents[2]
CONFIG = mkdocs_gen_files.config
EXTRA = CONFIG.extra
ODOO_VERSION = str(EXTRA.get('odoo_version') or '19.0')
BRANCH = str(EXTRA.get('git_branch') or ODOO_VERSION)
REPO_URL = (CONFIG.repo_url or '').rstrip('/')
ODOO_DOCS = 'https://www.odoo.com/documentation/%s/es_419/' % ODOO_VERSION

# Áreas del repositorio: la lista y su orden salen de scripts/areas.py; aquí
# solo su presentación (ruta en el sitio, título e ícono de Material).
AREA_SITE = {
    'OL-ACCOUNTING': ('contabilidad', 'Contabilidad', 'material/calculator-variant'),
    'OL-INVOICING': ('facturacion', 'Facturación', 'material/receipt-text'),
    'OL-PAYROLL': ('planillas', 'Planillas', 'material/account-cash'),
    'OL-POS': ('punto-de-venta', 'Punto de venta', 'material/point-of-sale'),
    'OL-INVENTORY': ('inventario', 'Inventario', 'material/warehouse'),
    'OL-PROJECTS': ('proyectos', 'Proyectos y obras', 'material/crane'),
    'OL-TOOLS': ('herramientas', 'Herramientas', 'material/tools'),
    'OL-THIRD-PARTY': ('terceros', 'Terceros', 'material/puzzle'),
}
CONTENT = ROOT / 'mkdocs' / 'content'
DEV = 'developer'
REF = 'developer/reference'
TECH = 'developer/specs'
NEWS = 'applications/novedades.md'
# Plantillas y su lugar en el sitio.
TEMPLATES = {
    'index.md': 'index.md',
    'versiones.md': 'administration/versions.md',
    'etiquetas.md': 'developer/reference/tags.md',
}
IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}
ATTACH_EXT = {'.xlsx', '.xls', '.csv', '.pdf', '.txt', '.zip', '.json', '.xml'}
SKIP_DIRS = {'static', 'i18n', 'tests', 'node_modules', '__pycache__', '.git'}


def _load_areas():
    namespace = {'__file__': str(ROOT / 'scripts' / 'areas.py')}
    exec((ROOT / 'scripts' / 'areas.py').read_text(encoding='utf-8'), namespace)
    return namespace['AREAS'], namespace['THIRD_PARTY']


AREAS, THIRD_PARTY = _load_areas()
missing = [area for area in AREAS if area not in AREA_SITE]
if missing:
    raise SystemExit('Áreas sin presentación en mkdocs/scripts/gen_pages.py: %s' % missing)


# ----------------------------------------------------------------------
# Inventario: módulos, páginas y destino de cada archivo
# ----------------------------------------------------------------------
class Module:
    def __init__(self, area, path):
        self.area = area
        self.path = path
        self.name = path.name
        self.manifest = ast.literal_eval((path / '__manifest__.py').read_text(encoding='utf-8'))
        ficha = ROOT / 'docs' / 'fichas' / ('%s.yml' % self.name)
        self.ficha_path = ficha if ficha.exists() else None
        self.ficha = yaml.safe_load(ficha.read_text(encoding='utf-8')) if self.ficha_path else {}
        self.vdir = '%s/modules/%s' % (REF, self.name)

    @property
    def title(self):
        return clean(self.ficha.get('titulo') or self.manifest.get('name') or self.name)

    @property
    def version(self):
        return str(self.manifest.get('version', ''))

    @property
    def summary(self):
        return clean(self.manifest.get('summary') or self.ficha.get('subtitulo') or '')


def clean(text):
    return ' '.join(str(text).split())


MODULES = []
for _area in AREAS:
    for _path in sorted((ROOT / _area).iterdir()):
        if (_path / '__manifest__.py').exists():
            MODULES.append(Module(_area, _path))
BY_NAME = {module.name: module for module in MODULES}

# Página del sitio de cada archivo Markdown del repositorio: {ruta absoluta: ruta virtual}.
PAGES = {}
# Página índice de cada carpeta enlazable: {carpeta absoluta: ruta virtual}.
DIRS = {ROOT: '%s/repository.md' % DEV}
# Contenido de las páginas que no salen de un solo archivo: {ruta virtual: texto}.
GENERATED = {}
# Archivo de origen de cada página (para «Editar en GitHub»).
EDIT = {}
TITLES = {}


def first_heading(path):
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r'#\s+(.+)', line)
        if match:
            return match.group(1).strip()
        if i + 1 < len(lines) and re.match(r'=+\s*$', lines[i + 1]) and line.strip():
            return line.strip()
    return path.stem.replace('_', ' ')


def md_files(folder):
    for path in sorted(folder.rglob('*.md')):
        if not SKIP_DIRS.intersection(path.relative_to(folder).parts):
            yield path


for _area in AREAS:
    slug = AREA_SITE[_area][0]
    PAGES[ROOT / _area / 'README.md'] = '%s/%s/index.md' % (REF, slug)
    DIRS[ROOT / _area] = '%s/%s/index.md' % (REF, slug)


def front_matter(path):
    text = path.read_text(encoding='utf-8')
    match = re.match(r'---\n(.*?)\n---\n', text, re.S)
    return (yaml.safe_load(match.group(1)) or {}) if match else {}


# Páginas escritas a mano (mkdocs/content/): su ruta en el sitio es la misma,
# y las que declaran ``modulos:`` documentan esos módulos.
FUNCTIONAL = defaultdict(list)  # módulo → [(título, ruta virtual)]
CONTENT_PAGES = []
for _path in sorted(CONTENT.rglob('*.md')):
    _rel = _path.relative_to(CONTENT).as_posix()
    PAGES[_path] = _rel
    CONTENT_PAGES.append(_path)
    for _name in front_matter(_path).get('modulos') or []:
        FUNCTIONAL[_name].append((first_heading(_path), _rel))

MODULE_PAGES = defaultdict(list)  # módulo → [(título, ruta virtual)]
for module in MODULES:
    DIRS[module.path] = '%s/index.md' % module.vdir
    special = {
        'CHANGELOG.md': ('Novedades', 'novedades.md'),
        'README.md': ('Descripción técnica', 'descripcion-tecnica.md'),
    }
    for path in md_files(module.path):
        rel = path.relative_to(module.path).as_posix()
        if rel in special:
            title, target = special[rel]
        elif rel.startswith('readme/'):
            continue  # fragmentos OCA: van juntos en una página
        else:
            title, target = first_heading(path), rel.lower()
            if target.endswith('/readme.md'):
                target = target[:-len('readme.md')] + 'index.md'
        PAGES[path] = '%s/%s' % (module.vdir, target)
        MODULE_PAGES[module.name].append((title, PAGES[path]))
    if (module.path / 'docs').is_dir():
        DIRS[module.path / 'docs'] = PAGES.get(module.path / 'docs' / 'README.md',
                                               '%s/index.md' % module.vdir)
    fragments = sorted((module.path / 'readme').glob('*.md')) if (module.path / 'readme').is_dir() else []
    if fragments:
        MODULE_PAGES[module.name].append(('Documentación del autor', '%s/autor.md' % module.vdir))
        for fragment in fragments:
            PAGES[fragment] = '%s/autor.md' % module.vdir

order = {'Descripción técnica': 1, 'Documentación del autor': 2, 'Novedades': 9}
for pages in MODULE_PAGES.values():
    pages.sort(key=lambda item: (order.get(item[0], 5), item[1]))

# Especificaciones: docs/<carpeta>/**/*.md, más el README raíz.
PAGES[ROOT / 'README.md'] = '%s/repository.md' % DEV
DIRS[ROOT / 'docs'] = '%s/index.md' % TECH
DIRS[CONTENT] = 'index.md'
TECH_FOLDERS = []
for folder in sorted(p for p in (ROOT / 'docs').iterdir() if p.is_dir()):
    files = list(md_files(folder))
    if not files:
        continue
    TECH_FOLDERS.append(folder)
    for path in files:
        rel = path.relative_to(folder).as_posix()
        if rel.lower().endswith('readme.md'):
            rel = rel[:-len('readme.md')] + 'index.md'
        PAGES[path] = '%s/%s/%s' % (TECH, folder.name, rel.lower())
    for sub in [folder, *(p for p in folder.rglob('*') if p.is_dir())]:
        readme = sub / 'README.md'
        DIRS[sub] = PAGES.get(readme) or '%s/%s/index.md' % (TECH, folder.name)


# ----------------------------------------------------------------------
# Reescritura de enlaces
# ----------------------------------------------------------------------
MEDIA = {}  # archivo absoluto → ruta virtual en _media/
BROKEN = []

LINK_RE = re.compile(r'(!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\()\s*(<[^>]+>|[^)\s]+)(\s+"[^"]*")?\s*\)')
# Definición de referencia ([x]: url "título"); no las notas al pie ([^1]: texto).
REF_RE = re.compile(r'^(\s{0,3}\[(?!\^)[^\]]+\]:\s*)(\S+)(\s+["\'(].*)?$')
HTML_RE = re.compile(r'''((?:src|href)=)(["'])([^"']+)\2''')
CODE_SPAN_RE = re.compile(r'(`+)(?:.|\n)*?(?<!`)\1(?!`)')


def relative(target, current):
    return posixpath.relpath(target, posixpath.dirname(current) or '.')


def github(path):
    rel = path.relative_to(ROOT).as_posix()
    kind = 'tree' if path.is_dir() else 'blob'
    return '%s/%s/%s/%s' % (REPO_URL, kind, BRANCH, rel)


def media(path):
    if path not in MEDIA:
        MEDIA[path] = '_media/%s' % path.relative_to(ROOT).as_posix()
    return MEDIA[path]


def resolve(url, source, current):
    """URL de ``url`` (escrita en ``source``) vista desde la página ``current``."""
    if url.startswith('<') and url.endswith('>'):
        url = url[1:-1]
    if re.match(r'^([a-z][a-z0-9+.-]*:|#|/|\{)', url, re.I):
        return url
    path_part, sep, fragment = url.partition('#')
    path_part = path_part.split('?')[0]
    if not path_part:
        return url
    target = (source.parent / unquote(path_part)).resolve()
    anchor = sep + fragment
    if target in PAGES:
        return relative(PAGES[target], current) + anchor
    if target in DIRS:
        return relative(DIRS[target], current) + anchor
    try:
        # Imágenes y carpetas de mkdocs/content/: ya están en el sitio.
        slash = '/' if path_part.endswith('/') else ''
        return relative(target.relative_to(CONTENT).as_posix(), current) + slash + anchor
    except ValueError:
        pass
    try:
        target.relative_to(ROOT)
    except ValueError:
        BROKEN.append((source, url))
        return url
    if not target.exists():
        BROKEN.append((source, url))
        return github(target)
    if target.is_file() and target.suffix.lower() in IMAGE_EXT | ATTACH_EXT:
        return relative(media(target), current)
    return github(target)


def rewrite(text, source, current):
    out, fence = [], None
    for line in text.split('\n'):
        stripped = line.lstrip()
        marker = re.match(r'(`{3,}|~{3,})', stripped)
        if fence:
            out.append(line)
            if marker and stripped.startswith(fence) and not stripped[len(fence):].strip():
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            out.append(line)
            continue
        out.append(_rewrite_line(line, source, current))
    return '\n'.join(out)


def _rewrite_line(line, source, current):
    ref = REF_RE.match(line)
    if ref and not ref.group(1).strip().startswith('[//]'):
        return ref.group(1) + resolve(ref.group(2), source, current) + (ref.group(3) or '')
    # Los fragmentos de código se apartan con un marcador: dentro no se
    # reescribe nada, pero pueden ser el texto de un enlace ([`x`](y)).
    spans = []

    def keep(match):
        spans.append(match.group(0))
        return '\x00%d\x00' % (len(spans) - 1)

    line = CODE_SPAN_RE.sub(keep, line)
    line = LINK_RE.sub(lambda m: '%s%s%s)' % (
        m.group(1), resolve(m.group(2), source, current), m.group(3) or ''), line)
    line = HTML_RE.sub(lambda m: '%s%s%s%s' % (
        m.group(1), m.group(2), resolve(m.group(3), source, current), m.group(2)), line)
    return re.sub('\x00(\\d+)\x00', lambda m: spans[int(m.group(1))], line)


def page_from_file(source, current, edit=None, transform=None):
    text = source.read_text(encoding='utf-8')
    if transform:
        text = transform(text)
    write(current, rewrite(text, source, current), edit or source)


def write(current, text, edit=None):
    with mkdocs_gen_files.open(current, 'w') as handle:
        handle.write(text)
    if edit is not None:
        rel = edit.relative_to(ROOT).as_posix() if isinstance(edit, Path) else edit
        mkdocs_gen_files.set_edit_path(current, rel)


# ----------------------------------------------------------------------
# Piezas comunes
# ----------------------------------------------------------------------
def cell(value):
    return clean(value).replace('|', '\\|')


def md_table(rows, head=None):
    if not rows:
        return ''
    head = head or rows[0]
    body = rows if head is not rows[0] else rows[1:]
    width = max(len(head), *(len(row) for row in body)) if body else len(head)
    head = list(head) + [''] * (width - len(head))
    lines = ['| %s |' % ' | '.join(cell(h) for h in head),
             '|%s|' % '|'.join(['---'] * width)]
    for row in body:
        row = list(row) + [''] * (width - len(row))
        lines.append('| %s |' % ' | '.join(cell(c) for c in row))
    return '\n'.join(lines) + '\n'


def paras(text):
    return '\n\n'.join(clean(p) for p in str(text).strip().split('\n\n')) + '\n'


def admonition(kind, text, title=None):
    head = '!!! %s' % kind + (' "%s"' % title if title else '')
    body = '\n'.join(('    ' + line) if line else '' for line in paras(text).split('\n'))
    return '%s\n\n%s\n' % (head, body)


def module_link(name, current):
    module = BY_NAME.get(name)
    if module:
        return '[%s](%s)' % (name, relative('%s/index.md' % module.vdir, current))
    return '`%s`' % name


def strip_title(text):
    """Quita el primer título (atx o setext) del texto."""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith('# '):
            return '\n'.join(lines[i + 1:])
        if i + 1 < len(lines) and re.match(r'=+\s*$', lines[i + 1]):
            return '\n'.join(lines[i + 2:])
        break
    return text


def strip_addons_block(text, marker):
    return re.sub(r'\[//\]: # \(%s\).*?\[//\]: # \(end %s\)\n?' % (marker, marker),
                  '{{ modulos }}\n', text, flags=re.S)


# ----------------------------------------------------------------------
# Ficha del módulo
# ----------------------------------------------------------------------
def module_table(modules, current):
    rows = []
    for module in modules:
        docs = FUNCTIONAL.get(module.name)
        rows.append([
            '[%s](%s)' % (module.title, relative('%s/index.md' % module.vdir, current)),
            '`%s`' % module.name,
            module.version,
            module.manifest.get('license', ''),
            '[:material-book-open-variant:](%s "%s")' % (relative(docs[0][1], current), docs[0][0].replace('"', ''))
            if docs else '',
            module.summary,
        ])
    return md_table(rows, ['Módulo', 'Nombre técnico', 'Versión', 'Licencia', 'Documentación', 'Resumen'])


def ficha_page(module):
    current = '%s/index.md' % module.vdir
    data, manifest = module.ficha, module.manifest
    out = ['---']
    tags = data.get('etiquetas') or []
    if tags:
        out.append('tags:')
        out.extend('  - %s' % yaml.safe_dump(t, allow_unicode=True).splitlines()[0] for t in tags)
    out.append('description: %s' % yaml.safe_dump(module.summary or module.title,
                                                  allow_unicode=True, width=10 ** 6).splitlines()[0])
    out += ['---', '', '# %s' % module.title, '']
    lead = clean(data.get('subtitulo') or '') or module.summary
    if lead:
        out += ['<p class="ol-lead">%s</p>' % lead, '']
    depends = manifest.get('depends') or []
    info = [
        ['Nombre técnico', '`%s`' % module.name],
        ['Versión', '`%s` (Odoo %s)' % (module.version, ODOO_VERSION)],
        ['Licencia', manifest.get('license', '')],
        ['Autor', manifest.get('author', '')],
        ['Área', '[%s](%s)' % (AREA_SITE[module.area][1], relative('%s/%s/index.md' % (REF, AREA_SITE[module.area][0]), current))],
        ['Categoría', data.get('categoria') or manifest.get('category', '')],
        ['Depende de', ', '.join(module_link(d, current) for d in depends) or '—'],
        ['Código', '[%s](%s)' % (module.path.relative_to(ROOT).as_posix(), github(module.path))],
    ]
    if data.get('ediciones'):
        info.insert(6, ['Ediciones', ', '.join(data['ediciones'])])
    out += ['<div class="ol-ficha" markdown>', '', md_table(info, ['Dato', 'Valor']), '</div>', '']
    docs = FUNCTIONAL.get(module.name)
    if docs:
        out.append(admonition('tip', 'Cómo se configura y se usa: ' + ' · '.join(
            '[%s](%s)' % (title, relative(vpath, current)) for title, vpath in docs) + '.',
            'Documentación funcional'))
    pages = MODULE_PAGES.get(module.name)
    if pages:
        out.append('**Referencia técnica:** ' + ' · '.join(
            '[%s](%s)' % (title, relative(vpath, current)) for title, vpath in pages) + '\n')
    if data.get('portada'):
        out += ['![%s](%s)' % (module.title, image(module, data['portada'], current)), '']

    if data.get('contexto'):
        ctx = data['contexto']
        out += ['## %s' % ctx.get('titulo', 'Contexto'), '', paras(ctx.get('texto', ''))]
        if ctx.get('nota'):
            out.append(admonition('note', ctx['nota']))
    if data.get('destacados'):
        out += ['## Lo más importante', '']
        if data.get('destacados_intro'):
            out.append(paras(data['destacados_intro']))
        out += ['<div class="grid cards" markdown>', '']
        for item in data['destacados']:
            out += ['-   <span class="ol-icon">%s</span> **%s**' % (clean(item.get('icono', '')), clean(item['titulo'])),
                    '', '    ---', '', '    %s' % clean(item['texto']), '']
        out += ['</div>', '']
    if data.get('funcionalidades'):
        out += ['## Funcionalidades', '']
        for group in data['funcionalidades']:
            if isinstance(group, str):
                out.append('- %s' % clean(group))
                continue
            out += ['', '### %s' % clean(group['grupo']), '']
            out += ['- %s' % clean(item) for item in group.get('items', [])]
        out.append('')
    if data.get('flujos'):
        out += ['## Flujos del proceso', '']
        if data.get('flujos_intro'):
            out.append(paras(data['flujos_intro']))
        for flow in data['flujos']:
            out += ['### %s' % clean(flow['titulo']), '']
            if flow.get('texto'):
                out.append(paras(flow['texto']))
            out += ['```mermaid', flow['mermaid'].rstrip(), '```', '']
            if flow.get('pie'):
                out += ['*%s*' % clean(flow['pie']), '']
    if data.get('libros'):
        out += ['## %s' % clean(data.get('libros_titulo') or 'Libros'), '']
        if data.get('libros_intro'):
            out.append(paras(data['libros_intro']))
        if data.get('libros_mapa'):
            out.append(md_table(data['libros_mapa']))
        for book in data['libros']:
            out += ['### %s %s' % (clean(book.get('codigo', '')), clean(book['titulo'])), '']
            if book.get('texto'):
                out.append(paras(book['texto']))
            if book.get('ficha'):
                out.append(md_table(book['ficha'], ['Dato', 'Detalle']))
            if book.get('formatos'):
                out += ['**Formatos:** ' + ' · '.join(clean(f) for f in book['formatos']), '']
            if book.get('revisar'):
                out += ['**Qué revisar:**', ''] + ['- %s' % clean(r) for r in book['revisar']] + ['']
            if book.get('nota'):
                out.append(admonition('note', book['nota']))
    if data.get('pasos'):
        out += ['## %s' % clean(data.get('pasos_titulo') or 'Paso a paso'), '']
        if data.get('pasos_intro'):
            out.append(paras(data['pasos_intro']))
        number = 0
        for step in data['pasos']:
            if step.get('seccion'):
                out += ['### %s' % clean(step['seccion']), '']
                continue
            number += 1
            out += ['#### %d. %s' % (number, clean(step.get('titulo', ''))), '']
            if step.get('ruta'):
                out += [':material-menu-open: *%s*' % clean(step['ruta']), '']
            if step.get('texto'):
                out.append(paras(step['texto']))
            out += ['- %s' % clean(p) for p in step.get('puntos') or []]
            if step.get('puntos'):
                out.append('')
            if step.get('imagen'):
                out += ['![%s](%s)' % (cell(step.get('titulo', '')), image(module, step['imagen'], current)), '']
            if step.get('pie'):
                out += ['*%s*' % clean(step['pie']), '']
    if data.get('ejemplos'):
        out += ['## Ejemplos', '']
        if data.get('ejemplos_intro'):
            out.append(paras(data['ejemplos_intro']))
        for example in data['ejemplos']:
            out += ['### %s' % clean(example['titulo']), '']
            if example.get('texto'):
                out.append(paras(example['texto']))
            if example.get('tabla'):
                out.append(md_table(example['tabla']))
            if example.get('codigo'):
                out += ['```text', example['codigo'].rstrip(), '```', '']
            if example.get('nota'):
                out.append(admonition('tip', example['nota']))
    if data.get('asientos'):
        out += ['## Asientos contables', '']
        if data.get('asientos_intro'):
            out.append(paras(data['asientos_intro']))
        for entry in data['asientos']:
            out += ['### %s' % clean(entry['titulo']), '']
            if entry.get('referencia'):
                out += ['*%s*' % clean(entry['referencia']), '']
            if entry.get('texto'):
                out.append(paras(entry['texto']))
            out.append(md_table(entry.get('lineas') or [], ['Cuenta', 'Detalle', 'Debe', 'Haber']))
            if entry.get('nota'):
                out.append(admonition('note', entry['nota']))
    if data.get('campos'):
        out += ['## Referencia de campos', '']
        if data.get('campos_intro'):
            out.append(paras(data['campos_intro']))
        for group in data['campos']:
            out += ['### %s' % clean(group['grupo']), '']
            if group.get('ruta'):
                out += [':material-map-marker: *%s*' % clean(group['ruta']), '']
            if group.get('texto'):
                out.append(paras(group['texto']))
            out.append(md_table(group['campos'], ['Campo', 'Qué hace', 'Por defecto', 'Efecto']))
    if data.get('configuracion'):
        out += ['## Configuración', '']
        if data.get('configuracion_intro'):
            out.append(paras(data['configuracion_intro']))
        out += ['%d. %s' % (i, clean(item)) for i, item in enumerate(data['configuracion'], 1)] + ['']
    if data.get('requisitos_nota'):
        out.append(admonition('info', data['requisitos_nota'], 'Requisitos'))
    if data.get('faq'):
        out += ['## Preguntas frecuentes', '']
        for item in data['faq']:
            out += ['??? question "%s"' % cell(item['pregunta']).replace('"', '&quot;'), '',
                    '    %s' % clean(item['respuesta']), '']
    if data.get('relacionados'):
        out += ['## Módulos relacionados', '']
        out += ['- %s' % module_link(name, current) for name in data['relacionados']] + ['']
    if not data:
        # Sin ficha: la descripción del manifiesto, si no hay README.
        description = manifest.get('description')
        if description and not (module.path / 'README.md').exists():
            out += ['## Descripción', '', '```text', description.strip(), '```', '']
    write(current, '\n'.join(out) + '\n', module.ficha_path or (module.path / '__manifest__.py'))


def image(module, rel, current):
    path = (module.path / 'static' / 'description' / rel).resolve()
    if not path.exists():
        BROKEN.append((module.ficha_path, rel))
        return github(path)
    return relative(media(path), current)


def author_page(module):
    current = '%s/autor.md' % module.vdir
    titles = {
        'DESCRIPTION': 'Descripción', 'CONTEXT': 'Contexto', 'INSTALL': 'Instalación',
        'CONFIGURE': 'Configuración', 'USAGE': 'Uso', 'ROADMAP': 'Pendientes',
        'HISTORY': 'Historial', 'CONTRIBUTORS': 'Colaboradores', 'CREDITS': 'Créditos',
    }
    sequence = list(titles)
    fragments = sorted((module.path / 'readme').glob('*.md'),
                       key=lambda p: sequence.index(p.stem) if p.stem in sequence else 99)
    out = ['# %s: documentación del autor' % module.name, '',
           admonition('info', 'Texto original del autor del módulo (fragmentos `readme/` de OCA), '
                              'sin traducir.')]
    for fragment in fragments:
        body = rewrite(fragment.read_text(encoding='utf-8'), fragment, current)
        body = re.sub(r'^(#{1,5}) ', r'#\1 ', body, flags=re.M)
        out += ['## %s' % titles.get(fragment.stem, fragment.stem.title()), '', body.strip(), '']
    write(current, '\n'.join(out) + '\n', module.path / 'readme')


# ----------------------------------------------------------------------
# Páginas
# ----------------------------------------------------------------------
def area_pages():
    for area in AREAS:
        slug, title, icon = AREA_SITE[area]
        current = '%s/%s/index.md' % (REF, slug)
        source = ROOT / area / 'README.md'
        modules = [m for m in MODULES if m.area == area]
        body = strip_addons_block(strip_title(source.read_text(encoding='utf-8')), 'addons')
        body = rewrite(body, source, current)
        table = module_table(modules, current)
        if '{{ modulos }}' in body:
            body = body.replace('{{ modulos }}', table)
        else:
            body += '\n\n## Módulos disponibles\n\n' + table
        head = '---\nicon: %s\n---\n\n# %s\n\n<p class="ol-lead">Carpeta <code>%s/</code> · %d módulos.</p>\n' % (
            icon, title, area, len(modules))
        write(current, head + body, source)
    rows = []
    for area in AREAS:
        slug, title, _icon = AREA_SITE[area]
        count = sum(1 for m in MODULES if m.area == area)
        rows.append(['[%s](%s/index.md)' % (title, slug), '`%s/`' % area, str(count),
                     first_paragraph(ROOT / area / 'README.md')])
    write('%s/index.md' % REF, '\n'.join([
        '# Referencia de módulos', '',
        'La ficha técnica de cada módulo (manifiesto, dependencias, destacados, flujos, '
        'campos y asientos), su descripción técnica y sus novedades, por carpeta del '
        'repositorio. Cómo se usa cada funcionalidad está en la '
        '[documentación para usuarios](../../applications/index.md).', '',
        md_table(rows, ['Área', 'Carpeta', 'Módulos', 'Contenido']),
    ]) + '\n', ROOT / 'README.md')


def module_pages():
    for module in MODULES:
        ficha_page(module)
        for path, vpath in PAGES.items():
            if vpath.startswith(module.vdir + '/') and path.parent != module.path / 'readme' \
                    and vpath != '%s/index.md' % module.vdir:
                page_from_file(path, vpath)
        if any(t == 'Documentación del autor' for t, _ in MODULE_PAGES[module.name]):
            author_page(module)


def tech_pages():
    for folder in TECH_FOLDERS:
        index = '%s/%s/index.md' % (TECH, folder.name)
        for path, vpath in PAGES.items():
            if vpath.startswith('%s/%s/' % (TECH, folder.name)):
                page_from_file(path, vpath)
        if (folder / 'README.md') not in PAGES:
            lines = ['# %s' % folder.name.capitalize(), '',
                     'Documentos de `docs/%s/`:' % folder.name, '']
            for path, vpath in sorted(PAGES.items(), key=lambda kv: kv[1]):
                if vpath.startswith('%s/%s/' % (TECH, folder.name)):
                    lines.append('- [%s](%s)' % (first_heading(path), relative(vpath, index)))
            write(index, '\n'.join(lines) + '\n', folder)
    root = ROOT / 'README.md'
    page_from_file(root, '%s/repository.md' % DEV,
                   transform=lambda t: strip_addons_block(t, 'addons-all').replace(
                       '{{ modulos }}', 'Ver la tabla de cada área en la referencia de módulos.'))
    lines = ['# Especificaciones y diseño', '',
             'Planes de desarrollo, especificaciones, análisis normativos, validaciones y '
             'herramientas del repositorio (carpeta `docs/`).', '']
    for folder in TECH_FOLDERS:
        lines.append('- [%s](%s/index.md)' % (tech_title(folder), folder.name))
    write('%s/index.md' % TECH, '\n'.join(lines) + '\n', ROOT / 'docs')


def tech_title(folder):
    readme = folder / 'README.md'
    return first_heading(readme) if readme.exists() else folder.name.capitalize()


def news_page():
    entries = []
    for module in MODULES:
        for item in module.ficha.get('novedades') or []:
            day, month, year = str(item['fecha']).split('/')
            entries.append(((year, month, day), item, module))
    entries.sort(key=lambda e: (e[0], e[2].name), reverse=True)
    lines = ['# Novedades de la suite', '',
             'Los cambios más recientes de todos los módulos, desde las `novedades` de cada '
             'ficha. El detalle completo está en la página «Novedades» de cada módulo.', '']
    shown = 0
    last_day = None
    for key, item, module in entries:
        if shown >= 150:
            break
        if key != last_day:
            lines += ['', '## %s' % item['fecha'], '']
            last_day = key
        changes = ' '.join(clean(c) for c in item.get('cambios') or [])
        docs = FUNCTIONAL.get(module.name)
        name = ('[%s](%s)' % (docs[0][0], relative(docs[0][1], NEWS)) if docs
                else module_link(module.name, NEWS))
        lines.append('- **%s** `%s`: %s' % (name, item.get('version', ''), changes))
        shown += 1
    write(NEWS, '\n'.join(lines) + '\n', None)


def template_pages():
    folder = ROOT / 'mkdocs' / 'plantillas'
    cards = []
    for area in AREAS:
        slug, title, icon = AREA_SITE[area]
        modules = [m for m in MODULES if m.area == area]
        summary = first_paragraph(ROOT / area / 'README.md')
        cards += ['-   :%s:{ .lg .middle } **[%s](%s/%s/index.md)**' % (icon.replace('/', '-'), title, REF, slug),
                  '', '    ---', '', '    %s' % summary, '',
                  '    *%d módulos*' % len(modules), '']
    functional = sum(1 for path in CONTENT_PAGES
                     if path.relative_to(CONTENT).parts[0] == 'applications')
    numbers = ('**%d módulos** en %d áreas · **%d páginas** para usuarios · **%d fichas** con '
               'capturas · Odoo **%s**') % (len(MODULES), len(AREAS), functional,
                                           sum(1 for m in MODULES if m.ficha_path), ODOO_VERSION)
    values = {
        '{{ odoo_version }}': ODOO_VERSION,
        '{{ odoo_docs }}': ODOO_DOCS,
        '{{ areas }}': '\n'.join(cards),
        '{{ cifras }}': numbers,
        '{{ repo_url }}': REPO_URL,
        '{{ branch }}': BRANCH,
    }
    for path in sorted(folder.glob('*.md')):
        text = path.read_text(encoding='utf-8')
        for key, value in values.items():
            text = text.replace(key, value)
        write(TEMPLATES.get(path.name, path.name), text, path)


def first_paragraph(readme):
    """Primer párrafo de «Para qué es esta carpeta» del README del área (o,
    si no lo tiene, su lema en negrita)."""
    text = strip_title(readme.read_text(encoding='utf-8')).strip()
    match = re.search(r'Para qué es esta carpeta\n-+\n+(.+?)(\n\n|$)', text, re.S)
    if match:
        return clean(match.group(1))
    match = re.search(r'\*\*(.+?)\*\*', text)
    return clean(match.group(1)) if match else ''


def nav():
    """Menú de las partes generadas; el resto está en los SUMMARY.md de
    mkdocs/content/."""
    def label(text):
        return text.replace('[', '(').replace(']', ')')

    lines = ['* [Referencia de módulos](index.md)']
    for area in AREAS:
        slug, title, _icon = AREA_SITE[area]
        lines.append('* [%s](%s/index.md)' % (title, slug))
        for module in (m for m in MODULES if m.area == area):
            vdir = module.vdir[len(REF) + 1:]
            lines.append('    * [%s](%s/index.md)' % (label(module.title), vdir))
            for title_page, vpath in MODULE_PAGES[module.name]:
                lines.append('        * [%s](%s)' % (label(title_page), vpath[len(REF) + 1:]))
    lines.append('* [Etiquetas](tags.md)')
    with mkdocs_gen_files.open('%s/SUMMARY.md' % REF, 'w') as handle:
        handle.write('\n'.join(lines) + '\n')

    lines = ['* [Especificaciones y diseño](index.md)']
    for folder in TECH_FOLDERS:
        index = '%s/index.md' % folder.name
        lines.append('* [%s](%s)' % (label(tech_title(folder)), index))
        for path, vpath in sorted(PAGES.items(), key=lambda kv: kv[1]):
            if vpath.startswith('%s/%s/' % (TECH, folder.name)) and vpath != '%s/%s' % (TECH, index):
                lines.append('    * [%s](%s)' % (label(first_heading(path)), vpath[len(TECH) + 1:]))
    with mkdocs_gen_files.open('%s/SUMMARY.md' % TECH, 'w') as handle:
        handle.write('\n'.join(lines) + '\n')


def content_pages():
    """Enlaces de las páginas escritas a mano hacia archivos del repositorio
    (ejemplos descargables, código): a _media/ o a GitHub, como en las
    páginas generadas."""
    for path in CONTENT_PAGES:
        if path.name == 'SUMMARY.md':
            continue  # menú de mkdocs-literate-nav: lo lee tal cual
        current = PAGES[path]
        text = path.read_text(encoding='utf-8')
        new = rewrite(text, path, current)
        if new != text:
            write(current, new, path)


def copy_media():
    for path, vpath in MEDIA.items():
        with mkdocs_gen_files.open(vpath, 'wb') as handle:
            handle.write(path.read_bytes())
    logo = ROOT / 'OL-ACCOUNTING' / 'al_account_base' / 'static' / 'description' / 'icon.png'
    with mkdocs_gen_files.open('assets/logo.png', 'wb') as handle:
        handle.write(logo.read_bytes())


template_pages()
area_pages()
module_pages()
tech_pages()
news_page()
content_pages()
nav()
copy_media()

for source, url in BROKEN:
    where = source.relative_to(ROOT) if isinstance(source, Path) else source
    log.warning('Enlace roto en %s: %s', where, url)
