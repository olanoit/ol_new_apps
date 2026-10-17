#!/usr/bin/env python3
"""Genera el mapa de la ayuda contextual (al_docs_help): qué página y qué
sección de la documentación abre el botón «?» de cada pantalla de la suite.

Fuentes, sin escribir nada a mano:

- Las páginas de ``mkdocs/content/applications/`` e ``industries/`` declaran en su
  encabezado los módulos que documentan (``modulos: [...]``).
- Modelos y asistentes que define cada módulo propio (``_name`` con su
  ``_description``) y sus acciones de cliente (``ir.actions.client``, por
  ``tag``): llevan a la página de ese módulo (si hay varias, a la que tenga
  la sección más parecida).
- Pantallas de modelos oficiales que la suite amplía (factura, nómina…):
  ``docs/ayuda/ayuda_contextual.yml`` dice a qué módulo van.
- La sección: el encabezado que más se parece a la descripción del modelo
  o la primera sección que lo cita; si no, el inicio de la página. El ancla
  se calcula como la del sitio (pymdownx slugify, minúsculas).

La ruta es la del sitio MkDocs: ``applications/…/<página>/#<ancla>``.

Uso:
    python3 scripts/gen_docs_help.py           # escribe el XML de datos
    python3 scripts/gen_docs_help.py --check   # falla si está desactualizado
"""
import ast
import re
import sys
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from pymdownx.slugs import slugify

sys.path.insert(0, str(Path(__file__).resolve().parent))
from areas import AREAS, REPO_ROOT, THIRD_PARTY  # noqa: E402

OUTPUT = REPO_ROOT / 'OL-TOOLS' / 'al_docs_help' / 'data' / 'al_docs_help_data.xml'
OVERRIDES = REPO_ROOT / 'docs' / 'ayuda' / 'ayuda_contextual.yml'
CONTENT = REPO_ROOT / 'mkdocs' / 'content'
# Secciones del sitio con páginas para usuarios (las que abre el botón «?»).
USER_SECTIONS = ('applications', 'industries')
SLUG = slugify(case='lower')
MIN_SCORE = 0.6
STOPWORDS = {
    'de', 'del', 'la', 'el', 'los', 'las', 'y', 'o', 'a', 'al', 'en', 'por', 'para',
    'con', 'sin', 'un', 'una', 'unos', 'su', 'sus', 'se', 'que', 'e', 'pe', 'peru',
    'asistente', 'wizard', 'linea', 'lineas',
}


