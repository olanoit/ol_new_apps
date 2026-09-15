"""Capturas de la ficha de al_l10n_pe_account_letter (datos «DEMO LETRA»).

Los asistentes (canje) se abren y se cierran sin confirmar."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402
from capturar import Captura, ROOT  # noqa: E402

SHOTS = ROOT / 'al_l10n_pe_account_letter' / 'static' / 'description' / 'screenshots'


def recortar_alto(nombre, alto):
    path = SHOTS / ('%s.png' % nombre)
    image = Image.open(path)
    if image.size[1] > alto:
        image.crop((0, 0, image.size[0], alto)).save(path, optimize=True)


def pestana(c, texto):
    c.page.locator('.o_notebook .nav-link', has_text=texto).first.click()
    c.esperar(900)


with Captura('al_l10n_pe_account_letter') as c:
    # 1. Cuentas contables por tipo de cuenta, tipo de letra y moneda
    c.abrir_accion('al_l10n_pe_account_letter.action_account_configuration', ms=2000)
    c.foto('01-cuentas-letras')
    recortar_alto('01-cuentas-letras', 380)

    # 2. Canjes de clientes
    c.abrir_accion('al_l10n_pe_account_letter.account_letter_action_clientes', ms=2000)
    c.foto('02-canjes')
    recortar_alto('02-canjes', 380)

    # Formularios con más columnas: ventana más ancha
    c.page.set_viewport_size({'width': 2300, 'height': 1100})
    c.viewport = {'width': 2300, 'height': 1100}

    # 3. Canje CLC00088: facturas canjeadas
    c.abrir_registro('l10n_pe.letter', 23, ms=2500)
    c.foto('03-canje-facturas', selector='.o_form_view .o_form_sheet_bg')

    # 4. Pestaña Letras: tres letras generadas a 30 días
    pestana(c, 'Letras')
    c.foto('04-canje-letras', selector='.o_form_view .o_form_sheet_bg')

    # 5. Pestaña Apuntes contables del asiento de canje
    pestana(c, 'Apuntes contables')
    c.foto('05-canje-apuntes', selector='.o_form_view .o_form_sheet_bg')

    # 6. Asistente de canje (cobranza libre o descuento), sin confirmar
    c.clic('.o_form_statusbar button[name=action_canje]', ms=2500)
    c.js('() => document.activeElement.blur()')
    c.esperar(400)
    c.foto('06-asistente-canje', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(800)

    # 7. Letras de clientes con su estado de pago
    c.page.set_viewport_size({'width': 1440, 'height': 900})
    c.viewport = {'width': 1440, 'height': 900}
    c.abrir_accion('al_l10n_pe_account_letter.account_move_letter_action_clientes',
                   ms=2000)
    c.foto('07-letras')
    recortar_alto('07-letras', 360)

    # 8. Facturas de cliente con la columna opcional «Estado de canje»
    c.abrir_accion('account.action_move_out_invoice_type', ms=2500)
    c.page.locator('.o_searchview_input').fill('DEMO LETRA')
    c.esperar(700)
    c.page.keyboard.press('Enter')
    c.esperar(1800)
    c.clic('.o_optional_columns_dropdown_toggle', ms=700)
    casilla = c.page.locator('.o-dropdown-item:has-text("Estado de canje") input')
    if not casilla.is_checked():
        casilla.click()
        c.esperar(1200)
    c.clic('.o_optional_columns_dropdown_toggle', ms=700)
    c.foto('08-facturas-canjeadas')
    recortar_alto('08-facturas-canjeadas', 330)
