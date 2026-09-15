"""Capturas de la ficha de al_account_destinations (datos «DEMO»).

La compañía de demostración trabaja con el sentido 9→6, así que las cuentas de
ejemplo son de clase 9 («DEMO Gastos por distribuir (9)» y «DEMO Gastos
compartidos (9)»).

Uso: ``python al_account_destinations.py [bloque …]`` (1, 2, 3; sin argumentos,
todos)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

COMPANY = 1
ACCOUNT = 156844      # 941200 DEMO Gastos por distribuir (9): 60 % / 40 %
ACCOUNT_3 = 156845    # 941300 DEMO Gastos compartidos (9): 3 × 33,3333 %
ENTRY = 2397          # MISCE/2026/09/0002 · DEMO destinos servicios setiembre
ENTRY_DEST = 2398     # GA/2026/09/0001
INVOICE = 2404        # F F001-00000877 · factura de DEMO Distribuidora Norte SAC
INVOICE_DEST = 2405   # GA/2026/09/0002
ROUNDING_DEST = 2424  # GA/2026/09/0003 · destino de «DEMO destinos redondeo»
NO_DEST = 2425        # borrador «DEMO destinos sin configurar» (cuenta 942100)
DRAFT_DEST = 2427     # GA/2026/09/0004 · vuelto a borrador con su origen

BLOQUES = set(sys.argv[1:]) or {'1', '2', '3'}


def pestaña(c, texto):
    c.page.locator('.o_notebook .nav-link:visible:has-text("%s")' % texto).first.click()
    c.esperar(800)


with Captura('al_account_destinations') as c:
    if '1' in BLOQUES:
        # 1. Ajustes ▸ Perú: sentido de la dinámica
        c.abrir_accion('al_account_base.action_pe_settings', ms=2500)
        c.foto('01-ajustes', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 300})

        # Formularios más anchos: con 1300 px el chatter va debajo de la hoja.
        c.page.set_viewport_size({'width': 1300, 'height': 900})

        # 2. Ficha de la compañía ▸ Contabilidad PE ▸ Destinos
        c.abrir_registro('res.company', COMPANY, ms=2000)
        pestaña(c, 'Contabilidad PE')
        grupo = c.page.locator('.o_inner_group:has(div[name=l10n_pe_dest_type])').first
        caja = grupo.bounding_box()
        c.foto('02-compania', clip={'x': caja['x'] - 16, 'y': caja['y'] - 12,
                                    'width': 640, 'height': caja['height'] + 24})

        # 3. Cuenta con su configuración de destinos
        c.abrir_registro('account.account', ACCOUNT, ms=2000)
        pestaña(c, 'Configuración de destinos')
        c.foto('03-cuenta-destinos', selector='.o_form_view .o_form_sheet_bg')

        # 5. Plan contable con la columna opcional «Incluye destino»
        c.abrir_accion('account.action_account_form', ms=2000)
        buscar = c.page.locator('.o_searchview_input').first
        buscar.fill('9')
        buscar.press('Enter')
        c.esperar(1200)
        c.clic('.o_list_renderer .o_optional_columns_dropdown button', ms=500)
        caja = c.page.locator('.o-dropdown--menu .dropdown-item:has-text("Incluye destino") input').first
        if not caja.is_checked():
            caja.click()
            c.esperar(700)
        c.page.keyboard.press('Escape')
        c.esperar(500)
        c.foto('05-plan-contable')

        # 6. Vista consolidada de destinos por cuenta
        c.abrir_accion('al_account_destinations.account_account_destiny_action', ms=2000)
        for header in c.page.locator('.o_group_header').all():
            header.click()
            c.esperar(500)
        c.foto('06-destinos-por-cuenta')

    if '2' in BLOQUES:
        c.page.set_viewport_size({'width': 1300, 'height': 900})

        # 4. La suma de porcentajes debe ser 100 %
        c.abrir_registro('account.account', ACCOUNT, ms=2000)
        pestaña(c, 'Configuración de destinos')
        c.page.locator('.o_field_one2many .o_data_row').first.locator(
            'td[name=percentage]').click()
        c.esperar(500)
        campo = c.page.locator('.o_field_one2many .o_data_row input').last
        campo.fill('50')
        c.clic('.o_form_button_save', ms=1800)
        c.foto('04-error-porcentaje', selector='.modal-content')
        c.clic('.modal-footer button', ms=600)
        c.clic('.o_form_button_cancel', ms=900)

        # 7. Asiento de origen con cuenta de clase 9
        c.abrir_registro('account.move', ENTRY, ms=2000)
        c.foto('07-asiento-origen', selector='.o_form_view .o_form_sheet_bg')

        # 8. Asiento de destino del asiento anterior
        c.abrir_registro('account.move', ENTRY_DEST, ms=2000)
        c.foto('08-asiento-destino', selector='.o_form_view .o_form_sheet_bg')

        # 9. Factura de proveedor con el enlace al asiento de destino
        c.abrir_registro('account.move', INVOICE, ms=2000)
        pestaña(c, 'Otra información')
        c.page.locator('.o_form_sheet .o_notebook_headers').first.evaluate(
            "e => e.scrollIntoView({block: 'start'})")
        c.esperar(600)
        c.foto('09-factura-origen', clip={'x': 0, 'y': 0, 'width': 1300, 'height': 786})

        # 10. Asiento de destino de la factura
        c.abrir_registro('account.move', INVOICE_DEST, ms=2000)
        c.foto('10-factura-destino', selector='.o_form_view .o_form_sheet_bg')

    if '3' in BLOQUES:
        c.page.set_viewport_size({'width': 1300, 'height': 900})

        # 11. Cuenta con tres destinos al 33,3333 % y su asiento redondeado
        c.abrir_registro('account.account', ACCOUNT_3, ms=2000)
        pestaña(c, 'Configuración de destinos')
        c.foto('11-cuenta-tres-destinos', selector='.o_form_view .o_form_sheet_bg')
        c.abrir_registro('account.move', ROUNDING_DEST, ms=2000)
        c.foto('12-asiento-redondeo', selector='.o_form_view .o_form_sheet_bg')

        # 13. Cuenta de la clase de origen sin destinos: no deja publicar
        c.abrir_registro('account.move', NO_DEST, ms=2000)
        c.clic('.o_form_statusbar button[name=action_post]', ms=2000)
        c.foto('13-error-sin-destinos', selector='.modal-content')
        c.clic('.modal-footer button', ms=600)

        # 14. Origen vuelto a borrador: el destino también
        c.abrir_registro('account.move', DRAFT_DEST, ms=2000)
        c.foto('14-destino-borrador', selector='.o_form_view .o_form_sheet_bg')
