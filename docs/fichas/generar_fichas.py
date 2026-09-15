#!/usr/bin/env python3
"""Genera las fichas ``static/description/index.html`` desde ``docs/fichas/*.yml``.

Uso (desde la raíz del repositorio, con el Python del entorno de Odoo)::

    python docs/fichas/generar_fichas.py                 # todas
    python docs/fichas/generar_fichas.py al_l10n_pe_ple  # una o varias
    python docs/fichas/generar_fichas.py --check         # ¿están al día?

Por qué un generador y no HTML a mano:

* **Aplicaciones descarta ``<style>``** al sanear la descripción, pero conserva
  los estilos en línea (grid, degradados, sombras), ``<img>``, tablas y
  ``<details>``. La ficha solo se ve bien en los dos sitios —Aplicaciones y la
  página completa— si todo el diseño va en línea, y eso a mano es inmantenible.
* El contenido de cada módulo vive en un YAML legible; el diseño, en un solo
  sitio. Cambiar el aspecto de las 31 fichas es volver a ejecutar esto.
* Versión, licencia, dependencias y módulos relacionados salen del manifest,
  así que no se desfasan.

Después se aplica ``docs/validacion/fichas_modulos.py`` (ASCII puro, enlace a
la ficha completa, pie sincronizado). Esquema del YAML: ``docs/fichas/README.md``.
"""
import ast
import html
import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'docs' / 'fichas'

_spec = importlib.util.spec_from_file_location(
    'fichas_modulos', ROOT / 'docs' / 'validacion' / 'fichas_modulos.py')
fichas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fichas)

# ----------------------------------------------------------------------
# Paleta y tipografía (misma identidad que las fichas anteriores)
# ----------------------------------------------------------------------
INK = '#1c2024'
MUTED = '#5b6570'
LINE = '#e2e5e9'
SOFT = '#f7f8fa'
BRAND = '#b45309'
BRAND_SOFT = '#fef6ec'
ACCENT = '#0f766e'
ACCENT_SOFT = '#edf7f6'
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',"
        "Arial,sans-serif")
MONO = 'ui-monospace,SFMono-Regular,Menlo,Consolas,monospace'

WRAP = 'max-width:1120px;margin:0 auto;padding:0 24px;'
CARD = ('background:#fff;border:1px solid %s;border-radius:12px;'
        'padding:22px;box-shadow:0 1px 2px rgba(16,24,40,.04);' % LINE)
H2 = ('font-size:28px;line-height:1.25;font-weight:800;color:%s;'
      'margin:0 0 8px;letter-spacing:-.01em;' % INK)
SUB = 'font-size:16px;color:%s;margin:0 0 28px;max-width:760px;' % MUTED
EYEBROW = ('display:inline-block;font-size:12px;letter-spacing:.14em;'
           'text-transform:uppercase;font-weight:700;color:%s;margin:0 0 10px;'
           % BRAND)
PILL = ('display:inline-block;font-size:12.5px;font-weight:600;'
        'padding:5px 12px;border-radius:999px;margin:0 6px 6px 0;')

EDITIONS = {
    'community': ('Community', ACCENT),
    'enterprise': ('Enterprise', '#714b67'),
}

# Módulos de Enterprise: si el módulo depende de alguno, no es Community.
ENTERPRISE_DEPENDS = {
    'account_accountant', 'account_asset', 'account_reports', 'hr_payroll',
    'hr_payroll_account', 'l10n_pe_reports', 'l10n_pe_reports_lib',
    'l10n_pe_reports_stock', 'project_enterprise', 'web_enterprise',
    'hr_payroll_holidays', 'documents', 'sign', 'planning', 'web_gantt',
}


class FichaError(Exception):
    pass


def esc(text):
    if isinstance(text, bool) or text is None:
        # YAML 1.1 lee No/Sí/On/Off/Yes sin comillas como booleanos, y una
        # celda vacía como nula: en la ficha saldría «False» o «None».
        raise FichaError(
            'valor %r donde se esperaba texto: ponga la celda entre comillas '
            '(p. ej. "No")' % (text,))
    return html.escape(str(text), quote=True)


