"""Capturas de la ficha de al_base_module_info (Aplicaciones)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

EJEMPLO = 'al_l10n_pe_retention'   # módulo con ficha ya generada


def buscar_apps(c, texto):
    c.abrir_accion('base.open_module_tree', ms=2500)
    for x in c.page.locator('.o_searchview_facet .o_facet_remove').all():
        x.click()
        c.esperar(600)
    inp = c.page.locator('.o_searchview_input')
    inp.fill(texto)
    inp.press('Enter')
    c.esperar(2000)


with Captura('al_base_module_info') as c:
    # 1. Tarjetas de Aplicaciones: con ficha y sin ficha
    buscar_apps(c, 'Perú')
    c.page.locator('.o_content').evaluate('e => e.scrollTop = 300')
    c.esperar(600)
    c.foto('01-aplicaciones')

    # 2. Menú de la tarjeta con la opción de la ficha
    card = c.page.locator('.o_kanban_record:has-text("PE - Letras de cambio")').first
    card.hover()
    c.esperar(300)
    card.locator('.o_dropdown_kanban button, .oe_kanban_action_dropdown, [title="Dropdown menu"]').first.click()
    c.esperar(700)
    box = card.bounding_box()
    menu = c.page.locator('.o-dropdown--menu').first.bounding_box()
    top = box['y'] - 16
    bottom = max(box['y'] + box['height'], menu['y'] + menu['height']) + 60
    c.page.mouse.move(1438, 898)
    c.page.wait_for_timeout(300)
    # Tres columnas de tarjetas: la imagen se muestra a todo el ancho de la
    # ficha y un recorte estrecho saldría ampliado y borroso.
    c.page.screenshot(path=str(c.out / '02-menu-tarjeta.png'), clip={
        'x': 220, 'y': top, 'width': 1220, 'height': bottom - top})
    print('captura 02-menu-tarjeta')
    c.page.keyboard.press('Escape')

    # 3. La ficha completa, tal como se abre en la pestaña nueva
    c.abrir('/%s/static/description/index.html' % EJEMPLO, ms=1500)
    c.foto('03-ficha-completa', recortar=False)

    # 4. La misma ficha dentro del formulario de Aplicaciones
    module_id = c.page.evaluate(
        """async (name) => {
            const r = await fetch('/web/dataset/call_kw', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                    model: 'ir.module.module', method: 'search',
                    args: [[['name', '=', name]]], kwargs: {}}})});
            return (await r.json()).result[0];
        }""", EJEMPLO)
    c.abrir('/odoo/action-base.open_module_tree/%s' % module_id, ms=2500)
    c.foto('04-ficha-en-aplicaciones', recortar=False)
