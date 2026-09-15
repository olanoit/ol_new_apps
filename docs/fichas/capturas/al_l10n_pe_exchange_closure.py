"""Capturas de la ficha de al_l10n_pe_exchange_closure (datos «DEMO TC»).

Base: ``al_l10n_pe_exchange_closure/tools/exchange_closure_demo.py`` (cierres
de junio y julio 2026 contabilizados, CTC/2026/06/0007 y CTC/2026/07/0002).

Encima, por odoo shell y solo para estas capturas, un cierre de **agosto
2026** en estado Calculado: «Traer T.C.» con la descarga de apis.net.pe
anulada (no había T.C. del 31/08: tomó el del 02/08, 3,391 / 3,400) y
«Calcular». No se contabiliza.

Aquí no se pulsa «Traer T.C.» (descargaría la tasa) ni se confirma ninguna
acción: el diálogo de «Cancelar» se abre y se cierra con su botón Cancelar.

Uso: ``python al_l10n_pe_exchange_closure.py [nombre de captura ...]``.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402
from capturar import Captura, ROOT, _recortar_fondo  # noqa: E402

SHOTS = ROOT / 'al_l10n_pe_exchange_closure' / 'static' / 'description' / 'screenshots'

CUENTA_DETALLE = 46        # 1212000, con detalle por socio
CIERRE_JUNIO = 29
CIERRE_JULIO = 30
CIERRE_AGOSTO = 309        # calculado, sin contabilizar
ASIENTO_JUNIO = 1152       # CTC/2026/06/0007
ASIENTO_JULIO = 1153       # CTC/2026/07/0002
ACCION = 'al_l10n_pe_exchange_closure.action_exchange_closure'

NORMAL = {'width': 1440, 'height': 900}
ANCHO = {'width': 1920, 'height': 1100}


def ventana(c, size):
    c.page.set_viewport_size(size)
    c.viewport = dict(size)


def recortar_alto(nombre, alto):
    path = SHOTS / ('%s.png' % nombre)
    image = Image.open(path)
    if image.size[1] > alto:
        image.crop((0, 0, image.size[0], alto)).save(path, optimize=True)


def pestana(c, texto):
    c.page.locator('.o_notebook .nav-link', has_text=texto).first.click()
    c.esperar(900)


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


def columna_opcional(c, contenedor, etiqueta):
    c.page.locator(contenedor).locator('.o_optional_columns_dropdown_toggle').first.click()
    c.esperar(600)
    casilla = c.page.locator('.o-dropdown-item', has_text=etiqueta).locator('input')
    if casilla.count() and not casilla.first.is_checked():
        casilla.first.click()
        c.esperar(900)
    c.page.keyboard.press('Escape')
    c.esperar(500)


def cierre(c, res_id):
    c.abrir('/odoo/action-%s/%s' % (ACCION, res_id), ms=2500)


# ---- Configuración -------------------------------------------------------
def ajustes(c):
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    foto_bloque(c, 'Cierre de tipo de cambio', '01-ajustes')


def cuenta(c):
    c.abrir_registro('account.account', CUENTA_DETALLE, ms=2000)
    tab = c.page.locator('.o_notebook .nav-link:has-text("Contabilidad")')
    if tab.count():
        tab.first.click()
        c.esperar(700)
    c.foto('02-cuenta', selector='.o_form_view .o_form_sheet_bg')


def cuentas_cierre(c):
    c.abrir_accion('al_l10n_pe_exchange_closure.action_account_exchange_closing', ms=2000)
    columna_opcional(c, '.o_list_renderer', 'Cierre de tipo de cambio')
    c.foto('03-cuentas-cierre')
    recortar_alto('03-cuentas-cierre', 300)


# ---- Cierre del mes ------------------------------------------------------
def cierres(c):
    c.abrir_accion(ACCION, ms=2000)
    c.foto('04-cierres')
    recortar_alto('04-cierres', 330)


def agosto(c):
    ventana(c, ANCHO)
    cierre(c, CIERRE_AGOSTO)
    c.foto('05-cierre-calculado', selector='.o_form_view .o_form_view_container')
    ventana(c, NORMAL)


def vista_previa(c):
    ventana(c, ANCHO)
    cierre(c, CIERRE_AGOSTO)
    pestana(c, 'Vista previa del asiento')
    c.foto('06-vista-previa', selector='.o_form_view .o_form_sheet_bg')
    ventana(c, NORMAL)


def apuntes_renglon(c):
    ventana(c, ANCHO)
    cierre(c, CIERRE_JULIO)
    fila = c.page.locator('div[name=line_ids] .o_data_row', has_text='DEMO TC Cliente').first
    fila.locator('button[name=action_open_move_lines]').click()
    c.esperar(2500)
    c.foto('07-apuntes-renglon')
    recortar_alto('07-apuntes-renglon', 330)
    ventana(c, NORMAL)


def cancelar(c):
    cierre(c, CIERRE_AGOSTO)
    c.clic('.o_form_statusbar button[name=action_cancel]', ms=1200)
    c.foto('08-cancelar', selector='.modal-content')
    # Botón «Cancelar» del diálogo: no se ejecuta la acción.
    c.page.locator('.modal-footer button', has_text='Cancelar').first.click()
    c.esperar(800)


# ---- Cierres contabilizados ---------------------------------------------
def cierre_mes(c, res_id, nombre):
    ventana(c, ANCHO)
    cierre(c, res_id)
    c.foto(nombre, selector='.o_form_view .o_form_sheet_bg')
    ventana(c, NORMAL)


def asiento(c, res_id, nombre):
    ventana(c, {'width': 2400, 'height': 1500})
    c.abrir_registro('account.move', res_id, ms=2500)
    columna_opcional(c, 'div[name=line_ids]', 'T.C. de cierre')
    c.foto(nombre, selector='.o_form_view .o_form_sheet_bg')
    ventana(c, NORMAL)


def junio(c):
    cierre_mes(c, CIERRE_JUNIO, '09-cierre-junio')


def asiento_junio(c):
    asiento(c, ASIENTO_JUNIO, '10-asiento-junio')


def julio(c):
    cierre_mes(c, CIERRE_JULIO, '11-cierre-julio')


def asiento_julio(c):
    asiento(c, ASIENTO_JULIO, '12-asiento-julio')


PASOS = [ajustes, cuenta, cuentas_cierre, cierres, agosto, vista_previa,
         apuntes_renglon, cancelar, junio, asiento_junio, julio, asiento_julio]

elegidos = sys.argv[1:]
with Captura('al_l10n_pe_exchange_closure') as c:
    for paso in PASOS:
        if not elegidos or paso.__name__ in elegidos:
            print('--', paso.__name__)
            paso(c)
