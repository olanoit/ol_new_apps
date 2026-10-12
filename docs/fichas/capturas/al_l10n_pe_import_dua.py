"""Capturas de la ficha de al_l10n_pe_import_dua (datos «DEMO DUA», cargados
con al_l10n_pe_import_dua/tools/import_dua_demo_data.py).

Uso: python3 docs/fichas/capturas/al_l10n_pe_import_dua.py <id DUA> <id costo en destino>
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_import_dua'
FULL = '.o_action_manager'
DUA, LANDED = int(sys.argv[1]), int(sys.argv[2])

with Captura(M) as c:
    # 1. DUA: pestaña DUA con el número de la DAM y la liquidación
    c.abrir_registro('account.move', DUA, ms=2500)
    c.texto('DUA', ms=900)
    c.foto('01-dua', selector=FULL)
    # 2. Líneas generadas: derechos, base imponible con el IGV y su compensación
    c.texto('Líneas de factura', ms=900)
    c.foto('02-lineas', selector=FULL)
    # 3. Costo en destino creado desde la DUA
    c.abrir_registro('stock.landed.cost', LANDED, ms=2500)
    c.foto('03-costo-en-destino', selector=FULL)
    # 4. Ajustes ▸ Perú ▸ Importaciones (DUA)
    c.abrir('/odoo/settings#al_account_base', ms=3000)
    c.page.locator('#al_dua_setting').scroll_into_view_if_needed()
    c.esperar(800)
    box = c.page.locator('#al_dua_setting').bounding_box()
    c.foto('04-ajustes', clip={'x': 0, 'y': max(box['y'] - 60, 0), 'width': 1440, 'height': 260})
