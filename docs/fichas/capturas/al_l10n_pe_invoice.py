"""Capturas de la ficha de al_l10n_pe_invoice.

Datos: facturas electrónicas de la base de demostración (F001-00000002 con
detracción, F002-00000001 con exonerada e ICBPER, B001-00000001 con
inafectas, F001-00000211 en dólares) y, creados por odoo shell con prefijo
DEMO FAC, el pedido S00060 («30% ahora, el resto en 60 días», OC. externa
OC-2026-0457) con su factura en **borrador** (línea con descuento y descuento
global). Nada se publica ni se envía a SUNAT/OSE.

Los reportes se capturan desde su vista previa HTML (/report/html/...).

Uso: ``python al_l10n_pe_invoice.py [nombre de captura ...]``.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capturar  # noqa: E402
from capturar import Captura  # noqa: E402

A4 = '/report/html/al_l10n_pe_invoice.report_cpe_invoice_a4_main/%s'
TICKET = '/report/html/al_l10n_pe_invoice.report_cpe_ticket_main/%s'
FACTURA_DETRACCION = 470   # F001-00000002, detracción 022
FACTURA_EXONERADA = 1417   # F002-00000001, exonerada + ICBPER
BOLETA_INAFECTA = 466      # B001-00000001, gravada, exonerada, inafecta, ICBPER
FACTURA_USD = 65           # F001-00000211, US$ 1.180,00
FACTURA_CREDITO = 2436     # borrador DEMO FAC desde S00060
PEDIDO = 60                # S00060

NORMAL = {'width': 1440, 'height': 900}


def ventana(c, size):
    c.page.set_viewport_size(size)
    c.viewport = dict(size)


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


def ajustes(c):
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    foto_bloque(c, 'Comprobantes electrónicos', '01-ajustes')


def compania(c):
    c.abrir_registro('res.company', 1, ms=2500)
    c.foto('02-compania', selector='.o_form_view .o_form_sheet_bg')
    capturar._recortar_fondo(c.out / '02-compania.png')


def imprimir(c):
    c.abrir('/odoo/accounting', ms=1500)
    c.abrir('/odoo/accounting/action-account.action_move_out_invoice_type/%s' % FACTURA_DETRACCION, ms=2500)
    c.js("document.querySelectorAll('.o_attachment_preview').forEach(e => e.remove())")
    c.esperar(400)
    c.clic('.o_cp_action_menus button', ms=800)
    c.page.locator('.o-dropdown--menu .o-dropdown-item:has-text("Imprimir")').first.hover()
    c.esperar(800)
    c.page.locator('.o-dropdown--menu .o-dropdown-item:has-text("CPE A4")').first.hover()
    c.esperar(400)
    path = c.out / '03-imprimir.png'
    c.page.screenshot(path=str(path), clip={'x': 0, 'y': 0, 'width': 1440, 'height': 495})
    print('captura 03-imprimir')


def reporte(c, url, nombre):
    ventana(c, NORMAL)
    c.abrir(url, ms=2000)
    c.foto(nombre, selector='.cpe-a4', padding=14)


def a4_detraccion(c):
    reporte(c, A4 % FACTURA_DETRACCION, '04-a4-detraccion')


def a4_exonerada(c):
    reporte(c, A4 % FACTURA_EXONERADA, '05-a4-exonerada')


def a4_inafecta(c):
    reporte(c, A4 % BOLETA_INAFECTA, '06-a4-boleta-inafecta')


def a4_dolares(c):
    reporte(c, A4 % FACTURA_USD, '07-a4-dolares')


def a4_credito(c):
    reporte(c, A4 % FACTURA_CREDITO, '08-a4-credito')


def ticket(c):
    ventana(c, {'width': 420, 'height': 900})
    c.abrir(TICKET % FACTURA_EXONERADA, ms=2000)
    c.foto('09-ticket', full_page=True)
    ventana(c, NORMAL)


def ticket_detraccion(c):
    ventana(c, {'width': 420, 'height': 900})
    c.abrir(TICKET % FACTURA_DETRACCION, ms=2000)
    c.foto('10-ticket-detraccion', full_page=True)
    ventana(c, NORMAL)


def factura_orden(c):
    c.abrir('/odoo/action-account.action_move_out_invoice_type/%s' % FACTURA_CREDITO, ms=2500)
    c.foto('11-factura-orden', selector='.o_form_view .o_form_sheet_bg')


def pedido(c):
    c.abrir_registro('sale.order', PEDIDO, ms=2500)
    c.foto('12-pedido-oc', selector='.o_form_view .o_form_sheet_bg')


def certificados(c):
    c.abrir_accion('certificate.certificate_certificate_action_view_list', ms=2000)
    c.foto('13-certificados')


PASOS = [ajustes, compania, imprimir, a4_detraccion, a4_exonerada, a4_inafecta,
         a4_dolares, a4_credito, ticket, ticket_detraccion, factura_orden,
         pedido, certificados]

elegidos = sys.argv[1:]
with Captura('al_l10n_pe_invoice') as c:
    for paso in PASOS:
        if not elegidos or paso.__name__ in elegidos:
            print('--', paso.__name__)
            paso(c)
