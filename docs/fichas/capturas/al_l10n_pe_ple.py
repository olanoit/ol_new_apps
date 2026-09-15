"""Capturas de la ficha de al_l10n_pe_ple (datos «DEMO PLE», ejercicio 2026)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

ALTO = {'width': 1440, 'height': 1400}


def escoger_anio(c, boton, pasos=1):
    """Abre el filtro de fecha del informe y avanza el año."""
    c.clic('.o_control_panel button:has-text("%s")' % boton, ms=800)
    for _ in range(pasos):
        c.clic('.date_filter_year .btn_next_date', ms=2000)
    c.page.keyboard.press('Escape')
    c.esperar(1500)


with Captura('al_l10n_pe_ple', viewport=ALTO) as c:
    # 1. Asistente Exportar PLE con 7.1 y 4.1 generados (julio 2026)
    c.abrir_accion('al_l10n_pe_ple.action_ple_export_wizard', ms=2000)
    c.clic('.modal-dialog div[name=export_41] input', ms=600)
    c.clic('.modal-dialog div[name=month] input', ms=500)
    c.page.locator('.o_select_menu_item:has-text("07")').first.click()
    c.esperar(400)
    c.clic('.modal-dialog button[name=action_export]', ms=3000)
    c.foto('01-exportar-ple', selector='.modal-content')
    c.clic('.modal-header .btn-close', ms=800)

    # 2. Pestaña PLE SUNAT del activo en arrendamiento financiero
    c.abrir_registro('account.asset', 27, ms=2000)
    c.texto('PLE SUNAT')
    c.foto('02-activo-ple-sunat', selector='.o_form_view .o_form_sheet_bg')

with Captura('al_l10n_pe_ple', viewport={'width': 1440, 'height': 760}) as c:
    # 3. Registro de Activos Fijos en pantalla, con los botones del libro
    c.abrir_accion('al_l10n_pe_ple.action_report_ple_asset_7_1', ms=3000)
    escoger_anio(c, 'Al 31/12/2025')
    c.clic('.o_control_panel .fa-cog', ms=800)
    c.foto('03-libro7-pantalla')
    c.page.keyboard.press('Escape')
    c.esperar(500)

    # 4. El mismo informe, bloque de uso, método y depreciación
    c.js("document.querySelectorAll('*').forEach(e => {"
         " if (e.scrollWidth > e.clientWidth + 50"
         " && getComputedStyle(e).overflowX != 'visible') e.scrollLeft = 5000; })")
    c.esperar(600)
    c.foto('04-libro7-depreciacion')

with Captura('al_l10n_pe_ple', viewport={'width': 1440, 'height': 700}) as c:
    # 5. Captura del PLE 4.1
    c.abrir_accion('al_l10n_pe_ple.action_ple_withholding', ms=2000)
    c.foto('05-retenciones-41')

    # 6. Patrimonio 3.19
    c.abrir_accion('al_l10n_pe_ple.action_ple_equity', ms=2000)
    c.foto('06-patrimonio-319')

    # 7. Libro 10: elementos del costo por mes
    c.abrir_accion('al_l10n_pe_ple.action_ple_cost_element', ms=2000)
    c.foto('07-costos-102')

with Captura('al_l10n_pe_ple') as c:
    # 8. Albarán marcado como consignación (Libro 9)
    c.abrir_registro('stock.picking', 176, ms=2000)
    c.foto('08-consignacion', selector='.o_form_view .o_form_sheet_bg')

    # 10. RCE 8.4 (septiembre 2026, periodo por defecto) con los botones TXT y XLSX
    c.abrir_accion('al_l10n_pe_ple.action_report_ple_purchase_8_1', ms=3000)
    c.clic('.o_control_panel .fa-cog', ms=800)
    c.foto('10-rce-84')
    c.page.keyboard.press('Escape')

    # 11. Clasificación RCE en el producto «DEMO PLE Producto Consignado»
    c.abrir_registro('product.template', 155, ms=2000)
    c.texto('Contabilidad')
    c.foto('11-producto-rce', selector='.o_form_view .o_form_sheet_bg')

with Captura('al_l10n_pe_ple', viewport={'width': 1440, 'height': 420}) as c:
    # 9. Ajustes: formatos simplificados
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    c.page.get_by_text('Libros electrónicos PLE', exact=True).first.evaluate(
        "e => e.scrollIntoView({block: 'start'})")
    c.esperar(600)
    c.foto('09-ajustes')
