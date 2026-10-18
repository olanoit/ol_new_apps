"""Capturas de la ficha de al_l10n_pe_edi_purchase_settlement (datos de demostración,
cargados con al_l10n_pe_edi_purchase_settlement/tools/purchase_settlement_demo_data.py).
No envía nada a SUNAT: la liquidación queda «Por enviar»."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capturar  # noqa: E402
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_edi_purchase_settlement'
FORM = '.o_form_view .o_form_sheet_bg'
SETTLEMENT, DRAFT, JOURNAL, PRODUCT = 29158, 29159, 13193, 14004


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


def pestana_liquidacion(c):
    c.texto('Facturación PE', ms=1200)
    c.page.locator('a.nav-link:text-is("Liquidación de compra")').last.click()
    c.esperar(900)


with Captura(M) as c:
    # 1. Ajustes ▸ Perú ▸ Liquidación de compra electrónica
    c.abrir('/odoo/settings#al_account_base', ms=3000)
    foto_bloque(c, 'Liquidación de compra electrónica', '01-ajustes')

    # 2. Diario de liquidaciones con su serie
    c.abrir_registro('account.journal', JOURNAL, ms=2000)
    c.foto('02-diario', selector=FORM)

    # 3. Borrador: líneas con las retenciones añadidas solas
    c.abrir_registro('account.move', DRAFT, ms=2500)
    c.foto('03-borrador', selector=FORM)

    # 4. Liquidación confirmada, por enviar (botón «Enviar a SUNAT»)
    c.abrir_registro('account.move', SETTLEMENT, ms=2500)
    c.foto('04-confirmada', full_page=False)

    # 5. Facturación PE ▸ Liquidación de compra
    pestana_liquidacion(c)
    c.foto('05-pestana', selector=FORM)

    # 6. Asiento contable
    c.texto('Apuntes contables', ms=1500)
    c.foto('06-asiento', selector=FORM)

    # 7. Lista de liquidaciones (app Perú)
    c.abrir_accion(f'{M}.action_purchase_settlement', ms=2000)
    c.foto('07-lista', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 320})

    # 8. Representación impresa
    c.abrir(f'/report/html/{M}.report_purchase_settlement/{SETTLEMENT}', ms=2500)
    c.foto('08-pdf', full_page=True)

    # 9. Producto: oro con retención del 4 %
    c.abrir_registro('product.template', PRODUCT, ms=2000)
    c.page.locator('a.nav-link:text-is("Contabilidad")').first.click()
    c.esperar(1200)
    c.foto('09-producto', selector=FORM)