def tokens(text):
    text = unicodedata.normalize('NFKD', text.lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return [t for t in re.findall(r'[a-z0-9]+', text) if t not in STOPWORDS and len(t) > 1]


def similar(a, b):
    """Misma palabra o misma raíz (plurales, género): 5 primeras letras."""
    return a == b or (len(a) > 4 and len(b) > 4 and a[:5] == b[:5])


# Encabezados genéricos (configuración, ejemplos, preguntas): no describen
# una pantalla concreta.
TEMPLATE_HEADINGS = {
    'para que sirve', 'marco normativo y conceptual', 'proceso de inicio a fin',
    'ejemplo completo', 'configuracion inicial', 'reportes y libros relacionados',
    'casos especiales y errores frecuentes', 'preguntas frecuentes del consultor',
    'referencias', 'configuracion', 'conceptos', 'reportes', 'casos especiales',
    'ejemplo', 'ejemplos', 'requisitos', 'ver tambien',
}


def _plain(text):
    text = unicodedata.normalize('NFKD', text.lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9. _-]+', ' ', text)).strip()


def guide_headings(path):
    """Secciones ## y ### de la página (fuera de bloques de código): título,
    ancla y texto propio. Sin los encabezados genéricos."""
    sections, fence, current = [], False, None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.lstrip().startswith(('```', '~~~')):
            fence = not fence
        match = not fence and re.match(r'^(#{2,3})\s+(.+?)\s*#*$', line)
        if match:
            title = match.group(2).strip()
            current = [title, SLUG(title, '-'), []]
            sections.append(current)
        elif current:
            current[2].append(line)
    result = []
    for title, anchor, body in sections:
        bare = re.sub(r'^\d+(\.\d+)*\.?\s*', '', _plain(title)).strip()
        if bare in TEMPLATE_HEADINGS:
            continue
        result.append((title, anchor, '\n'.join(body)))
    return result


def mentioned(key, description, sections):
    """Primera sección que cita el nombre técnico (`modelo`) o la descripción."""
    phrase = _plain(description)
    for title, anchor, body in sections:
        text = _plain(body)
        if key in body or (len(phrase) > 12 and phrase in text):
            return title, anchor
    return None


def best_heading(description, headings, with_score=False):
    words = tokens(description)
    if not words:
        return (None, 0.0) if with_score else None
    best, best_score = None, 0.0
    for title, anchor, _body in headings:
        title_words = tokens(title)
        hits = sum(1 for w in words if any(similar(w, t) for t in title_words))
        score = hits / len(words)
        # Empate: el encabezado más corto (el más específico).
        if score > best_score or (score == best_score and best and len(title) < len(best[0])):
            best, best_score = (title, anchor), score
    found = best if best_score >= MIN_SCORE else None
    return (found, best_score if found else 0.0) if with_score else found


def python_models(module_path):
    """``{modelo: descripción}`` de los modelos que el módulo define (no los
    que solo amplía)."""
    models = {}
    for path in module_path.rglob('*.py'):
        if 'tests' in path.parts or path.name.startswith('__'):
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            attrs = {}
            for item in node.body:
                if isinstance(item, ast.Assign) and len(item.targets) == 1 \
                        and isinstance(item.targets[0], ast.Name):
                    try:
                        attrs[item.targets[0].id] = ast.literal_eval(item.value)
                    except ValueError:
                        pass
            name = attrs.get('_name')
            if not isinstance(name, str):
                continue
            inherit = attrs.get('_inherit')
            inherits = [inherit] if isinstance(inherit, str) else list(inherit or [])
            if name in inherits:
                continue  # ampliación de un modelo existente
            models[name] = attrs.get('_description') or name
    return models


def client_actions(module_path):
    """``{tag: nombre}`` de las acciones de cliente del módulo."""
    actions = {}
    for path in module_path.rglob('*.xml'):
        if 'static' in path.parts:
            continue
        text = path.read_text(encoding='utf-8')
        for record in re.findall(r'<record[^>]*model="ir\.actions\.client"[^>]*>(.*?)</record>',
                                 text, re.S):
            tag = re.search(r'<field name="tag">([^<]+)</field>', record)
            name = re.search(r'<field name="name">([^<]+)</field>', record)
            if tag:
                actions[tag.group(1).strip()] = (name.group(1).strip() if name else tag.group(1))
    return actions


def module_paths():
    """``{módulo: ruta}`` de los módulos propios."""
    paths = {}
    for area in AREAS:
        if area in THIRD_PARTY:
            continue
        for path in sorted((REPO_ROOT / area).iterdir()):
            if (path / '__manifest__.py').exists():
                paths[path.name] = path
    return paths


def doc_pages():
    """``{módulo: [(ruta del sitio, archivo)]}`` desde ``modulos:`` de las
    páginas de usuarios."""
    pages = {}
    for path in sorted(p for section in USER_SECTIONS for p in (CONTENT / section).rglob('*.md')):
        match = re.match(r'---\n(.*?)\n---\n', path.read_text(encoding='utf-8'), re.S)
        meta = (yaml.safe_load(match.group(1)) or {}) if match else {}
        rel = path.relative_to(CONTENT).with_suffix('').as_posix()
        url = rel[:-len('index')] if rel.endswith('/index') or rel == 'index' else rel + '/'
        for module in meta.get('modulos') or []:
            pages.setdefault(module, []).append((url, path))
    return pages


def locate(key, description, candidates):
    """Página y sección para una pantalla entre las páginas de su módulo: el
    título que mejor se parece en cualquiera de ellas; si ninguno, la primera
    sección que la cita; si no, el inicio de la primera página."""
    best, best_score = None, 0.0
    for url, path in candidates:
        # El título de la página (H1, sin ancla) compite con sus secciones.
        sections = [(first_title(path), '', '')] + guide_headings(path)
        heading, score = best_heading(description, sections, with_score=True)
        if heading and score > best_score:
            best, best_score = (url, heading), score
    if best:
        return best
    for url, path in candidates:
        heading = mentioned(key, description, guide_headings(path))
        if heading:
            return url, heading
    # Ninguna sección basta: el inicio de la página que más se le parece
    # (y, en empate, la primera).
    fallback, fallback_score = candidates[0][0], 0.0
    for url, path in candidates:
        score = raw_score(description, [(first_title(path), '', '')] + guide_headings(path))
        if score > fallback_score:
            fallback, fallback_score = url, score
    return fallback, None


def raw_score(description, headings):
    """Mejor parecido de la descripción con los encabezados, sin umbral."""
    words = tokens(description)
    if not words:
        return 0.0
    return max((sum(1 for w in words if any(similar(w, t) for t in tokens(title))) / len(words)
                for title, _anchor, _body in headings), default=0.0)


def build_entries():
    modules = module_paths()
    pages = doc_pages()
    unknown = sorted(set(pages) - set(modules))
    if unknown:
        raise SystemExit('Páginas con módulos que no existen: %s' % ', '.join(unknown))
    entries = {}
    for name, path in modules.items():
        if name not in pages:
            continue
        items = [('model', key, desc) for key, desc in python_models(path).items()]
        items += [('tag', key, desc) for key, desc in client_actions(path).items()]
        for kind, key, desc in items:
            url, heading = locate(key, desc, pages[name])
            entries[key] = {
                'kind': kind, 'module': name, 'name': desc,
                'path': url + ('#' + heading[1] if heading and heading[1] else ''),
                'section': heading[0] if heading else first_title(pages[name][0][1]),
            }
    overrides = yaml.safe_load(OVERRIDES.read_text(encoding='utf-8')) if OVERRIDES.exists() else {}
    for key, spec in (overrides or {}).items():
        module = spec['modulo']
        if module not in pages:
            raise SystemExit('%s: el módulo %s no tiene página en la documentación' % (OVERRIDES, module))
        url, page = pages[module][0]
        heading = None
        if spec.get('seccion'):
            heading = next((h[:2] for h in guide_headings(page) if h[0] == spec['seccion']), None)
            if not heading:
                raise SystemExit('%s: «%s» no es un encabezado de %s'
                                 % (OVERRIDES, spec['seccion'], page.relative_to(REPO_ROOT)))
        entries[key] = {
            'kind': spec.get('tipo', 'model'), 'module': module, 'name': spec.get('nombre', key),
            'path': url + ('#' + heading[1] if heading else ''),
            'section': heading[0] if heading else first_title(page),
        }
    return entries


def first_title(path):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('# '):
            return line[2:].strip()
    return path.stem


def render(entries):
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!-- Generado por scripts/gen_docs_help.py: no editar a mano. Para',
        '     llevar una pantalla a otra guía o sección, use',
        '     docs/ayuda/ayuda_contextual.yml y vuelva a generar. -->',
        '<odoo>',
    ]
    for key in sorted(entries):
        entry = entries[key]
        xmlid = 'help_' + re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_')
        lines += [
            '    <record id="%s" model="al.docs.help">' % xmlid,
            '        <field name="key">%s</field>' % escape(key),
            '        <field name="kind">%s</field>' % entry['kind'],
            '        <field name="name">%s</field>' % escape(entry['name']),
            '        <field name="module">%s</field>' % entry['module'],
            '        <field name="path">%s</field>' % escape(entry['path']),
            '        <field name="section">%s</field>' % escape(entry['section']),
            '    </record>',
        ]
    lines.append('</odoo>')
    return '\n'.join(lines) + '\n'


def main():
    entries = build_entries()
    content = render(entries)
    with_section = sum(1 for e in entries.values() if '#' in e['path'])
    if '--check' in sys.argv:
        current = OUTPUT.read_text(encoding='utf-8') if OUTPUT.exists() else ''
        if current != content:
            raise SystemExit('Desactualizado: %s (python3 scripts/gen_docs_help.py)'
                             % OUTPUT.relative_to(REPO_ROOT))
        print('Ayuda contextual al día: %d pantallas.' % len(entries))
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding='utf-8')
    print('%d pantallas (%d con sección, %d al inicio de la página) → %s' % (
        len(entries), with_section, len(entries) - with_section, OUTPUT.relative_to(REPO_ROOT)))


if __name__ == '__main__':
    main()