def rich(text):
    """Texto con marcado mínimo: ``**negrita**``, ```código``` y saltos de
    párrafo con línea en blanco. El resto se escapa."""
    esc(text)  # rechaza booleanos y nulos antes de convertir a texto
    out = []
    for para in str(text).strip().split('\n\n'):
        chunk = esc(' '.join(para.split()))
        parts = chunk.split('**')
        chunk = ''.join(p if i % 2 == 0 else '<strong>%s</strong>' % p
                        for i, p in enumerate(parts))
        parts = chunk.split('`')
        chunk = ''.join(
            p if i % 2 == 0 else
            '<code style="font-family:%s;font-size:.9em;background:%s;'
            'border:1px solid %s;border-radius:4px;padding:1px 5px;">%s</code>'
            % (MONO, SOFT, LINE, p)
            for i, p in enumerate(parts))
        out.append(chunk)
    return out


def paragraphs(text, style=''):
    return ''.join('<p style="margin:0 0 12px;%s">%s</p>' % (style, p)
                   for p in rich(text))


def inline(text):
    return '<br/>'.join(rich(text))


# Donde buscar el manifest de las dependencias (nombre legible en la ficha).
ADDONS_PATHS = [ROOT] + [
    ROOT.parents[1] / sub for sub in ('addons', 'ee19', 'odoo/addons')]


def manifest_of(module):
    for base in ADDONS_PATHS:
        path = base / module / '__manifest__.py'
        if path.exists():
            return ast.literal_eval(path.read_text())
    return {}


def shorten(text, limit=150):
    text = ' '.join(str(text).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0].rstrip(',;:.') + '…'


ENTERPRISE_PATH = ROOT.parents[1] / 'ee19'


def needs_enterprise(module, _seen=None):
    """True si el módulo depende, directa o indirectamente, de Enterprise."""
    seen = _seen if _seen is not None else set()
    if module in seen:
        return False
    seen.add(module)
    if module in ENTERPRISE_DEPENDS or (ENTERPRISE_PATH / module).is_dir():
        return True
    return any(needs_enterprise(dep, seen)
               for dep in manifest_of(module).get('depends', []))


def figure(src, alt, margin_top=18, border=LINE,
           shadow='0 12px 32px rgba(16,24,40,.10)'):
    """Captura a su tamaño natural, centrada y como mucho al ancho de la página.

    Con ``width:100%`` un diálogo de 650 px se ampliaba a 1070 px y salía
    borroso; ``max-width`` solo reduce las anchas."""
    return ('<div style="margin-top:%dpx;text-align:center;">'
            '<div style="display:inline-block;max-width:100%%;border-radius:12px;'
            'overflow:hidden;border:1px solid %s;box-shadow:%s;vertical-align:top;">'
            '<img src="%s" alt="%s" style="display:block;max-width:100%%;height:auto;"/>'
            '</div></div>' % (margin_top, border, shadow, esc(src), esc(alt)))


# ----------------------------------------------------------------------
# Secciones
# ----------------------------------------------------------------------
def section(inner, alt=False, anchor=None):
    return ('<section%s style="padding:56px 0;background:%s;%s">'
            '<div style="%s">%s</div></section>\n'
            % (' id="%s"' % anchor if anchor else '',
               SOFT if alt else '#fff',
               'border-top:1px solid %s;border-bottom:1px solid %s;' % (LINE, LINE)
               if alt else '', WRAP, inner))


def heading(title, subtitle=None, eyebrow=None):
    return ((('<p style="%s">%s</p>' % (EYEBROW, esc(eyebrow))) if eyebrow else '')
            + '<h2 style="%s">%s</h2>' % (H2, esc(title))
            + ('<p style="%s">%s</p>' % (SUB, inline(subtitle)) if subtitle else ''))


def render_topbar(data, manifest, module):
    editions = data.get('ediciones') or (
        ['enterprise'] if needs_enterprise(module)
        else ['community', 'enterprise'])
    badges = ''.join(
        '<span style="%sbackground:%s;color:#fff;">%s</span>'
        % (PILL, EDITIONS[e][1], EDITIONS[e][0]) for e in editions)
    avail = ''.join(
        '<span style="%sbackground:#fff;color:%s;border:1px solid %s;">'
        '&#10003; %s</span>' % (PILL, INK, LINE, name)
        for name in ('On premise', 'Odoo.sh'))
    return (
        '<div style="background:#fff;border-bottom:1px solid %s;">'
        '<div style="%sdisplay:flex;flex-wrap:wrap;align-items:center;'
        'justify-content:space-between;gap:12px;padding-top:14px;padding-bottom:8px;">'
        '<div style="font-weight:800;font-size:18px;color:%s;margin-bottom:6px;">'
        'Alta<span style="color:%s;">BPO</span>'
        '<span style="font-weight:500;font-size:13px;color:%s;margin-left:10px;">'
        'Odoo 19 &#183; %s</span></div>'
        '<div><span style="font-size:12.5px;font-weight:700;color:%s;margin-right:8px;">'
        'Ediciones</span>%s<span style="font-size:12.5px;font-weight:700;color:%s;'
        'margin:0 8px 0 10px;">Despliegue</span>%s</div>'
        '</div></div>\n'
        % (LINE, WRAP, INK, BRAND, MUTED, esc(module), MUTED, badges, MUTED, avail))


