"""Capturas de la ficha de al_account_destinations (datos «DEMO»).

La compañía de demostración trabaja con el sentido 9→6, así que la cuenta de
ejemplo es de clase 9 («DEMO Gastos por distribuir (9)»)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

ACCOUNT = 156844      # 941200 DEMO Gastos por distribuir (9)
ORIGIN = 2404         # F F001-00000877 · factura de DEMO Distribuidora Norte SAC
DESTINY = 2405        # GA/2026/09/0002

with Captura('al_account_destinations') as c:
    # 1. Ajustes ▸ Perú: sentido de la dinámica
    c.abrir_accion('al_account_base.action_pe_settings', ms=2500)
    c.page.mouse.move(1438, 898)
    c.page.wait_for_timeout(300)
    c.page.screenshot(path=str(c.out / '01-ajustes.png'),
                      clip={'x': 0, 'y': 0, 'width': 1440, 'height': 300})
    print('captura 01-ajustes')

    # Formularios más anchos: con 1300 px el chatter va debajo de la hoja.
    c.page.set_viewport_size({'width': 1300, 'height': 900})

    # 2. Cuenta con su configuración de destinos
    c.abrir_registro('account.account', ACCOUNT, ms=2000)
    c.texto('Configuración de destinos', ms=900)
    c.foto('02-cuenta-destinos', selector='.o_form_view .o_form_sheet_bg')

    # 3. Vista consolidada de destinos por cuenta
    c.abrir_accion('al_account_destinations.account_account_destiny_action', ms=2000)
    c.page.locator('.o_group_header').first.click()
    c.esperar(500)
    for header in c.page.locator('.o_group_header').all()[1:]:
        header.click()
        c.esperar(400)
    c.foto('03-destinos-por-cuenta')

    # 4. Comprobante de origen publicado, con el enlace al asiento de destino
    c.abrir_registro('account.move', ORIGIN, ms=2000)
    c.page.locator('.o_notebook .nav-link:visible:has-text("Otra información")').first.click()
    c.esperar(900)
    c.page.locator('.o_form_sheet .o_notebook_headers').first.evaluate(
        "e => e.scrollIntoView({block: 'start'})")
    c.esperar(600)
    c.page.mouse.move(1298, 898)
    c.page.wait_for_timeout(300)
    c.page.screenshot(path=str(c.out / '04-origen.png'),
                      clip={'x': 0, 'y': 0, 'width': 1300, 'height': 786})
    print('captura 04-origen')

    # 5. Asiento de destino generado en el diario GA
    c.abrir_registro('account.move', DESTINY, ms=2000)
    c.foto('05-asiento-destino', selector='.o_form_view .o_form_sheet_bg')
