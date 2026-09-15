"""Capturas de la ficha de al_l10n_pe_detraction (datos «DEMO SPOT» / «DEMO SPLIT»).

Las cuentas de detracciones del Banco de la Nación de «DEMO SPOT Contraparte
SAC» y «DEMO SPOT2 Cliente SAC» se cargaron por odoo shell para el depósito
masivo; «DEMO SPLIT SAC» queda sin cuenta a propósito (sale como excluido).
Los asistentes se abren y se capturan, pero no se confirman.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capturar  # noqa: E402
from capturar import Captura  # noqa: E402

PRODUCTO_SPOT = 165          # DEMO SPOT Servicio Empresarial (037)
FACTURA_VENTA = 206          # DPSV/2026/00002, S/ 5.900, 12 % = S/ 708
FACTURA_REPARTO = 250        # DPSV/2026/00008, reparto en 121901
FACTURA_COMPRA = 233         # DPSC/2026/07/0004, sin constancia


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


with Captura('al_l10n_pe_detraction') as c:
    # 1. Catálogo 54 (Perú ▸ Configuración ▸ Tributos SUNAT ▸ Detracciones)
    c.abrir_accion('al_l10n_pe_detraction.action_detraction_type', ms=2000)
    c.page.set_viewport_size({'width': 1440, 'height': 760})
    c.esperar(400)
    c.foto('01-catalogo')
    c.page.set_viewport_size(c.viewport)

    # 2. Producto con su tipo de detracción
    c.abrir_registro('product.template', PRODUCTO_SPOT, ms=2000)
    c.foto('02-producto', selector='.o_form_view .o_form_sheet_bg')

    # 3. Factura de venta: pestaña Detracción
    c.abrir('/odoo/action-account.action_move_out_invoice_type/%s' % FACTURA_VENTA, ms=2500)
    c.texto('Detracción', ms=800)
    c.foto('03-factura-venta', selector='.o_form_view .o_form_sheet_bg')

    # 4. Reparto dentro del mismo asiento
    c.abrir('/odoo/action-account.action_move_out_invoice_type/%s' % FACTURA_REPARTO, ms=2500)
    c.texto('Apuntes contables', ms=800)
    c.foto('04-reparto-asiento', selector='.o_form_view .o_form_sheet_bg')

    # 5. Registrar depósito en una factura de proveedor (sin confirmar)
    c.abrir('/odoo/action-account.action_move_in_invoice_type/%s' % FACTURA_COMPRA, ms=2500)
    c.texto('Detracción', ms=800)
    c.clic('button[name=action_open_detraction_deposit]', ms=1500)
    c.page.locator('.modal-dialog div[name=journal_id] input').fill('Banco')
    c.esperar(900)
    c.page.locator('.o-autocomplete--dropdown-item').first.click()
    c.esperar(800)
    c.page.locator('.modal-dialog div[name=constancy_number] input').fill('0987654321')
    c.js("document.activeElement && document.activeElement.blur()")
    c.esperar(600)
    c.foto('05-registrar-deposito', selector='.modal-content')
    c.clic('.modal-footer button:has-text("Cancelar")', ms=800)

    # 6. Depósito masivo del Banco de la Nación, julio 2026
    c.abrir('/odoo/action-al_l10n_pe_detraction.action_l10n_pe_detraction_txt_wizard', ms=2000)
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
    c.foto('06-deposito-masivo', selector='.modal-content')

    # 7. Ajustes ▸ Perú ▸ Detracciones (SPOT)
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    foto_bloque(c, 'Detracciones (SPOT)', '07-ajustes')