def render_hero(data, manifest):
    tags = ''.join(
        '<span style="%sbackground:rgba(255,255,255,.1);color:#e6e9ec;'
        'border:1px solid rgba(255,255,255,.18);">%s</span>' % (PILL, esc(t))
        for t in data.get('etiquetas', []))
    email = (manifest.get('author', '').split('<')[-1].rstrip('>')
             if '<' in manifest.get('author', '') else '')
    website = manifest.get('website', '')
    buttons = ''
    if email:
        buttons += ('<a href="mailto:%s" style="display:inline-block;background:%s;'
                    'color:#fff;font-weight:700;font-size:14px;text-decoration:none;'
                    'padding:11px 22px;border-radius:999px;margin:0 8px 8px 0;">'
                    '&#9993; Escríbenos</a>' % (esc(email), BRAND))
    if website:
        buttons += ('<a href="%s" target="_blank" rel="noopener" style="display:inline-block;'
                    'background:transparent;color:#fff;font-weight:700;font-size:14px;'
                    'text-decoration:none;padding:10px 22px;border-radius:999px;'
                    'border:1px solid rgba(255,255,255,.4);margin:0 8px 8px 0;">'
                    'Sitio web</a>' % esc(website))
    image = ''
    if data.get('portada'):
        image = figure(data['portada'], data['titulo'], margin_top=34,
                       border='rgba(255,255,255,.15)',
                       shadow='0 20px 50px rgba(0,0,0,.35)')
    return (
        '<header style="background:linear-gradient(160deg,#1c2024 0%%,#2c3138 55%%,'
        '#3a3128 100%%);color:#fff;padding:60px 0 52px;">'
        '<div style="%s">'
        '<p style="%scolor:#fbbf24;">%s</p>'
        '<h1 style="font-size:42px;line-height:1.12;font-weight:800;margin:0 0 16px;'
        'letter-spacing:-.02em;color:#fff;">%s</h1>'
        '<p style="font-size:18px;color:#c9ced5;max-width:720px;margin:0 0 24px;">%s</p>'
        '<div style="margin:0 0 18px;">%s</div><div>%s</div>%s'
        '</div></header>\n'
        % (WRAP, EYEBROW, esc(data.get('categoria', 'Odoo 19')), esc(data['titulo']),
           inline(data['subtitulo']), tags, buttons, image))


def render_highlights(data):
    items = data.get('destacados') or []
    if not items:
        return ''
    cards = ''.join(
        '<div style="%s">'
        '<div style="width:44px;height:44px;border-radius:10px;background:%s;color:#fff;'
        'display:flex;align-items:center;justify-content:center;font-size:20px;'
        'font-weight:800;margin-bottom:14px;">%s</div>'
        '<h3 style="font-size:17px;font-weight:700;color:%s;margin:0 0 8px;">%s</h3>'
        '<p style="font-size:14.5px;color:%s;margin:0;line-height:1.55;">%s</p></div>'
        % (CARD, ACCENT if i % 2 == 0 else BRAND, esc(item.get('icono', i + 1)),
           INK, esc(item['titulo']), MUTED, inline(item['texto']))
        for i, item in enumerate(items))
    return section(
        heading('Aspectos destacados', data.get('destacados_intro'), 'Resumen')
        + '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
          'minmax(250px,1fr));gap:18px;">%s</div>' % cards)


def render_problem(data):
    if not data.get('contexto'):
        return ''
    ctx = data['contexto']
    return section(
        heading(ctx.get('titulo', 'Por qué este módulo'), None, 'Contexto')
        + '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
          'minmax(300px,1fr));gap:28px;align-items:start;">'
          '<div style="font-size:16px;color:%s;line-height:1.65;">%s</div>'
          '<div style="background:%s;border-left:4px solid %s;border-radius:0 10px 10px 0;'
          'padding:18px 22px;font-size:15px;color:%s;line-height:1.6;">%s</div></div>'
        % (INK, paragraphs(ctx['texto']), BRAND_SOFT, BRAND, INK,
           paragraphs(ctx.get('nota', ''))), alt=True)


