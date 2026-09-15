#!/usr/bin/env python3
"""Dibuja los diagramas de flujo de una ficha (Mermaid → PNG).

    python docs/fichas/diagramas.py <módulo> [<módulo> …]

Lee ``flujos`` de ``docs/fichas/<módulo>.yml`` y deja, por cada uno,
``<módulo>/static/description/diagramas/<id>.png`` y ``<id>.mmd`` (el texto
con el que se dibujó: el generador lo compara con el YAML y avisa si el
diagrama quedó desfasado).

Por qué imagen y no HTML: Aplicaciones descarta ``<svg>`` y ``<script>`` al
sanear la ficha, así que un diagrama con decisiones y ramas solo sobrevive como
PNG. Se dibuja con Mermaid en Chrome (Playwright); necesita acceso a
cdn.jsdelivr.net.
"""
import json
import sys
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CHROME = '/usr/bin/google-chrome'
MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js'

# Misma paleta que generar_fichas.py
THEME = {
    'fontFamily': "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif",
    'fontSize': '15px',
    'primaryColor': '#edf7f6',
    'primaryBorderColor': '#0f766e',
    'primaryTextColor': '#1c2024',
    'secondaryColor': '#fef6ec',
    'secondaryBorderColor': '#b45309',
    'tertiaryColor': '#f7f8fa',
    'tertiaryBorderColor': '#e2e5e9',
    'lineColor': '#5b6570',
    'clusterBkg': '#f7f8fa',
    'clusterBorder': '#e2e5e9',
    'edgeLabelBackground': '#ffffff',
}

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>body{margin:0;background:#fff;} #d{display:inline-block;padding:24px;}</style>
</head><body><div id="d"></div>
<script src="%s"></script>
<script>
  mermaid.initialize({startOnLoad: false, theme: 'base', themeVariables: %s,
                      flowchart: {curve: 'basis', padding: 14, htmlLabels: true, useMaxWidth: false},
                      sequence: {useMaxWidth: false}});
  window.dibujar = async (texto) => {
    const {svg} = await mermaid.render('g', texto);
    document.getElementById('d').innerHTML = svg;
    return true;
  };
</script></body></html>"""


def draw(module):
    data = yaml.safe_load((ROOT / 'docs' / 'fichas' / ('%s.yml' % module)).read_text())
    flows = data.get('flujos') or []
    if not flows:
        print('%s: sin flujos' % module)
        return
    out = ROOT / module / 'static' / 'description' / 'diagramas'
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
        # Ventana ancha y SVG a tamaño natural (useMaxWidth: false): si no,
        # Mermaid encoge los diagramas horizontales hasta hacerlos ilegibles.
        page = browser.new_page(viewport={'width': 2400, 'height': 1200},
                                device_scale_factor=1.5)
        page.set_content(PAGE % (MERMAID, json.dumps(THEME)))
        page.wait_for_function('window.mermaid !== undefined', timeout=30000)
        for flow in flows:
            page.evaluate('texto => window.dibujar(texto)', flow['mermaid'])
            page.wait_for_timeout(300)
            page.locator('#d').screenshot(path=str(out / ('%s.png' % flow['id'])))
            (out / ('%s.mmd' % flow['id'])).write_text(flow['mermaid'], encoding='utf-8')
            print('diagrama', (out / ('%s.png' % flow['id'])).relative_to(ROOT))
        browser.close()


if __name__ == '__main__':
    for name in sys.argv[1:]:
        draw(name)
