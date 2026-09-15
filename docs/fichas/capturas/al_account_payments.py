"""Capturas de la ficha de al_account_payments (datos «DEMO PAGO»)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402
from PIL import Image

BILL_OPEN = 2402        # F F001-00004588, DEMO PAGO Proveedor SAC, sin pagar
PAYMENT = 177           # PBNK1/2026/00002: transferencia, operación 00458721

with Captura('al_account_payments') as c:
    # 1. Catálogo de medios de pago con todas sus columnas
    c.abrir_accion('al_account_payments.action_pe_catalog_payment_form', ms=2000)
    c.clic('.o_list_renderer .o_optional_columns_dropdown button', ms=500)
    for label in ('Código de facturador', 'Para detracción'):
        box = c.page.locator('.o-dropdown--menu .dropdown-item:has-text("%s") input' % label).first
        if not box.is_checked():
            box.click()
            c.esperar(500)
    c.page.keyboard.press('Escape')
    c.esperar(500)
    c.foto('01-catalogo')

    # 2. Medio de pago válido para detracción
    c.abrir_accion('al_account_payments.action_pe_catalog_payment_form', ms=2000)
    c.page.locator('.o_data_row:has-text("TRANSFERENCIA DE FONDOS")').first.locator('td.o_data_cell').first.click()
    c.esperar(1500)
    c.foto('02-medio-pago', selector='.o_form_view .o_form_sheet_bg')
    ruta = c.out / '02-medio-pago.png'
    imagen = Image.open(ruta)
    imagen.crop((0, 0, imagen.width, 132)).save(ruta, optimize=True)

    # 3. Asistente de pago con medio de pago y número de operación
    c.abrir_registro('account.move', BILL_OPEN, ms=2000)
    c.clic('.o_form_statusbar button:has-text("Pagar")', ms=2500)
    modal = c.page.locator('.modal-content')
    modal.locator('div[name=pe_payment_method_id] input').fill('003')
    c.esperar(900)
    c.page.locator('.o-autocomplete--dropdown-menu li:has-text("TRANSFERENCIA")').first.click()
    c.esperar(500)
    modal.locator('div[name=bank_operation_number] input').fill('00461390')
    c.esperar(300)
    modal.locator('.modal-title').click()
    c.esperar(500)
    c.foto('03-asistente-pago', selector='.modal-content')
    c.clic('.modal-header .btn-close', ms=800)

    # 4. Pago creado: los datos pasan del asistente al pago
    c.abrir_registro('account.payment', PAYMENT, ms=2000)
    c.foto('04-pago', selector='.o_form_view .o_form_sheet_bg')