def render_steps(data):
    steps = data.get('pasos') or []
    if not steps:
        return ''
    out = ''
    for i, step in enumerate(steps, start=1):
        route = ('<div style="display:inline-block;font-size:13px;font-weight:600;'
                 'color:%s;background:%s;border:1px solid #cfe8e5;border-radius:6px;'
                 'padding:4px 10px;margin:0 0 12px;">&#128205; %s</div>'
                 % (ACCENT, ACCENT_SOFT, esc(step['ruta']))) if step.get('ruta') else ''
        image = ''
        if step.get('imagen'):
            image = figure(step['imagen'], step['titulo'])
            if step.get('pie'):
                image += ('<p style="font-size:13px;color:%s;text-align:center;'
                          'margin:10px 0 0;">%s</p>' % (MUTED, inline(step['pie'])))
        tips = ''.join(
            '<li style="margin:0 0 6px;">%s</li>' % inline(t)
            for t in step.get('puntos', []))
        if tips:
            tips = ('<ul style="margin:6px 0 0;padding-left:20px;font-size:15px;'
                    'color:%s;line-height:1.6;">%s</ul>' % (INK, tips))
        out += (
            '<div style="display:flex;gap:18px;margin:0 0 44px;">'
            '<div style="flex:0 0 38px;height:38px;border-radius:50%%;background:%s;'
            'color:#fff;font-weight:800;display:flex;align-items:center;'
            'justify-content:center;font-size:16px;">%d</div>'
            '<div style="flex:1;min-width:0;">'
            '<h3 style="font-size:21px;font-weight:700;color:%s;margin:4px 0 10px;">%s</h3>'
            '%s<div style="font-size:15.5px;color:%s;line-height:1.65;">%s</div>%s%s'
            '</div></div>'
            % (INK, i, INK, esc(step['titulo']), route, INK,
               paragraphs(step.get('texto', '')), tips, image))
    return section(heading(data.get('pasos_titulo', 'Paso a paso'),
                           data.get('pasos_intro'), 'Capturas') + out,
                   anchor='capturas')


def render_features(data):
    groups = data.get('funcionalidades') or []
    if not groups:
        return ''
    if groups and isinstance(groups[0], str):
        groups = [{'grupo': None, 'items': groups}]
    cols = ''
    for group in groups:
        items = ''.join(
            '<li style="display:flex;gap:10px;margin:0 0 10px;font-size:15px;'
            'color:%s;line-height:1.5;"><span style="color:%s;font-weight:800;">'
            '&#10003;</span><span>%s</span></li>' % (INK, ACCENT, inline(item))
            for item in group['items'])
        title = ('<h3 style="font-size:16px;font-weight:700;color:%s;margin:0 0 14px;">%s</h3>'
                 % (INK, esc(group['grupo']))) if group.get('grupo') else ''
        cols += ('<div style="%s">%s<ul style="list-style:none;margin:0;padding:0;">'
                 '%s</ul></div>' % (CARD, title, items))
    return section(
        heading('Funcionalidades', data.get('funcionalidades_intro'), 'Qué incluye')
        + '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
          'minmax(300px,1fr));gap:18px;">%s</div>' % cols, alt=True)


