"""Capturas de la ficha de al_l10n_pe_currency.

No se pulsa ningún botón que descargue tipos de cambio (SUNAT, BCRP,
Decolecta, apis.net.pe): se fotografían las tasas ya registradas y los
asistentes antes de aceptar.

Datos «DEMO TC FACTURA», creados por odoo shell (idempotente):

- Diario de ventas DTCV «DEMO TC Ventas» (sin documentos LATAM).
- Dos facturas de US$ 1.180,00 del 02/08/2026 a «DEMO TC FACTURA Cliente
  SAC», iguales salvo el tipo de T.C.: DTCV/2026/00001 a venta (3,400) y
  DTCV/2026/00002 a compra (3,391).
- Cobro PBNK1/2026/00005 de la primera, registrado con T.C. compra, y su
  diferencia de cambio CAMBI/2026/08/0001.

Uso: ``python al_l10n_pe_currency.py [nombre de captura ...]``.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402
from capturar import Captura, ROOT, _recortar_fondo  # noqa: E402

SHOTS = ROOT / 'al_l10n_pe_currency' / 'static' / 'description' / 'screenshots'

USD = 1
TASA_MANUAL = 67             # 31/07/2026, compañía 1, origen Manual
FACTURA_VENTA = 2432         # DTCV/2026/00001, T.C. venta
FACTURA_COMPRA = 2433        # DTCV/2026/00002, T.C. compra
COBRO = 181                  # PBNK1/2026/00005, T.C. compra
DIFERENCIA = 2435            # CAMBI/2026/08/0001
CRON_TC = 42

NORMAL = {'width': 1440, 'height': 900}
ANCHO = {'width': 2400, 'height': 1100}


def ventana(c, size):
    c.page.set_viewport_size(size)
    c.viewport = dict(size)


def recortar_alto(nombre, alto):
    path = SHOTS / ('%s.png' % nombre)
    image = Image.open(path)
    if image.size[1] > alto:
        image.crop((0, 0, image.size[0], alto)).save(path, optimize=True)


def blur(c):
    c.js("() => document.activeElement && document.activeElement.blur()")
    c.esperar(400)


def foto_bloque(c, titulo, nombre):
    """Recorta un bloque de Ajustes: su título y su contenido."""
    c.page.locator('h2', has_text=titulo).first.evaluate(
        "e => e.scrollIntoView({block: 'start'})")
    c.esperar(600)
    box = c.page.evaluate("""(t) => {
        const h = [...document.querySelectorAll('h2')].find(x => x.textContent.trim() === t.trim());
        const a = h.getBoundingClientRect(), b = h.nextElementSibling.getBoundingClientRect();
        return {x: a.left, y: a.top, width: a.width, height: b.bottom - a.top + 8};
    }""", titulo)
    c.page.mouse.move(1, c.viewport['height'] - 2)
    path = SHOTS / ('%s.png' % nombre)
    c.page.screenshot(path=str(path), clip=box)
    _recortar_fondo(path)
    print('captura', path.relative_to(ROOT))


def pestana(c, texto):
    c.page.locator('.o_notebook .nav-link', has_text=texto).first.click()
    c.esperar(900)


# ---- Configuración -------------------------------------------------------
def ajustes(c):
    c.abrir('/odoo/settings#account', ms=2500)
    foto_bloque(c, 'Tipo de cambio (Perú)', '01-ajustes')


def cron(c):
    c.abrir_registro('ir.cron', CRON_TC, ms=2000)
    c.foto('02-cron', selector='.o_form_view .o_form_sheet_bg')


# ---- Tipos de cambio -----------------------------------------------------
def tipos_de_cambio(c):
    c.abrir_accion('al_l10n_pe_currency.action_l10n_pe_currency_rate', ms=2000)
    c.foto('03-tipos-de-cambio')
    recortar_alto('03-tipos-de-cambio', 560)


def tasa(c):
    c.abrir('/odoo/action-al_l10n_pe_currency.action_l10n_pe_currency_rate/%s'
            % TASA_MANUAL, ms=2000)
    c.foto('04-tasa', selector='.o_form_view .o_form_sheet_bg')


def aviso_compra(c):
    """Registro manual (sin guardar): compra mayor que venta."""
    c.abrir('/odoo/action-al_l10n_pe_currency.action_l10n_pe_currency_rate/new', ms=2000)
    c.page.locator('div[name=rate_purchase] input').fill('3,500')
    blur(c)
    c.page.locator('div[name=rate_sale] input').fill('3,400')
    blur(c)
    c.esperar(1200)
    c.foto('05-aviso-compra', selector='.modal-content')
    c.page.locator('.modal-footer button').first.click()
    c.esperar(600)
    c.page.locator('.o_form_button_cancel').first.click()
    c.esperar(800)


def moneda(c):
    c.abrir_registro('res.currency', USD, ms=2000)
    c.foto('06-moneda-usd', selector='.o_form_view .o_form_view_container')
    recortar_alto('06-moneda-usd', 700)


def asistente_mes(c):
    c.abrir_accion('al_l10n_pe_currency.action_l10n_pe_exchange_rate_wizard', ms=2000)
    c.page.locator('.modal-dialog div[name=range] input[data-value=month]').first.check()
    c.esperar(1200)
    c.page.locator('.modal-dialog div[name=month] select, .modal-dialog div[name=month] input').first.click()
    c.esperar(500)
    item = c.page.locator('.o_select_menu_item', has_text='Julio')
    if item.count():
        item.first.click()
        c.esperar(900)
    else:
        c.page.keyboard.press('Escape')
    blur(c)
    c.foto('07-asistente-mes', selector='.modal-content')
    c.clic('.modal-header .btn-close', ms=800)


def asistente_decolecta(c):
    c.abrir_accion('al_l10n_pe_currency.action_l10n_pe_exchange_rate_wizard', ms=2000)
    c.page.locator('.modal-dialog div[name=range] input[data-value=dates]').first.check()
    c.esperar(1000)
    c.page.locator('.modal-dialog div[name=source] input').first.click()
    c.esperar(700)
    c.page.locator('.o_select_menu_item', has_text='Decolecta').first.click()
    c.esperar(1000)
    blur(c)
    c.foto('08-asistente-decolecta', selector='.modal-content')
    c.clic('.modal-header .btn-close', ms=800)


# ---- Facturas y pagos ----------------------------------------------------
def factura(c, res_id, nombre):
    ventana(c, ANCHO)
    c.abrir('/odoo/action-account.action_move_out_invoice_type/%s' % res_id, ms=2500)
    pestana(c, 'Apuntes contables')
    c.foto(nombre, selector='.o_form_view .o_form_sheet_bg')
    ventana(c, NORMAL)


def factura_venta(c):
    factura(c, FACTURA_VENTA, '09-factura-venta')


def factura_compra(c):
    factura(c, FACTURA_COMPRA, '10-factura-compra')


def registrar_pago(c):
    """Asistente de pago de la factura a compra (sin registrar)."""
    c.abrir('/odoo/action-account.action_move_out_invoice_type/%s' % FACTURA_COMPRA, ms=2500)
    c.clic('.o_form_statusbar button[name=action_register_payment]', ms=3500)
    blur(c)
    c.foto('11-registrar-pago', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(800)


def cobro(c):
    c.abrir_registro('account.payment', COBRO, ms=2500)
    c.foto('12-cobro', selector='.o_form_view .o_form_sheet_bg')


def diferencia(c):
    c.abrir_registro('account.move', DIFERENCIA, ms=2500)
    c.foto('13-diferencia-cambio', selector='.o_form_view .o_form_sheet_bg')


PASOS = [ajustes, cron, tipos_de_cambio, tasa, aviso_compra, moneda,
         asistente_mes, asistente_decolecta, factura_venta, factura_compra,
         registrar_pago, cobro, diferencia]

elegidos = sys.argv[1:]
with Captura('al_l10n_pe_currency') as c:
    for paso in PASOS:
        if not elegidos or paso.__name__ in elegidos:
            print('--', paso.__name__)
            paso(c)
