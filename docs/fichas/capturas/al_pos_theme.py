"""Capturas de la ficha de al_pos_theme (tema y marca blanca del TPV).

Usa el punto de venta «DEMO TPV Vendedores» (id 23) y su sesión abierta, sin
cobrar ninguna orden. La caja queda con la marca neutra por defecto; para el
ejemplo de marca propia se le aplica una marca DEMO y al final se restaura.
El administrador tiene la vista de lista de al_pos_product_view como
preferencia: el guion la deja igual al terminar.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import URL, Captura  # noqa: E402

CONFIG = 23
DESKTOP = {'width': 1440, 'height': 900}
PHONE = {'width': 390, 'height': 844}
DEMO_BRAND = {
    'al_theme_brand_name': 'DEMO Botica Central',
    'al_theme_color_primary': '#0F766E',
    'al_theme_color_secondary': '#134E4A',
    'al_theme_color_accent': '#F59E0B',
    'al_theme_color_background': '#F6F8F7',
}
NEUTRAL = {'al_theme_brand_name': False, 'al_theme_color_primary': '#2563EB',
           'al_theme_color_secondary': '#1E293B', 'al_theme_color_accent': '#0EA5E9',
           'al_theme_color_background': '#F8FAFC'}


def w(c, ms):
    c.page.wait_for_timeout(ms)


def rpc_write(c, vals):
    c.page.evaluate("""([id, vals]) => fetch('/web/dataset/call_kw', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
            model: 'pos.config', method: 'write', args: [[id], vals], kwargs: {}}})
    }).then(r => r.json())""", [CONFIG, vals])


def abrir_tpv(c, desbloquear=True):
    c.abrir('/pos/ui/%s' % CONFIG, ms=6000)
    if not desbloquear:
        return
    p = c.page
    for text in ('Desbloquear caja registradora', 'Abrir caja registradora'):
        if p.get_by_text(text, exact=True).count():
            p.get_by_text(text, exact=True).first.click()
            w(c, 2500)
    p.wait_for_selector('.product-list', timeout=60000)
    w(c, 1500)


def vista(c, lista):
    p = c.page
    es_lista = p.locator('.pos-product-list-row').count() > 0
    if es_lista != lista and p.locator('.pos-view-switch__btn').count():
        p.locator('.pos-view-switch__btn').click()
        w(c, 1500)


with Captura('al_pos_theme', viewport=DESKTOP) as c:
    p = c.page
    rpc_write(c, NEUTRAL)

    # 1. Ajustes ▸ Punto de venta ▸ Apariencia
    c.abrir('/odoo/settings#point_of_sale', ms=3000)
    title = p.locator('h2:has-text("Apariencia")').first
    title.evaluate("e => e.scrollIntoView({block: 'center'})")
    w(c, 600)
    box = c.js("""() => {
        const h = [...document.querySelectorAll('h2')].find(e => e.textContent.trim() === 'Apariencia');
        const r1 = h.getBoundingClientRect(), r2 = h.nextElementSibling.getBoundingClientRect();
        return {x: r1.x - 8, y: r1.y - 8, width: Math.max(r1.width, r2.width) + 16,
                height: r2.bottom - r1.y + 16};
    }""")
    c.foto('01-ajustes', clip=box)

    # 2. Pantalla de bloqueo con la marca neutra (logo de la compañía)
    abrir_tpv(c, desbloquear=False)
    c.foto('02-bloqueo', recortar=False)

    # 3-4. Venta: cuadrícula y lista con productos en la orden
    abrir_tpv(c)
    vista(c, lista=False)
    for nombre, veces in (('Gaseosa', 2), ('Libro educativo', 1)):
        for _ in range(veces):
            p.locator('.product-list article').filter(has_text=nombre).first.click()
            w(c, 600)
    c.foto('03-venta', recortar=False)
    vista(c, lista=True)
    c.foto('04-lista', recortar=False)

    # 5. Pago dentro del panel de la orden (sin cambiar de pantalla)
    p.locator('.pay-order-button').first.click()
    w(c, 2000)
    c.foto('05-pago', recortar=False)
    p.locator('[aria-label="Volver a la orden"]').first.click()
    w(c, 1200)

    # 6. Órdenes
    p.get_by_text('Órdenes', exact=True).first.click()
    w(c, 2500)
    c.foto('06-ordenes', recortar=False)

    # 8. Marca propia (ejemplo DEMO): nombre, logo de la compañía y colores
    rpc_write(c, DEMO_BRAND)
    abrir_tpv(c, desbloquear=False)
    c.foto('08-marca-propia-bloqueo', recortar=False)
    abrir_tpv(c)
    vista(c, lista=False)
    c.foto('09-marca-propia', recortar=False)
    vista(c, lista=True)          # preferencia del administrador: lista
    rpc_write(c, NEUTRAL)

# 7. Modo oscuro (preferencia del cajero, cookie del navegador)
with Captura('al_pos_theme', viewport=DESKTOP) as c:
    c.page.context.add_cookies([{'name': 'pos_color_scheme', 'value': 'dark', 'url': URL}])
    abrir_tpv(c)
    vista(c, lista=False)
    c.foto('07-oscuro', recortar=False)
    vista(c, lista=True)

# 10. Teléfono
with Captura('al_pos_theme', viewport=PHONE) as c:
    abrir_tpv(c)
    c.foto('10-movil', recortar=False)