def render_examples(data):
    examples = data.get('ejemplos') or []
    if not examples:
        return ''
    out = ''
    for ex in examples:
        body = paragraphs(ex.get('texto', ''))
        if ex.get('tabla'):
            head, *rows = ex['tabla']
            for row in rows:
                if len(row) != len(head):
                    raise FichaError(
                        'tabla «%s»: la fila %r tiene %d celdas y la cabecera %d '
                        '(¿una celda con coma sin comillas?)'
                        % (ex['titulo'], row, len(row), len(head)))
            th = ''.join(
                '<th style="text-align:left;padding:10px 12px;background:%s;color:#fff;'
                'font-size:13px;font-weight:700;white-space:nowrap;">%s</th>'
                % (INK, esc(c)) for c in head)
            trs = ''.join(
                '<tr>%s</tr>' % ''.join(
                    '<td style="padding:9px 12px;border-bottom:1px solid %s;font-size:14px;'
                    'color:%s;background:%s;">%s</td>'
                    % (LINE, INK, '#fff' if r % 2 == 0 else SOFT, inline(c)) for c in row)
                for r, row in enumerate(rows))
            body += ('<div style="overflow-x:auto;border:1px solid %s;border-radius:10px;'
                     'margin:6px 0 14px;"><table style="width:100%%;border-collapse:collapse;">'
                     '<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                     % (LINE, th, trs))
        if ex.get('codigo'):
            body += ('<pre style="background:%s;color:#e6e9ec;padding:16px 18px;'
                     'border-radius:10px;overflow-x:auto;font-family:%s;font-size:13px;'
                     'line-height:1.6;margin:6px 0 14px;white-space:pre;">%s</pre>'
                     % (INK, MONO, esc(ex['codigo'].rstrip())))
        if ex.get('nota'):
            body += ('<div style="background:%s;border-left:4px solid %s;'
                     'border-radius:0 8px 8px 0;padding:12px 16px;font-size:14.5px;'
                     'color:%s;">%s</div>' % (BRAND_SOFT, BRAND, INK, inline(ex['nota'])))
        out += ('<div style="%smargin:0 0 22px;"><h3 style="font-size:19px;font-weight:700;'
                'color:%s;margin:0 0 12px;">%s</h3><div style="font-size:15.5px;color:%s;'
                'line-height:1.65;">%s</div></div>' % (CARD, INK, esc(ex['titulo']), INK, body))
    return section(heading('Ejemplos prácticos', data.get('ejemplos_intro'), 'Casos')
                   + out)


def render_setup(data, manifest):
    steps = data.get('configuracion') or []
    depends = manifest.get('depends', [])
    names = []
    for dep in depends:
        dep_manifest = manifest_of(dep)
        label = dep_manifest.get('name')
        names.append('<code style="font-family:%s;font-size:13px;background:%s;'
                     'border:1px solid %s;border-radius:4px;padding:2px 6px;'
                     'margin:0 6px 6px 0;display:inline-block;">%s</code>%s'
                     % (MONO, SOFT, LINE, esc(dep),
                        (' <span style="color:%s;font-size:13px;">%s</span>'
                         % (MUTED, esc(label))) if label else ''))
    deps = ('<div style="%s"><h3 style="font-size:16px;font-weight:700;color:%s;'
            'margin:0 0 12px;">Dependencias</h3><div style="line-height:2;">%s</div>'
            '%s</div>'
            % (CARD, INK, '<br/>'.join(names) or 'Ninguna',
               ('<p style="font-size:14px;color:%s;margin:12px 0 0;">%s</p>'
                % (MUTED, inline(data['requisitos_nota'])))
               if data.get('requisitos_nota') else ''))
    items = ''.join(
        '<li style="margin:0 0 12px;padding-left:4px;">%s</li>' % inline(s)
        for s in steps)
    setup = ('<div style="%s"><h3 style="font-size:16px;font-weight:700;color:%s;'
             'margin:0 0 12px;">Puesta en marcha</h3><ol style="margin:0;padding-left:22px;'
             'font-size:15px;color:%s;line-height:1.6;">%s</ol></div>'
             % (CARD, INK, INK, items)) if items else ''
    return section(
        heading('Instalación y configuración', data.get('configuracion_intro'), 'Empezar')
        + '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
          'minmax(320px,1fr));gap:18px;align-items:start;">%s%s</div>' % (setup, deps),
        alt=True)


def render_faq(data):
    faq = data.get('faq') or []
    if not faq:
        return ''
    items = ''.join(
        '<details style="background:#fff;border:1px solid %s;border-radius:10px;'
        'padding:14px 18px;margin:0 0 10px;"><summary style="cursor:pointer;'
        'font-weight:700;font-size:16px;color:%s;">%s</summary>'
        '<div style="font-size:15px;color:%s;line-height:1.65;margin-top:10px;">%s</div>'
        '</details>' % (LINE, INK, esc(q['pregunta']), INK, paragraphs(q['respuesta']))
        for q in faq)
    return section(heading('Preguntas frecuentes', None, 'Dudas') + items)


def render_releases(data, manifest):
    releases = data.get('novedades') or []
    if not releases:
        return ''
    items = ''
    for i, rel in enumerate(releases):
        changes = ''.join('<li style="margin:0 0 6px;">%s</li>' % inline(c)
                          for c in rel['cambios'])
        version = rel.get('version') or (manifest.get('version') if i == 0 else '')
        items += (
            '<div style="display:flex;gap:18px;margin:0 0 18px;">'
            '<div style="flex:0 0 120px;"><div style="font-weight:800;color:%s;'
            'font-size:15px;">%s</div><div style="font-size:13px;color:%s;">%s</div></div>'
            '<div style="flex:1;%s"><ul style="margin:0;padding-left:18px;font-size:15px;'
            'color:%s;line-height:1.6;">%s</ul></div></div>'
            % (BRAND if i == 0 else INK, esc(version), MUTED, esc(rel.get('fecha', '')),
               CARD, INK, changes))
    return section(heading('Novedades', None, 'Historial') + items, alt=True)


def render_related(data):
    related = data.get('relacionados') or []
    if not related:
        return ''
    cards = ''
    for module in related:
        manifest = manifest_of(module)
        if not manifest:
            continue
        icon = ''
        if (ROOT / module / 'static' / 'description' / 'icon.png').exists():
            icon = ('<img src="/%s/static/description/icon.png" alt="" style="width:40px;'
                    'height:40px;border-radius:8px;margin-bottom:10px;"/>' % module)
        cards += (
            '<a href="/%s/static/description/index.html" target="_blank" rel="noopener" '
            'style="%sdisplay:block;text-decoration:none;">%s'
            '<div style="font-size:15.5px;font-weight:700;color:%s;margin:0 0 6px;">%s</div>'
            '<div style="font-size:13.5px;color:%s;line-height:1.5;">%s</div></a>'
            % (module, CARD, icon, INK, esc(manifest.get('name', module)), MUTED,
               esc(shorten(manifest.get('summary', '')))))
    return section(heading('Módulos relacionados', None, 'Suite AltaBPO')
                   + '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
                     'minmax(240px,1fr));gap:18px;">%s</div>' % cards)


def render_footer(data, manifest, module):
    return (
        '<footer style="background:%s;color:#9aa4ae;padding:34px 0;font-size:13.5px;">'
        '<div style="%s">'
        '<p style="margin:0 0 6px"><strong>%s</strong> · versión %s · %s</p>'
        '<p style="margin:0">%s</p></div></footer>\n'
        % (INK, WRAP, esc(module), esc(manifest.get('version', '')),
           esc(manifest.get('license', '')),
           inline(data.get('pie', 'Desarrollado por AltaBPO para Odoo 19.'))))


def render(module, data):
    manifest = manifest_of(module)
    body = (render_topbar(data, manifest, module)
            + render_hero(data, manifest)
            + render_highlights(data)
            + render_problem(data)
            + render_steps(data)
            + render_features(data)
            + render_examples(data)
            + render_setup(data, manifest)
            + render_faq(data)
            + render_releases(data, manifest)
            + render_related(data)
            + render_footer(data, manifest, module))
    return (
        '<!DOCTYPE html>\n<html lang="es">\n<head>\n'
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        '<title>%s</title>\n</head>\n'
        '<body style="margin:0;font-family:%s;color:%s;background:#fff;line-height:1.55;">\n'
        '%s</body>\n</html>\n' % (esc(data['titulo']), FONT, INK, body))


def build(module, check=False):
    source = SRC / ('%s.yml' % module)
    data = yaml.safe_load(source.read_text(encoding='utf-8'))
    manifest = manifest_of(module)
    target = ROOT / module / 'static' / 'description' / 'index.html'
    content = render(module, data)
    content = fichas.sync_footer(
        fichas.add_link(fichas.encode(content), module), module, manifest)
    missing = [
        img for img in _images(data)
        if not (ROOT / module / 'static' / 'description' / img).exists()]
    if missing:
        raise SystemExit('%s: faltan imágenes %s' % (module, missing))
    current = target.read_text(encoding='utf-8') if target.exists() else ''
    if content == current:
        return False
    if not check:
        target.write_text(content, encoding='utf-8')
    return True


def _images(data):
    images = [data['portada']] if data.get('portada') else []
    images += [s['imagen'] for s in data.get('pasos', []) if s.get('imagen')]
    return images


def main(argv):
    check = '--check' in argv
    modules = [a for a in argv if not a.startswith('--')] or sorted(
        p.stem for p in SRC.glob('*.yml'))
    changed = []
    for module in modules:
        try:
            if build(module, check=check):
                changed.append(module)
        except (FichaError, yaml.YAMLError) as error:
            raise SystemExit('%s: %s' % (module, error))
    for module in changed:
        print('%s %s' % ('desfasada' if check else 'generada', module))
    print('%d de %d fichas %s' % (len(changed), len(modules),
                                  'desfasadas' if check else 'generadas'))
    return 1 if check and changed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
