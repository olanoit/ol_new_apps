#!/usr/bin/env python3
"""Fotografía una ficha generada para revisarla a ojo.

    python docs/fichas/revisar.py <módulo> <carpeta_salida>

Deja en la carpeta ``<módulo>_completa_N.png`` (la página completa por tramos
de 1600 px, reducidos a la mitad) y ``<módulo>_aplicaciones.png`` (la ficha
dentro del formulario del módulo en Aplicaciones, que es la versión saneada).
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capturar import URL, Captura  # noqa: E402


def main(module, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    full = out / ('%s_completa.png' % module)
    with Captura(module) as c:
        c.abrir('/%s/static/description/index.html' % module, ms=1500)
        c.page.screenshot(path=str(full), full_page=True)
        module_id = c.page.evaluate(
            """async (name) => {
                const r = await fetch('/web/dataset/call_kw', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                        model: 'ir.module.module', method: 'search',
                        args: [[['name', '=', name]]], kwargs: {}}})});
                return (await r.json()).result[0];
            }""", module)
        c.abrir('/odoo/action-base.open_module_tree/%s' % module_id, ms=2500)
        c.page.screenshot(path=str(out / ('%s_aplicaciones.png' % module)))
    image = Image.open(full)
    width, height = image.size
    parts = 0
    for top in range(0, height, 1600):
        bottom = min(height, top + 1600)
        image.crop((0, top, width, bottom)).resize(
            (width // 2, (bottom - top) // 2)).save(
                out / ('%s_completa_%d.png' % (module, parts)))
        parts += 1
    full.unlink()
    print('%s: %d tramos de la página completa + vista en Aplicaciones en %s'
          % (module, parts, out))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
