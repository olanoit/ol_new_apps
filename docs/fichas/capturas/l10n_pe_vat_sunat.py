"""Capturas de la ficha de l10n_pe_vat_sunat.

Solo se fotografían formularios y datos ya guardados: no se pulsa ningún botón
que consulte una API (RUC/DNI, padrón SUNAT). La única edición es escribir un
RUC mal formado en un contacto nuevo, que se rechaza antes de consultar nada,
y se descarta.

Uso: ``python l10n_pe_vat_sunat.py [nombre de captura ...]`` (sin argumentos,
todas)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402
from capturar import Captura, ROOT, _recortar_fondo  # noqa: E402

SHOTS = ROOT / 'l10n_pe_vat_sunat' / 'static' / 'description' / 'screenshots'

CONEXION_DECOLECTA = 35
CONEXION_SUNAT = 3
CONEXION_JSONPE = 11      # POST con cuerpo JSON, deshabilitada
CONEXION_APIPERU = 1
CONTACTO_OK = 4645        # NOR AUTOS CHICLAYO S.A.C.: activo, habido, agente
CONTACTO_ALERTA = 64      # ANGEL DIVINO BUS S.A.C.: última consulta fallida
CRON_PADRON = 38


def recortar_alto(nombre, alto):
    path = SHOTS / ('%s.png' % nombre)
    image = Image.open(path)
    if image.size[1] > alto:
        image.crop((0, 0, image.size[0], alto)).save(path, optimize=True)


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


def ajustes(c):
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    foto_bloque(c, 'Validación RUC/DNI (PE)', '01-ajustes')


def compania(c):
    c.abrir_registro('res.company', 1, ms=2500)
    c.page.locator('.o_notebook .nav-link', has_text='Validación RUC/DNI').first.click()
    c.esperar(900)
    c.foto('02-compania', selector='.o_form_view .o_form_sheet_bg')


def conexiones(c):
    # Desde el botón de Ajustes: filtra la compañía activa. El menú muestra
    # las conexiones de todas las compañías permitidas, mezcladas.
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    c.clic('button[name=action_open_pe_api_connections]', ms=2000)
    c.foto('03-conexiones')
    recortar_alto('03-conexiones', 420)


def conexion_mapeo(c):
    c.abrir_registro('l10n_pe.api.connection', CONEXION_DECOLECTA, ms=2000)
    c.foto('04-conexion-mapeo', selector='.o_form_view .o_form_sheet_bg')


def conexion_post(c):
    c.abrir_registro('l10n_pe.api.connection', CONEXION_JSONPE, ms=2000)
    c.foto('05-conexion-post', selector='.o_form_view .o_form_sheet_bg')


def conexion_sunat(c):
    c.abrir_registro('l10n_pe.api.connection', CONEXION_SUNAT, ms=2000)
    c.foto('06-conexion-sunat', selector='.o_form_view .o_form_sheet_bg')


def mapeo_opciones(c):
    """Columnas opcionales del mapeo: valor por defecto y omitir si vacío."""
    c.abrir_registro('l10n_pe.api.connection', CONEXION_APIPERU, ms=2000)
    lista = c.page.locator('div[name=mapping_ids]')
    lista.locator('.o_optional_columns_dropdown_toggle').click()
    c.esperar(600)
    for etiqueta in ('Valor por defecto', 'Omitir si vacío'):
        casilla = c.page.locator('.o-dropdown-item', has_text=etiqueta).locator('input')
        if not casilla.is_checked():
            casilla.click()
            c.esperar(700)
    c.page.keyboard.press('Escape')
    c.esperar(500)
    c.foto('07-mapeo-opciones', selector='.o_form_view .o_notebook')


def contacto(c):
    c.abrir_registro('res.partner', CONTACTO_OK, ms=2000)
    c.foto('08-contacto', selector='.o_form_view .o_form_renderer')


def contacto_alerta(c):
    c.abrir_registro('res.partner', CONTACTO_ALERTA, ms=2000)
    c.foto('09-contacto-alerta', selector='.o_form_view .o_form_renderer')
    recortar_alto('09-contacto-alerta', 520)


def ruc_invalido(c):
    """Contacto nuevo (empresa, RUC): un número de 4 dígitos se rechaza por
    formato antes de consultar ninguna conexión. Se descarta."""
    c.abrir('/odoo/contacts/new', ms=2500)
    c.page.locator('div[name=vat] input').fill('1234')
    c.page.keyboard.press('Tab')
    c.esperar(1500)
    c.foto('10-ruc-invalido', selector='.modal-content')
    c.page.locator('.modal-footer button').first.click()
    c.esperar(600)
    c.page.locator('.o_form_button_cancel').first.click()
    c.esperar(800)


def padron(c):
    c.abrir_accion('l10n_pe_vat_sunat.action_l10n_pe_sunat_padron', ms=2000)
    c.clic('.o_searchview_dropdown_toggler', ms=700)
    c.clic('.o-dropdown-item:text-is("Tipo de padrón")', ms=1500)
    c.clic('.o_searchview_dropdown_toggler', ms=700)
    c.clic('.o_group_name:has-text("Agente de retención")', ms=1800)
    c.foto('11-padron')
    recortar_alto('11-padron', 470)


def cron(c):
    c.abrir_registro('ir.cron', CRON_PADRON, ms=2000)
    c.foto('12-cron', selector='.o_form_view .o_form_sheet_bg')


def menu_contactos(c):
    c.abrir('/odoo/contacts', ms=2000)
    c.page.locator('.o_menu_sections button', has_text='Configuración').first.click()
    c.esperar(800)
    c.page.mouse.move(700, 600)
    c.foto('13-menu-contactos', clip={'x': 0, 'y': 0, 'width': 760, 'height': 560},
           recortar=False)


PASOS = [ajustes, compania, conexiones, conexion_mapeo, conexion_post,
         conexion_sunat, mapeo_opciones, contacto, contacto_alerta,
         ruc_invalido, padron, cron, menu_contactos]

elegidos = sys.argv[1:]
with Captura('l10n_pe_vat_sunat', viewport={'width': 1440, 'height': 1250}) as c:
    for paso in PASOS:
        if not elegidos or paso.__name__ in elegidos:
            print('--', paso.__name__)
            paso(c)
