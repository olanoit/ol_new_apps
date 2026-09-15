"""Capturas de la ficha de al_account_base (datos «DEMO»)."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

MOVE_GLOSS = 2396       # MISCE/2026/09/0001 · DEMO provisión alquiler setiembre
JOURNAL_OPENING = 1970  # DEMO Asientos de apertura
BANK_ACCOUNT = 165      # cuenta BCP de DEMO Distribuidora Norte SAC


def recortar_alto(c, name, alto):
    path = c.out / ('%s.png' % name)
    image = Image.open(path)
    image.crop((0, 0, image.width, min(alto, image.height))).save(path, optimize=True)


with Captura('al_account_base') as c:
    # 1. App Perú con el menú Configuración desplegado
    c.abrir_accion('al_account_base.action_pe_settings', ms=2500)
    c.clic('.o_menu_sections button:has-text("Configuración")', ms=900)
    c.page.mouse.move(1438, 898)
    c.page.wait_for_timeout(300)
    c.page.screenshot(path=str(c.out / '01-menu-configuracion.png'),
                      clip={'x': 0, 'y': 0, 'width': 1440, 'height': 690})
    print('captura 01-menu-configuracion')
    c.page.keyboard.press('Escape')

    # 2. Ajustes ▸ Perú: contenedor de los ajustes de la localización
    c.abrir_accion('al_account_base.action_pe_settings', ms=2500)
    c.foto('02-ajustes-peru')

    # Formularios más anchos: con 1300 px el chatter va debajo de la hoja.
    c.page.set_viewport_size({'width': 1300, 'height': 900})

    # 3. Asiento con glosa en la cabecera y en las líneas
    c.abrir_registro('account.move', MOVE_GLOSS, ms=2000)
    c.page.locator('.o_field_one2many .o_optional_columns_dropdown button').first.click()
    c.esperar(500)
    item = c.page.locator('.o-dropdown--menu .dropdown-item:has-text("Glosa") input')
    if not item.first.is_checked():
        item.first.click()
        c.esperar(600)
    c.page.keyboard.press('Escape')
    c.page.locator('.o_form_sheet .oe_title').first.click()
    c.esperar(400)
    c.foto('03-asiento-glosa', selector='.o_form_view .o_form_sheet_bg')

    # 4. Diario con naturaleza y exclusión de los libros electrónicos
    c.abrir_registro('account.journal', JOURNAL_OPENING, ms=2000)
    c.foto('04-diario', selector='.o_form_view .o_form_sheet_bg')
    recortar_alto(c, '04-diario', 276)

    # 5. Cuenta bancaria con código SUNAT del banco
    c.abrir_registro('res.partner.bank', BANK_ACCOUNT, ms=2000)
    c.foto('05-cuenta-bancaria', selector='.o_form_view .o_form_sheet_bg')
    recortar_alto(c, '05-cuenta-bancaria', 350)
