"""Capturas de la ficha de al_l10n_pe_account_letter (datos «DEMO LETRA»).

Base: el guion del módulo ``tools/account_letter_demo_data.py``. Encima, por
odoo shell y solo sobre registros DEMO LETRA:

- Factura DLTV/2026/00004 (S/ 2.360,00) y canje CLC00124 en «Comprobado» con
  dos letras generadas y aún sin número.
- Letra LET-CLI-002 de CLC00088 enviada a descuento (asiento
  LETC/2026/07/0011).
- Refinanciación CLC00091 completada: dos letras nuevas y canjeada (asiento
  LETC/2026/07/0012).

Los asistentes que se capturan aquí se abren y se cierran sin confirmar.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402
from capturar import Captura, ROOT  # noqa: E402

SHOTS = ROOT / 'al_l10n_pe_account_letter' / 'static' / 'description' / 'screenshots'

CANJE_COMPROBADO = 58        # CLC00124, DLTV/2026/00004 en dos letras
CANJE_CLIENTE = 23           # CLC00088, tres letras, cobranza libre y descuento
CANJE_SIMPLE = 27            # CLC00092, una letra pendiente (en canje masivo)
REFIN_BORRADOR = 24          # CLC00089, refinanciación de CLC00088 en borrador
REFIN_CANJEADA = 26          # CLC00091, refinanciación canjeada
CANJE_SIN_LETRAS = 29        # CLC00095, vinculado por referencia
CANJE_MASIVO = 2             # CLC00093 (l10n_pe.letter.massive)
CANJE_PROVEEDOR = 28         # CLP00094
FACTURA_CANJEADA = 913       # DLTV/2026/00002

# Los canjes incluidos en un canje masivo solo se listan en «Historial de canje».
HISTORIAL = 'al_l10n_pe_account_letter.account_letter_action_historial_clientes'

ANCHO = {'width': 2300, 'height': 1100}
NORMAL = {'width': 1440, 'height': 900}


def recortar_alto(nombre, alto):
    path = SHOTS / ('%s.png' % nombre)
    image = Image.open(path)
    if image.size[1] > alto:
        image.crop((0, 0, image.size[0], alto)).save(path, optimize=True)


def ventana(c, size):
    c.page.set_viewport_size(size)
    c.viewport = dict(size)


def pestana(c, texto):
    c.page.locator('.o_notebook .nav-link', has_text=texto).first.click()
    c.esperar(900)


def canje(c, res_id, accion='al_l10n_pe_account_letter.account_letter_action_clientes'):
    c.abrir('/odoo/action-%s/%s' % (accion, res_id), ms=2500)


def seleccionar(c, *nombres):
    for nombre in nombres:
        c.page.locator('.o_data_row', has_text=nombre).first.locator(
            '.o_list_record_selector input').check()
        c.esperar(400)


def blur(c):
    c.js("document.activeElement && document.activeElement.blur()")
    c.esperar(400)


with Captura('al_l10n_pe_account_letter') as c:
    # ---- Configuración ---------------------------------------------------
    # 1. Cuentas contables por tipo de cuenta, tipo de letra y moneda
    c.abrir_accion('al_l10n_pe_account_letter.action_account_configuration', ms=2000)
    c.foto('01-cuentas-letras')
    recortar_alto('01-cuentas-letras', 380)

    # ---- Canje de clientes -----------------------------------------------
    # 2. Lista de canjes de clientes
    c.abrir_accion('al_l10n_pe_account_letter.account_letter_action_clientes', ms=2000)
    c.foto('02-canjes')
    recortar_alto('02-canjes', 460)

    ventana(c, ANCHO)
    # 3. Canje comprobado: facturas
    canje(c, CANJE_COMPROBADO)
    c.foto('03-canje-facturas', selector='.o_form_view .o_form_sheet_bg')

    # 4. Canje comprobado: letras generadas, aún sin número
    pestana(c, 'Letras')
    c.foto('04-crear-letras', selector='.o_form_view .o_form_sheet_bg')

    # 5. Canje canjeado: letras con cobranza libre y descuento
    canje(c, CANJE_CLIENTE)
    pestana(c, 'Letras')
    c.foto('05-canje-letras', selector='.o_form_view .o_form_sheet_bg')

    # 6. Redondeo del canje
    pestana(c, 'Redondeos')
    c.foto('06-redondeo', selector='.o_form_view .o_form_sheet_bg')

    # 7. Apuntes del asiento del canje
    pestana(c, 'Apuntes contables')
    c.foto('07-canje-apuntes', selector='.o_form_view .o_form_sheet_bg')

    # ---- Letras en el banco ----------------------------------------------
    # 8. Asistente de canje por letra (descuento), sin confirmar
    c.clic('.o_form_statusbar button[name=action_canje]', ms=2500)
    # Con una sola letra pendiente el asistente oculta «Tipo de canje».
    tipo = c.page.locator('.modal-dialog div[name=canje_type] .o_selection_badge', has_text='Por letra')
    if tipo.count():
        tipo.first.click()
        c.esperar(700)
    c.page.locator('.modal-dialog div[name=letter_line_id] input').click()
    c.esperar(900)
    c.page.locator('.o-autocomplete--dropdown-item', has_text='LET-CLI-003').first.click()
    c.esperar(700)
    c.page.locator('.modal-dialog div[name=letter_type] .o_selection_badge', has_text='Descuento').first.click()
    c.esperar(500)
    c.page.locator('.modal-dialog div[name=bank_id] input').fill('Credito')
    c.esperar(900)
    c.page.locator('.o-autocomplete--dropdown-item').first.click()
    c.esperar(700)
    c.page.locator('.modal-dialog div[name=code] input').fill('DESC-003')
    blur(c)
    c.foto('08-asistente-canje', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(800)

    ventana(c, NORMAL)
    # 9. Letras de clientes con banco, tipo y estado de pago
    c.abrir_accion('al_l10n_pe_account_letter.account_move_letter_action_clientes', ms=2000)
    c.foto('09-letras')
    recortar_alto('09-letras', 520)

    # 10. Factura canjeada: acceso al canje
    c.abrir('/odoo/action-account.action_move_out_invoice_type/%s' % FACTURA_CANJEADA, ms=2500)
    c.foto('10-factura-canjeada', selector='.o_form_view .o_form_sheet_bg')

    # 11. Facturas de cliente con la columna opcional «Estado de canje»
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
    c.foto('11-facturas-canjeadas', clip={'x': 0, 'y': 46, 'width': 1440, 'height': 300})

    # ---- Refinanciación ---------------------------------------------------
    # 12. Asistente Refinanciar (individual), sin confirmar
    canje(c, CANJE_SIMPLE, HISTORIAL)
    c.clic('.o_form_statusbar button:has-text("Refinanciar")', ms=2000)
    blur(c)
    c.foto('12-refinanciar', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(800)

    ventana(c, ANCHO)
    # 13. Refinanciación en borrador: lo adeudado como documento «Letra»
    canje(c, REFIN_BORRADOR)
    c.foto('13-refinanciacion-borrador', selector='.o_form_view .o_form_sheet_bg')

    # 14. Refinanciación canjeada: apuntes que cierran la letra de origen
    canje(c, REFIN_CANJEADA)
    pestana(c, 'Apuntes contables')
    c.foto('14-refinanciacion-apuntes', selector='.o_form_view .o_form_sheet_bg')
    ventana(c, NORMAL)

    # 15. Refinanciación masiva desde la lista (sin confirmar)
    c.abrir_accion('al_l10n_pe_account_letter.account_letter_action_clientes', ms=2000)
    seleccionar(c, 'CLC00095', 'CLC00124')
    c.clic('.o_cp_action_menus button:has(.fa-cog)', ms=800)
    c.page.locator('.o-dropdown-item', has_text='Refinanciación masiva de canjes').first.click()
    c.esperar(2000)
    blur(c)
    c.foto('15-refinanciacion-masiva', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(800)

    # ---- Canje masivo ----------------------------------------------------
    # 16. Botón «Método»: tipo de letra del canje masivo (sin confirmar)
    c.abrir_accion('al_l10n_pe_account_letter.account_letter_action_clientes', ms=2000)
    seleccionar(c, 'CLC00088', 'CLC00091')
    c.clic('.o_control_panel button:has-text("Método")', ms=1500)
    c.foto('16-metodo', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(800)

    # 17. Canje masivo consolidado
    ventana(c, ANCHO)
    c.abrir('/odoo/action-al_l10n_pe_account_letter.account_massive_letter_action_clientes/%s'
            % CANJE_MASIVO, ms=2500)
    pestana(c, 'Letras')
    c.foto('17-canje-masivo', selector='.o_form_view .o_form_sheet_bg')
    ventana(c, NORMAL)

    # 18. Historial: canjes incluidos en un canje masivo
    c.abrir_accion('al_l10n_pe_account_letter.account_letter_action_historial_clientes', ms=2000)
    c.foto('18-historial')
    recortar_alto('18-historial', 300)

    # ---- Proveedores -----------------------------------------------------
    # 19. Canje de proveedor: apuntes del asiento
    ventana(c, ANCHO)
    canje(c, CANJE_PROVEEDOR, 'al_l10n_pe_account_letter.account_letter_action_proveedores')
    pestana(c, 'Apuntes contables')
    c.foto('19-canje-proveedor', selector='.o_form_view .o_form_sheet_bg')
