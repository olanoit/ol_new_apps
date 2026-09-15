"""Capturas de la ficha de al_l10n_pe_sire.

Datos: periodo RCE-07-2026 del script ``tools/sire_demo_data.py`` y periodo
RVIE-08-2026 en carga manual con una propuesta simulada
(``DEMO_Propuesta_RVIE_202608.txt``: una factura con otro importe, una que
SUNAT no tiene y una del socio «DEMO SIRE SOCIO SAC» que Odoo no tiene).
Ningún paso llama a la API de SUNAT.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

RVIE_ID = 22
RCE_ID = 3

with Captura('al_l10n_pe_sire', viewport={'width': 1920, 'height': 1500}) as c:
    # 1. Ajustes ▸ Perú: credenciales de la API SIRE (ventana más baja)
    c.page.set_viewport_size({'width': 1440, 'height': 620})
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    c.page.get_by_text('SIRE (RVIE / RCE)', exact=True).first.evaluate(
        "e => e.scrollIntoView({block: 'start'})")
    c.esperar(600)
    c.foto('01-ajustes')
    c.page.set_viewport_size(c.viewport)

    # 2. Nuevo periodo en carga manual (sin guardar)
    c.abrir_accion('al_l10n_pe_sire.action_sire_rvie', ms=2000)
    c.clic('.o_control_panel .o-kanban-button-new, .o_control_panel .o_list_button_add', ms=1500)
    c.clic('div[name=download_manual] input', ms=800)
    c.foto('02-nuevo-periodo', selector='.o_form_view .o_form_sheet_bg')
    c.clic('.o_form_button_cancel', ms=1000)

    # 3. Periodos del RVIE
    c.abrir_accion('al_l10n_pe_sire.action_sire_rvie', ms=2000)
    c.foto('03-periodos')

    # 4. Periodo comparado: resumen y diferencias
    c.abrir_registro('l10n_pe.sire.rvie', RVIE_ID, ms=2000)
    c.texto('Diferencias')
    # Más ancho para la columna Diferencias: se ocultan dos columnas
    # opcionales (preferencia local del navegador de la captura).
    for columna in ('Comprobante', 'Nro Doc Identidad'):
        c.clic('.o_notebook .o_optional_columns_dropdown button', ms=600)
        c.page.locator('.o-dropdown--menu .o-dropdown-item:has-text("%s") input' % columna).first.click()
        c.esperar(600)
        c.page.keyboard.press('Escape')
        c.esperar(400)
    c.foto('04-rvie-diferencias', selector='.o_form_view .o_form_sheet_bg')

    # 5. «Aceptar propuesta» con diferencias: el módulo lo rechaza antes de
    # pedir el token a SUNAT (action_accept_proposal valida los contadores
    # primero), así que no sale ninguna llamada a la API.
    c.clic('.o_form_statusbar button[name=action_accept_proposal]', ms=1200)
    c.clic('.modal-footer .btn-primary', ms=2000)
    c.foto('05-aceptar-con-diferencias', selector='.modal-content')
    c.clic('.modal-footer .btn-primary', ms=800)

    # 6. RCE: líneas construidas desde las facturas de proveedor
    c.abrir_registro('l10n_pe.sire.rce', RCE_ID, ms=2000)
    c.texto('Sistema')
    c.foto('06-rce-sistema', selector='.o_form_view .o_form_sheet_bg')

    # 7. Campos de comparación
    c.page.set_viewport_size({'width': 1440, 'height': 760})
    c.abrir_accion('al_l10n_pe_sire.action_sire_compare_field', ms=2000)
    c.texto('RVIE — Ventas (24)', ms=1500)
    c.foto('07-campos-comparacion')
    c.page.set_viewport_size(c.viewport)

    # 8. Clasificación de bienes y servicios en la factura de proveedor
    c.abrir_registro('account.move', 372, ms=2000)
    c.texto('Otra información')
    c.foto('08-factura-clasificacion', selector='.o_form_view .o_form_sheet_bg')
