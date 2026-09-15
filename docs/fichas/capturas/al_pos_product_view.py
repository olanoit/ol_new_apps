"""Capturas de la ficha de al_pos_product_view.

Usa el punto de venta «DEMO TPV Vendedores» (id 23) y su sesión abierta. Los
seis productos del TPV de demostración ya llevan las etiquetas de ejemplo del
módulo. El conmutador guarda la vista preferida del usuario: el guion termina
en «Lista», que es la preferencia que tenía el administrador.

No se captura la ventana de información del producto: con `pos_hr` instalado
falla al abrirse (ver el informe de la ficha).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

CONFIG = 23


def w(c, ms):
    c.page.wait_for_timeout(ms)


def foto_ancha(c, name, selector, ancho=960, margen=40):
    c.page.mouse.move(2, 2)
    w(c, 250)
    box = c.page.locator(selector).first.bounding_box()
    width = max(box['width'] + 2 * margen, ancho)
    x = max(box['x'] + box['width'] / 2 - width / 2, 0)
    clip = {'x': x, 'y': max(box['y'] - margen, 0), 'width': width,
            'height': box['height'] + 2 * margen}
    path = c.out / ('%s.png' % name)
    c.page.screenshot(path=str(path), clip=clip)
    print('captura', path.name)


with Captura('al_pos_product_view') as c:
    p = c.page

    # 1. Ajustes del punto de venta
    c.abrir('/odoo/settings#point_of_sale', ms=3000)
    p.get_by_text('Vista de productos por defecto', exact=True).first.evaluate(
        "e => e.scrollIntoView({block: 'center'})")
    w(c, 600)
    c.foto('01-ajustes')

    # 2. Etiqueta con «Mostrar en la barra de filtros del TPV»
    c.abrir('/odoo/action-product.product_tag_action/5', ms=2500)
    c.foto('02-etiqueta', selector='.o_form_view .o_form_sheet_bg')

    # 3. Preferencia del usuario
    c.abrir('/odoo', ms=2000)
    p.locator('.o_user_menu button, .o_user_menu').first.click()
    w(c, 800)
    p.locator('.dropdown-item').filter(has_text='Preferencias').first.click()
    w(c, 2500)
    c.foto('06-preferencias', selector='.modal-content')

    # TPV
    c.abrir('/pos/ui/%s' % CONFIG, ms=5000)
    for text in ('Desbloquear caja registradora', 'Abrir caja registradora'):
        if p.get_by_text(text, exact=True).count():
            p.get_by_text(text, exact=True).first.click()
            w(c, 3000)
    p.wait_for_selector('.product-list', timeout=60000)
    w(c, 1500)
    if p.locator('.pos-product-list-row').count() == 0:
        p.locator('.pos-view-switch__btn').click()   # asegurar lista
        w(c, 1500)

    # Vista de lista con productos en el carrito
    for nombre, veces in (('Gaseosa', 2), ('Libro educativo', 1)):
        for _ in range(veces):
            p.locator('.pos-product-list-row').filter(has_text=nombre).first.click()
            w(c, 600)
    c.foto('05-lista')

    # Cuadrícula nativa con botones de información y chips
    p.locator('.pos-view-switch__btn').click()
    w(c, 1500)
    c.foto('03-cuadricula', selector='.rightpane')

    # Filtro por la etiqueta «Promoción»
    p.locator('.alpv-tag-chip').filter(has_text='Promoción').click()
    w(c, 1000)
    c.foto('04-filtro', selector='.rightpane')
    p.get_by_text('Limpiar', exact=True).click()
    w(c, 600)

    # Volver a lista: la preferencia del usuario queda como estaba
    p.locator('.pos-view-switch__btn').click()
    w(c, 1500)
