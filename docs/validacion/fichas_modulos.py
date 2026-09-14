#!/usr/bin/env python3
"""Normaliza las fichas ``static/description/index.html`` de los módulos.

Uso (desde la raíz del repositorio; es idempotente)::

    python3 docs/validacion/fichas_modulos.py          # corrige
    python3 docs/validacion/fichas_modulos.py --check  # solo informa

Tres arreglos:

1. **Caracteres en español.** Las fichas son fragmentos HTML sin
   ``<meta charset>``: abiertas directamente (archivo local, vista previa del
   IDE) el navegador las lee como Windows-1252 y «ó» sale como «Ã³». El meta no
   se puede añadir porque vacía la ficha en Aplicaciones (lxml lo mueve a un
   ``<head>`` y ``html_sanitize`` devuelve cadena vacía). Se convierten los
   caracteres no ASCII a referencias numéricas (``&#243;``), que se leen igual
   con cualquier codificación; dentro de ``<style>`` se usan escapes CSS.

2. **Enlace a la ficha completa.** En Aplicaciones, Odoo sanea la ficha y
   descarta el ``<style>``: se ve el texto sin diseño. Se añade al principio un
   enlace a ``/<módulo>/static/description/index.html``, que Odoo sirve con
   ``charset=utf-8`` y con el diseño completo. La regla que lo oculta vive en
   el propio ``<style>``: en la página completa no se ve (ya se está en ella) y
   en Aplicaciones, donde el estilo desaparece, sí.

3. **Pie de la ficha.** Versión y licencia se toman del ``__manifest__.py``.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINK_CLASS = 'al-ficha-link'
LINK_CSS = '.%s { display: none; }' % LINK_CLASS
LINK_HTML = (
    '<p class="%s" style="margin:0 0 16px;padding:10px 14px;'
    'border:1px solid #cfe8e5;border-radius:6px;background:#edf7f6;">'
    '<a href="/{module}/static/description/index.html" target="_blank" '
    'rel="noopener"><strong>Ver la ficha completa del m&#243;dulo</strong></a>'
    ' &#8212; abre esta descripci&#243;n con su dise&#241;o en una pesta&#241;a'
    ' nueva.</p>' % LINK_CLASS
)
BLOCK_RE = re.compile(r'(<style\b[^>]*>)(.*?)(</style>)', re.S | re.I)


def to_entities(text):
    return ''.join(c if ord(c) < 128 else '&#%d;' % ord(c) for c in text)


def to_css_escapes(text):
    return ''.join(c if ord(c) < 128 else '\\%X ' % ord(c) for c in text)


def encode(html):
    """Entidades fuera de ``<style>``; escapes CSS dentro."""
    out, pos = [], 0
    for match in BLOCK_RE.finditer(html):
        out.append(to_entities(html[pos:match.start()]))
        out.append(match.group(1) + to_css_escapes(match.group(2))
                   + match.group(3))
        pos = match.end()
    out.append(to_entities(html[pos:]))
    return ''.join(out)


def add_link(html, module):
    if LINK_CLASS in html:
        return html
    link = LINK_HTML.format(module=module)
    style_end = re.search(r'</style>', html, re.I)
    body = re.search(r'<body\b[^>]*>', html, re.I)
    if body:
        # Documento completo: la regla va en su <head>, el enlace tras <body>.
        head_end = re.search(r'</head>', html, re.I)
        html = (html[:head_end.start()] + '<style>%s</style>\n' % LINK_CSS
                + html[head_end.start():])
        body = re.search(r'<body\b[^>]*>', html, re.I)
        return html[:body.end()] + '\n' + link + html[body.end():]
    if style_end:
        html = (html[:style_end.start()] + LINK_CSS + '\n'
                + html[style_end.start():])
        style_end = re.search(r'</style>', html, re.I)
        return (html[:style_end.end()] + '\n\n' + link
                + html[style_end.end():])
    # Fragmento sin estilos: nada que ocultar, el enlace va al principio.
    first_tag = re.search(r'<[a-zA-Z][^>]*>', html)
    return html[:first_tag.end()] + '\n' + link + html[first_tag.end():]


def sync_footer(html, module, manifest):
    version = manifest.get('version', '')
    license_ = manifest.get('license', '')
    return re.sub(
        r'(<strong>%s</strong> &#183; versi&#243;n )[^<&]*( &#183; )[^<]*(</p>)'
        % re.escape(module),
        lambda m: '%s%s%s%s%s' % (m.group(1), version, m.group(2), license_,
                                  m.group(3)),
        html)


def main(check=False):
    changed = 0
    for index in sorted(ROOT.glob('*/static/description/index.html')):
        module = index.parts[-4]
        manifest_path = ROOT / module / '__manifest__.py'
        manifest = ast.literal_eval(manifest_path.read_text()) \
            if manifest_path.exists() else {}
        original = index.read_text(encoding='utf-8')
        fixed = sync_footer(add_link(encode(original), module), module,
                            manifest)
        if fixed != original:
            changed += 1
            print('%s %s' % ('pendiente' if check else 'corregido', module))
            if not check:
                index.write_text(fixed, encoding='utf-8')
    print('%d fichas %s' % (changed, 'por corregir' if check else 'corregidas'))
    return 1 if check and changed else 0


if __name__ == '__main__':
    sys.exit(main(check='--check' in sys.argv))
