"""Capturas de la ficha de al_account_payments (datos «DEMO PAGO»).

Uso: ``python al_account_payments.py [bloque …]`` (1, 2, 3; sin argumentos,
todos)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402
from PIL import Image

BILL_OPEN = 2402        # F F001-00004588, DEMO PAGO Proveedor SAC, sin pagar
BILL_OPEN_2 = 2437      # F F001-00004610, DEMO PAGO Proveedor SAC, sin pagar
PAYMENT = 177           # PBNK1/2026/00002: transferencia, operación 00458721
PAYMENT_MOVE = 2403
GROUPED = 182           # PBNK1/2026/00006: F001-00004620 + F001-00004621, depósito
GROUPED_MOVE = 2440

BLOQUES = set(sys.argv[1:]) or {'1', '2', '3'}


def medio_y_operacion(c, modal, busqueda, opcion, operacion):
    modal.locator('div[name=pe_payment_method_id] input').fill(busqueda)
    c.esperar(900)
    c.page.locator('.o-autocomplete--dropdown-menu li:has-text("%s")' % opcion).first.click()
    c.esperar(500)
    modal.locator('div[name=bank_operation_number] input').fill(operacion)
    c.esperar(300)
    modal.locator('.modal-title').click()
    c.esperar(500)


def apuntes(c, move_id, nombre):
    c.abrir_registro('account.move', move_id, ms=2000)
    c.foto(nombre, selector='.o_form_view .o_form_sheet_bg')


with Captura('al_account_payments') as c:
    if '1' in BLOQUES:
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

    if '2' in BLOQUES:
        # 3. Búsqueda del medio por descripción en el asistente
        c.abrir_registro('account.move', BILL_OPEN, ms=2000)
        c.clic('.o_form_statusbar button:has-text("Pagar")', ms=2500)
        modal = c.page.locator('.modal-content')
        modal.locator('div[name=pe_payment_method_id] input').fill('transf')
        c.esperar(1200)
        caja = modal.bounding_box()
        menu = c.page.locator('.o-autocomplete--dropdown-menu').first.bounding_box()
        alto = max(caja['y'] + caja['height'], menu['y'] + menu['height']) - caja['y']
        ancho = max(caja['x'] + caja['width'], menu['x'] + menu['width'] + 12) - caja['x']
        c.foto('03-buscar-medio', clip={'x': caja['x'], 'y': caja['y'],
                                        'width': ancho, 'height': alto})

        # 4. Asistente de pago con medio de pago y número de operación
        c.page.locator('.o-autocomplete--dropdown-menu li:has-text("TRANSFERENCIA")').first.click()
        c.esperar(500)
        modal.locator('div[name=bank_operation_number] input').fill('00461390')
        modal.locator('.modal-title').click()
        c.esperar(500)
        c.foto('04-asistente-pago', selector='.modal-content')
        c.clic('.modal-header .btn-close', ms=800)

        # 5. Pago creado: los datos pasan del asistente al pago
        c.page.set_viewport_size({'width': 1300, 'height': 900})
        c.abrir_registro('account.payment', PAYMENT, ms=2000)
        c.foto('05-pago', selector='.o_form_view .o_form_sheet_bg')

        # 6. Asiento del pago
        apuntes(c, PAYMENT_MOVE, '06-asiento-pago')

    if '3' in BLOQUES:
        # 7. Dos facturas del mismo proveedor, pagadas en un pago agrupado
        c.abrir_accion('account.action_move_in_invoice_type', ms=2000)
        buscar = c.page.locator('.o_searchview_input').first
        buscar.fill('DEMO PAGO')
        buscar.press('Enter')
        c.esperar(1500)
        for numero in ('F001-00004588', 'F001-00004610'):
            c.page.locator('.o_data_row:has-text("%s") .o_list_record_selector' % numero).first.click()
            c.esperar(400)
        c.clic('.o_control_panel button:has-text("Pagar")', ms=2500)
        modal = c.page.locator('.modal-content')
        agrupar = modal.locator('div[name=group_payment] input').first
        if not agrupar.is_checked():
            agrupar.click()
            c.esperar(900)
        medio_y_operacion(c, modal, '001', 'DEPÓSITO', '00471300')
        c.foto('07-asistente-agrupado', selector='.modal-content')
        c.clic('.modal-header .btn-close', ms=800)

        # 8. Pago agrupado real y su asiento
        c.page.set_viewport_size({'width': 1300, 'height': 900})
        c.abrir_registro('account.payment', GROUPED, ms=2000)
        c.foto('08-pago-agrupado', selector='.o_form_view .o_form_sheet_bg')
        apuntes(c, GROUPED_MOVE, '09-asiento-agrupado')
