"""Capturas de la ficha de al_account_base (datos «DEMO»).

Uso: ``python al_account_base.py [bloque …]`` (1, 2; sin argumentos, todos)."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

MOVE_GLOSS = 2396       # MISCE/2026/09/0001 · DEMO provisión alquiler setiembre
JOURNAL_OPENING = 1970  # DEMO Asientos de apertura
BANK_ACCOUNT = 165      # cuenta BCP de DEMO Distribuidora Norte SAC
PARTNER = 5363          # DEMO Distribuidora Norte SAC · anexo 0002
COMPANY = 1

BLOQUES = set(sys.argv[1:]) or {'1', '2'}


def recortar_alto(c, name, alto):
    path = c.out / ('%s.png' % name)
    image = Image.open(path)
    image.crop((0, 0, image.width, min(alto, image.height))).save(path, optimize=True)


def error_al_guardar(c, campo, valor, nombre):
    """Escribe un valor inválido, guarda, fotografía el aviso y descarta."""
    entrada = c.page.locator('div[name=%s] input' % campo).first
    entrada.fill(valor)
    c.clic('.o_form_button_save', ms=1800)
    c.foto(nombre, selector='.modal-content')
    c.clic('.modal-footer button', ms=600)
    c.clic('.o_form_button_cancel', ms=900)


with Captura('al_account_base') as c:
    if '1' in BLOQUES:
        # 1. App Perú con el menú Configuración desplegado
        c.abrir_accion('al_account_base.action_pe_settings', ms=2500)
        c.clic('.o_menu_sections button:has-text("Configuración")', ms=900)
        c.foto('01-menu-configuracion', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 690},
               recortar=False)
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

    if '2' in BLOQUES:
        c.page.set_viewport_size({'width': 1300, 'height': 900})

        # 6. Código SUNAT del banco con tres dígitos: rechazado
        c.abrir_registro('res.partner.bank', BANK_ACCOUNT, ms=2000)
        error_al_guardar(c, 'l10n_pe_bank_code', '123', '06-error-banco')

        # 7. Contacto peruano con establecimiento anexo
        c.abrir_registro('res.partner', PARTNER, ms=2000)
        grupo = c.page.locator('.o_inner_group:has(div[name=l10n_pe_annex_code])').first
        grupo.evaluate("e => e.scrollIntoView({block: 'center'})")
        c.esperar(400)
        caja = grupo.bounding_box()
        c.foto('07-contacto-anexo', clip={'x': caja['x'] - 16, 'y': caja['y'] - 12,
                                          'width': caja['width'] + 32,
                                          'height': caja['height'] + 24})

        # 8. Establecimiento anexo con cinco dígitos: rechazado
        error_al_guardar(c, 'l10n_pe_annex_code', '00123', '08-error-anexo')

        # 9. Compañía: página Contabilidad PE, donde los módulos añaden grupos
        c.abrir_registro('res.company', COMPANY, ms=2000)
        c.page.locator('.o_notebook .nav-link:visible:has-text("Contabilidad PE")').first.click()
        c.esperar(900)
        c.foto('09-compania-contabilidad-pe', selector='.o_form_view .o_form_sheet_bg')
