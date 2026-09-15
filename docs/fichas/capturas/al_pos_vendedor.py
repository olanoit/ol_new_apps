"""Capturas de la ficha de al_pos_vendedor.

Usa el punto de venta «DEMO TPV Vendedores» (copia del TPV de la compañía con
solo el método Tarjeta, sin comprobante electrónico y con seis vendedores
autorizados) y su propia sesión. Las tres ventas validadas que se ven en el
análisis (órdenes 44-46) se hicieron una sola vez; el guion no valida ventas
para no consumir numeración de boletas en cada ejecución.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

CONFIG = 23  # DEMO TPV Vendedores


def w(c, ms):
    c.page.wait_for_timeout(ms)


def entrar(c):
    p = c.page
    c.abrir('/pos/ui/%s' % CONFIG, ms=5000)
    for text in ('Desbloquear caja registradora', 'Abrir caja registradora'):
        if p.get_by_text(text, exact=True).count():
            p.get_by_text(text, exact=True).first.click()
            w(c, 3000)
    p.wait_for_selector('.product-list', timeout=60000)
    w(c, 1500)


def producto(c, nombre, veces=1):
    for _ in range(veces):
        c.page.locator('.pos-product-list-row, article.product').filter(
            has_text=nombre).first.click()
        w(c, 500)


def pagar(c):
    c.page.locator('button.pay-order-button').first.click()
    c.page.wait_for_selector('.payment-screen', timeout=20000)
    w(c, 1200)


def validar(c):
    c.page.locator('.payment-screen .button.next, .payment-screen button:has-text("Validar")').first.click()
    w(c, 2000)


def foto_ancha(c, name, selector, ancho=960, margen=40):
    """Diálogo estrecho con su entorno: la ficha muestra las imágenes a todo
    el ancho y un diálogo de 300 px recortado a secas quedaría gigante."""
    c.page.mouse.move(2, 2)
    c.page.wait_for_timeout(250)
    box = c.page.locator(selector).first.bounding_box()
    width = max(box['width'] + 2 * margen, ancho)
    x = max(box['x'] + box['width'] / 2 - width / 2, 0)
    clip = {'x': x, 'y': max(box['y'] - margen, 0), 'width': width,
            'height': box['height'] + 2 * margen}
    path = c.out / ('%s.png' % name)
    c.page.screenshot(path=str(path), clip=clip)
    print('captura', path.name)


def elegir(c, nombre):
    c.page.locator('.alv-card').filter(has_text=nombre).first.click()
    w(c, 800)


with Captura('al_pos_vendedor') as c:
    p = c.page

    # 1. Configuración del punto de venta: vendedores autorizados
    c.abrir('/odoo/action-point_of_sale.action_pos_config_kanban/%s' % CONFIG, ms=2500)
    c.foto('01-configuracion', selector='.o_form_view .o_form_sheet_bg')

    entrar(c)
    # Primera venta: 2 gaseosas + 1 libro
    producto(c, 'Gaseosa', 2)
    producto(c, 'Libro educativo')
    pagar(c)
    c.foto('02-pantalla-pago')

    # 2. Validar sin vendedor: el selector se abre solo; al cerrarlo, aviso
    validar(c)
    p.wait_for_selector('.alv-popup', timeout=10000)
    w(c, 600)
    p.locator('.alv-cancel').click()
    w(c, 1000)
    foto_ancha(c, '03-vendedor-requerido', '.modal-content')
    p.locator('.modal-footer button').first.click()
    w(c, 800)

    # 3. Selector: estrella de predeterminado en Quispe
    p.locator('.seller-button').click()
    w(c, 1000)
    p.locator('.alv-card').filter(has_text='Quispe').locator('.alv-star').click()
    w(c, 600)
    foto_ancha(c, '04-selector', '.modal-content')
    elegir(c, 'Quispe')

    # 4. Con vendedor asignado, el selector muestra el banner «Vendedor actual»
    p.locator('.seller-button').click()
    w(c, 1000)
    foto_ancha(c, '05-vendedor-actual', '.modal-content')
    p.locator('.alv-cancel').click()
    w(c, 600)

    # 5. Órdenes agrupadas por vendedor (incluye las tres ventas DEMO validadas:
    #    Quispe S/ 33,26, Flores S/ 18,73 y Torres S/ 50,00)
    c.abrir('/odoo/action-point_of_sale.action_pos_pos_form', ms=2500)
    c.clic('.o_searchview_dropdown_toggler', ms=800)
    p.locator('.o_add_custom_group_menu').select_option(label='Vendedor')
    c.esperar(1200)
    c.clic('.o_searchview_dropdown_toggler', ms=600)
    c.foto('06-ordenes-por-vendedor')

    # 6. Análisis de órdenes por vendedor (tabla dinámica)
    c.abrir('/odoo/action-point_of_sale.action_report_pos_order_all', ms=2500)
    c.clic('.o_switch_view.o_pivot', ms=2000)
    c.clic('.o_searchview_dropdown_toggler', ms=800)
    p.locator('.o_add_custom_group_menu').select_option(label='Vendedor')
    c.esperar(1200)
    c.clic('.o_searchview_dropdown_toggler', ms=600)
    c.clic('.o_pivot thead .o_pivot_header_cell_opened', ms=1500)
    c.foto('07-analisis')
