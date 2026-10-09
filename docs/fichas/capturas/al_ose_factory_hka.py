"""Capturas de la ficha de al_ose_factory_hka. Elige el operador en pantalla
sin guardar: la base de demostración sigue con su operador."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

# El bloque de Ajustes no lleva id en el DOM: es su título más el contenedor
# que le sigue. Devuelve la caja que abarca a los dos.
BLOCK_BOX = """(title) => {
    const h = [...document.querySelectorAll('h2')].find(e => e.textContent.trim() == title);
    h.scrollIntoView({block: 'start'});
    const a = h.getBoundingClientRect(), b = h.nextElementSibling.getBoundingClientRect();
    return {x: a.x, y: a.y, width: Math.max(a.width, b.width), height: b.bottom - a.y};
}"""

with Captura('al_ose_factory_hka', viewport={'width': 1440, 'height': 1500}) as c:
    # 1. Ajustes ▸ Facturación electrónica peruana con The Factory HKA
    c.abrir('/odoo/settings#account', ms=2500)
    c.page.evaluate(BLOCK_BOX, 'Facturación electrónica peruana')
    c.page.locator('input[id$=_factory_hka][type=radio]').first.check()
    c.esperar(800)
    c.page.locator('[name=l10n_pe_edi_factory_hka_username] input').first.fill('20512345678HKA')
    c.esperar(400)
    box = c.page.evaluate(BLOCK_BOX, 'Facturación electrónica peruana')
    c.esperar(400)
    c.foto('01-ajustes', clip={'x': box['x'], 'y': box['y'] - 8, 'width': box['width'],
                               'height': box['height'] + 16})
