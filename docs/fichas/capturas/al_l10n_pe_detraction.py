"""Capturas de la ficha de al_l10n_pe_detraction (datos «DEMO SPOT» / «DEMO SPLIT»).

Datos previos, cargados por odoo shell sobre registros DEMO:

- Cuentas de detracciones del Banco de la Nación en «DEMO SPOT Contraparte
  SAC» y «DEMO SPOT2 Cliente SAC»; «DEMO SPLIT SAC» queda sin cuenta a
  propósito (sale como excluido en el depósito masivo).
- Depósitos registrados con el asistente sobre las facturas con reparto
  DPSC/2026/07/0007 (constancia DEMO-SPLIT-0001) y DPSV/2026/00008
  (DEMO-SPLIT-0002).

Los asistentes que se capturan aquí se abren pero no se confirman.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capturar  # noqa: E402
from capturar import Captura  # noqa: E402

TIPO_037 = 24                # [037] Demás servicios gravados con el IGV
PRODUCTO_SPOT = 165          # DEMO SPOT Servicio Empresarial (037)
CONTACTO = 149               # DEMO SPOT Contraparte SAC, con cuenta del BN
FACTURA_VENTA = 206          # DPSV/2026/00002, S/ 5.900, 12 % = S/ 708
FACTURA_REPARTO = 250        # DPSV/2026/00008, reparto en 121901, depositada
FACTURA_COMPRA = 233         # DPSC/2026/07/0004, sin constancia
COMPRA_REPARTO = 251         # DPSC/2026/07/0007, reparto en 424901, depositada
PAGO_DEPOSITO = 178          # PBNK1/2026/00003, depósito de DPSC/2026/07/0007


def foto_bloque(c, titulo, nombre, margen=16, ancho=780):
    """Recorta un bloque de Ajustes: su título y el contenedor siguiente."""
    c.page.evaluate("""(t) => Array.from(document.querySelectorAll('.app_settings_block h2'))
        .find(e => e.textContent.trim() === t).scrollIntoView({block: 'start'})""", titulo)
    c.esperar(500)
    box = c.page.evaluate("""(t) => {
        const h = Array.from(document.querySelectorAll('.app_settings_block h2'))
            .find(e => e.textContent.trim() === t);
        const a = h.getBoundingClientRect();
        const b = h.nextElementSibling.getBoundingClientRect();
        return {x: Math.min(a.x, b.x), y: a.y, width: Math.max(a.right, b.right) - Math.min(a.x, b.x),
                height: b.bottom - a.y};
    }""", titulo)
    c.page.mouse.move(c.viewport['width'] - 2, c.viewport['height'] - 2)
    path = c.out / ('%s.png' % nombre)
    c.page.screenshot(path=str(path), clip={
        'x': box['x'], 'y': max(box['y'] - margen, 0),
        'width': min(box['width'], ancho), 'height': box['height'] + 2 * margen})
    capturar._recortar_fondo(path)
    print('captura', nombre)


def pestana(c, texto):
    c.page.locator('.o_notebook .nav-link', has_text=texto).first.click()
    c.esperar(900)


def factura(c, accion, res_id):
    c.abrir('/odoo/action-%s/%s' % (accion, res_id), ms=2500)


with Captura('al_l10n_pe_detraction') as c:
    # ---- Configuración -------------------------------------------------
    # 1. Catálogo 54
    c.abrir_accion('al_l10n_pe_detraction.action_detraction_type', ms=2000)
    c.page.set_viewport_size({'width': 1440, 'height': 760})
    c.esperar(400)
    c.foto('01-catalogo')
    c.page.set_viewport_size(c.viewport)

    # 2. Ficha de un tipo: botón de sincronización y productos vinculados
    c.abrir('/odoo/action-al_l10n_pe_detraction.action_detraction_type/%s' % TIPO_037, ms=2000)
    # En pantalla ancha Odoo 19 lleva los botones inteligentes a la barra de
    # control: se recorta desde la barra para que salga «Productos».
    c.foto('02-tipo-detraccion', clip={'x': 0, 'y': 46, 'width': 1440, 'height': 330})

    # 3. Producto con su tipo de detracción
    c.abrir_registro('product.template', PRODUCTO_SPOT, ms=2000)
    c.foto('03-producto', selector='.o_form_view .o_form_sheet_bg')

    # 4. Contacto con la cuenta de detracciones del Banco de la Nación
    c.abrir_registro('res.partner', CONTACTO, ms=2000)
    c.foto('04-contacto', selector='.o_form_view .o_form_sheet_bg')

    # 5. Ajustes ▸ Perú ▸ Detracciones (SPOT)
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    foto_bloque(c, 'Detracciones (SPOT)', '05-ajustes')

    # ---- Ventas ----------------------------------------------------------
    # 6. Factura de venta: pestaña Detracción
    factura(c, 'account.action_move_out_invoice_type', FACTURA_VENTA)
    pestana(c, 'Detracción')
    c.foto('06-factura-venta', selector='.o_form_view .o_form_sheet_bg')

    # 7. Reparto dentro del asiento de la venta
    factura(c, 'account.action_move_out_invoice_type', FACTURA_REPARTO)
    pestana(c, 'Apuntes contables')
    c.foto('07-reparto-venta', selector='.o_form_view .o_form_sheet_bg')

    # ---- Compras ---------------------------------------------------------
    # 8. Factura de proveedor sin constancia: botón Registrar depósito
    factura(c, 'account.action_move_in_invoice_type', FACTURA_COMPRA)
    pestana(c, 'Detracción')
    c.foto('08-factura-compra', selector='.o_form_view .o_form_sheet_bg')

    # 9. Asistente Registrar depósito (sin confirmar)
    c.clic('button[name=action_open_detraction_deposit]', ms=1500)
    c.page.locator('.modal-dialog div[name=journal_id] input').fill('Banco')
    c.esperar(900)
    c.page.locator('.o-autocomplete--dropdown-item').first.click()
    c.esperar(800)
    c.page.locator('.modal-dialog div[name=constancy_number] input').fill('0987654321')
    c.js("document.activeElement && document.activeElement.blur()")
    c.esperar(600)
    c.foto('09-registrar-deposito', selector='.modal-content')
    c.clic('.modal-footer button:has-text("Cancelar")', ms=800)

    # 10. Compra con reparto ya depositada: constancia guardada
    factura(c, 'account.action_move_in_invoice_type', COMPRA_REPARTO)
    pestana(c, 'Detracción')
    c.foto('10-constancia', selector='.o_form_view .o_form_sheet_bg')

    # 11. Reparto dentro del asiento de la compra
    pestana(c, 'Apuntes contables')
    c.foto('11-reparto-compra', selector='.o_form_view .o_form_sheet_bg')

    # 12. Pago generado por el depósito
    c.abrir_registro('account.payment', PAGO_DEPOSITO, ms=2000)
    c.foto('12-pago-deposito', selector='.o_form_view .o_form_sheet_bg')

    # 13. Facturas de proveedor: filtro «Detracción sin constancia»
    c.abrir_accion('account.action_move_in_invoice_type', ms=2500)
    c.clic('.o_searchview_dropdown_toggler', ms=900)
    c.texto('Detracción sin constancia', ms=1500)
    c.clic('.o_searchview_dropdown_toggler', ms=700)
    c.foto('13-sin-constancia', clip={'x': 0, 'y': 46, 'width': 1440, 'height': 200})

    # ---- Depósito masivo -------------------------------------------------
    # 14. Depósito masivo del Banco de la Nación, julio 2026
    c.abrir_accion('al_l10n_pe_detraction.action_l10n_pe_detraction_txt_wizard', ms=2000)
    for name, val in (('date_from', '01/07/2026'), ('date_to', '31/07/2026')):
        inp = c.page.locator('.modal-dialog div[name=%s] input' % name)
        inp.fill(val)
        inp.press('Enter')
        c.esperar(400)
        c.js("document.activeElement && document.activeElement.blur()")
    c.page.locator('.modal-footer button[name=action_generate]').click(force=True)
    c.esperar(2500)
    c.js("document.activeElement && document.activeElement.blur()")
    c.esperar(300)
    c.foto('14-deposito-masivo', selector='.modal-content')

    # ---- Contraste con SUNAT ---------------------------------------------
    # 15. Catálogo con el botón «Contrastar con SUNAT»
    c.page.set_viewport_size({'width': 1440, 'height': 900})
    c.abrir_accion('al_l10n_pe_detraction.action_detraction_type', ms=2500)
    c.page.locator('.o_al_detraction_check_btn').wait_for()
    c.foto('15-contrastar-boton', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 330})

    # 16. Contraste real con la página de SUNAT (descarga la página: crea un
    # contraste nuevo en el historial, que es lo que hace el botón)
    c.page.set_viewport_size({'width': 1600, 'height': 1500})
    c.clic('.o_al_detraction_check_btn', ms=8000)
    c.foto('16-contraste-sunat', selector='.o_form_view .o_form_sheet_bg')
    c.page.set_viewport_size({'width': 1440, 'height': 900})
