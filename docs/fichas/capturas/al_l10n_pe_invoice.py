"""Capturas de la ficha de al_l10n_pe_invoice.

Datos: facturas electrónicas ya enviadas de la base de demostración
(F001-00000002 con detracción y F002-00000001 con exonerada e ICBPER).
Los reportes se capturan desde su vista previa HTML (/report/html/...).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capturar  # noqa: E402
from capturar import Captura  # noqa: E402

A4 = '/report/html/al_l10n_pe_invoice.report_cpe_invoice_a4_main/%s'
TICKET = '/report/html/al_l10n_pe_invoice.report_cpe_ticket_main/%s'
FACTURA_DETRACCION = 470   # F001-00000002, detracción 022, XML firmado
FACTURA_EXONERADA = 1417   # F002-00000001, exonerada + ICBPER, XML firmado


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


with Captura('al_l10n_pe_invoice') as c:
    # 2. Factura: menú Imprimir con los dos formatos propios
    c.abrir('/odoo/accounting', ms=1500)
    c.abrir('/odoo/accounting/action-account.action_move_out_invoice_type/%s' % FACTURA_DETRACCION, ms=2500)
    c.js("document.querySelectorAll('.o_attachment_preview').forEach(e => e.remove())")
    c.esperar(400)
    c.clic('.o_cp_action_menus button', ms=800)
    c.page.locator('.o-dropdown--menu .o-dropdown-item:has-text("Imprimir")').first.hover()
    c.esperar(800)
    c.page.locator('.o-dropdown--menu .o-dropdown-item:has-text("CPE A4")').first.hover()
    c.esperar(400)
    path = c.out / '02-imprimir.png'
    c.page.screenshot(path=str(path), clip={'x': 0, 'y': 0, 'width': 1440, 'height': 495})
    print('captura 02-imprimir')

    # 1. Ajustes ▸ Perú ▸ Comprobantes electrónicos
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    foto_bloque(c, 'Comprobantes electrónicos', '01-ajustes')

    # 3. A4 con detracción, cuentas bancarias y QR del XML firmado
    c.abrir(A4 % FACTURA_DETRACCION, ms=2000)
    c.foto('03-a4-detraccion', selector='.cpe-a4', padding=14)

    # 4. A4 con operaciones exoneradas e ICBPER
    c.abrir(A4 % FACTURA_EXONERADA, ms=2000)
    c.foto('04-a4-exonerada', selector='.cpe-a4', padding=14)

    # 5. Ticket 80 mm (ancho de rollo)
    c.page.set_viewport_size({'width': 420, 'height': 900})
    c.abrir(TICKET % FACTURA_EXONERADA, ms=2000)
    c.foto('05-ticket', full_page=True)
