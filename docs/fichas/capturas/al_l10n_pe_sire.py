"""Capturas de la ficha de al_l10n_pe_sire.

Datos: periodos RVIE-07-2026 (SIRE desplegado) y RCE-07-2026 del script
``tools/sire_demo_data.py``, y periodo RVIE-08-2026 en carga manual con una
propuesta simulada (``DEMO_Propuesta_RVIE_202608.txt``: una factura con otro
importe, una que SUNAT no tiene y una del socio «DEMO SIRE SOCIO SAC» que Odoo
no tiene).

Ningún paso llama a la API de SUNAT: la compañía no tiene credenciales, los
formularios nuevos se descartan sin guardar y los diálogos de confirmación se
cierran con «Cancelar». Uso: ``al_l10n_pe_sire.py [bloque …]``.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

RVIE_JUL_ID = 3     # RVIE-07-2026, estado «SIRE desplegado»
RVIE_ID = 22        # RVIE-08-2026, estado «Comparado»
RCE_ID = 3          # RCE-07-2026, estado «Comparado»
FACTURA_ID = 372    # F F077-00000771, compra de «DEMO SIRE SOCIO SAC»
FORM = '.o_form_view .o_form_sheet_bg'
BLOQUES = {int(a) for a in sys.argv[1:]} or {1, 2}


def ocultar_columnas(c, columnas):
    """Oculta columnas opcionales de la lista del cuaderno (preferencia local
    del navegador de la captura, no se guarda en la base)."""
    for columna in columnas:
        c.clic('.o_notebook .o_optional_columns_dropdown button', ms=600)
        c.page.locator('.o-dropdown--menu .o-dropdown-item:has-text("%s") input'
                       % columna).first.click()
        c.esperar(600)
        c.page.keyboard.press('Escape')
        c.esperar(400)


if 1 in BLOQUES:
    with Captura('al_l10n_pe_sire', viewport={'width': 1920, 'height': 1500}) as c:
        # 01. Ajustes ▸ Perú: credenciales de la API SIRE (ventana más baja)
        c.page.set_viewport_size({'width': 1440, 'height': 620})
        c.abrir('/odoo/settings#al_account_base', ms=2500)
        c.page.get_by_text('SIRE (RVIE / RCE)', exact=True).first.evaluate(
            "e => e.scrollIntoView({block: 'start'})")
        c.esperar(600)
        c.foto('01-ajustes')
        c.page.set_viewport_size(c.viewport)

        # 04. Nuevo periodo por API (sin guardar): botón «Solicitar propuesta»
        c.abrir_accion('al_l10n_pe_sire.action_sire_rvie', ms=2000)
        c.clic('.o_control_panel .o_list_button_add', ms=1500)
        c.foto('04-nuevo-periodo-api', selector=FORM)

        # 05. El mismo formulario en carga manual: «Confirmar TXT manual»
        c.clic('div[name=download_manual] input', ms=800)
        c.foto('05-nuevo-periodo-manual', selector=FORM)
        c.clic('.o_form_button_cancel', ms=1000)

        # 06. Periodos del RVIE
        c.abrir_accion('al_l10n_pe_sire.action_sire_rvie', ms=2000)
        c.foto('06-periodos')

        # 07. Periodo con la propuesta desplegada: pestaña SIRE y botón
        # «Desplegar sistema»
        c.abrir_registro('l10n_pe.sire.rvie', RVIE_JUL_ID, ms=2000)
        c.foto('07-rvie-sire-desplegado', selector=FORM)

        # 08. Periodo comparado: resumen y diferencias (más ancho para la
        # columna Diferencias)
        c.abrir_registro('l10n_pe.sire.rvie', RVIE_ID, ms=2000)
        c.texto('Diferencias')
        ocultar_columnas(c, ('Comprobante', 'Nro Doc Identidad'))
        c.foto('08-rvie-diferencias', selector=FORM)

        # 11. «Aceptar propuesta» con diferencias: action_accept_proposal
        # valida los contadores antes de pedir el token, así que se rechaza
        # sin salir a SUNAT.
        c.clic('.o_form_statusbar button[name=action_accept_proposal]', ms=1200)
        c.clic('.modal-footer .btn-primary', ms=2000)
        c.foto('11-aceptar-con-diferencias', selector='.modal-content')
        c.clic('.modal-footer .btn-primary', ms=800)

        # 12. Confirmación de «Enviar reemplazo»: se cierra con «Cancelar»
        c.abrir_registro('l10n_pe.sire.rvie', RVIE_ID, ms=2000)
        c.clic('.o_form_statusbar button[name=action_send_replacement]', ms=1200)
        c.foto('12-confirmar-reemplazo', selector='.modal-content')
        c.clic('.modal-footer .btn-secondary', ms=800)

if 2 in BLOQUES:
    with Captura('al_l10n_pe_sire', viewport={'width': 1920, 'height': 1500}) as c:
        # 09. RCE: líneas construidas desde las facturas de proveedor
        c.abrir_registro('l10n_pe.sire.rce', RCE_ID, ms=2000)
        c.texto('Sistema')
        c.foto('09-rce-sistema', selector=FORM)

        # 10. RCE: diferencias (comprobantes solo en el sistema)
        c.texto('Diferencias')
        c.foto('10-rce-diferencias', selector=FORM)

        # 03. Clasificación de bienes y servicios en la factura de proveedor
        c.abrir_registro('account.move', FACTURA_ID, ms=2000)
        c.texto('Otra información')
        c.foto('03-factura-clasificacion', selector=FORM)

        # 02. Campos de comparación
        c.page.set_viewport_size({'width': 1440, 'height': 760})
        c.abrir_accion('al_l10n_pe_sire.action_sire_compare_field', ms=2000)
        c.texto('RVIE — Ventas (24)', ms=1500)
        c.foto('02-campos-comparacion')
        c.page.set_viewport_size(c.viewport)
