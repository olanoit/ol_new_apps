"""Capturas de la ficha de al_l10n_pe_currency.

No se pulsa ningún botón que descargue tipos de cambio (SUNAT, BCRP,
Decolecta, apis.net.pe): se fotografían las tasas ya registradas y los
formularios antes de aceptar."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura, ROOT, _recortar_fondo  # noqa: E402


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
    path = ROOT / c.module / 'static/description/screenshots' / ('%s.png' % nombre)
    c.page.screenshot(path=str(path), clip=box)
    _recortar_fondo(path)
    print('captura', path.relative_to(ROOT))


with Captura('al_l10n_pe_currency') as c:
    # 1. Ajustes ▸ Contabilidad: criterio de compra o venta por sentido
    c.abrir('/odoo/settings#account', ms=2500)
    foto_bloque(c, 'Tipo de cambio (Perú)', '01-ajustes')

    # 2. Perú ▸ Tipo de cambio ▸ Tipos de cambio (compra, venta y origen)
    c.abrir_accion('al_l10n_pe_currency.action_l10n_pe_currency_rate', ms=2000)
    c.foto('02-tipos-de-cambio')

    # 3. Moneda USD con los botones de actualización
    usd = c.js("""async () => {
        const r = await fetch('/web/dataset/call_kw', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                model: 'res.currency', method: 'search',
                args: [[['name', '=', 'USD']]], kwargs: {}}})});
        return (await r.json()).result[0];
    }""")
    c.abrir_registro('res.currency', usd, ms=2000)
    c.foto('03-moneda-usd', selector='.o_form_view .o_form_view_container')

    # 4. Asistente «Actualizar tipo de cambio» por mes (sin aceptar)
    c.abrir_accion('al_l10n_pe_currency.action_l10n_pe_exchange_rate_wizard',
                   ms=2000)
    c.page.locator('.modal-dialog div[name=range] input[data-value=month]').first.check()
    c.esperar(1200)
    c.foto('04-asistente', selector='.modal-content')
    c.clic('.modal-header .btn-close', ms=800)

    # 5. Factura en dólares: tipo de T.C. y T.C. aplicado con su fecha
    # (más ancho: el T.C. aplicado va en una sola línea junto a la moneda)
    c.page.set_viewport_size({'width': 1920, 'height': 1000})
    c.viewport = {'width': 1920, 'height': 1000}
    c.abrir_registro('account.move', 65, ms=2500)
    c.js("() => document.querySelectorAll('.o_form_view .alert-danger').forEach(e => e.remove())")
    c.esperar(400)
    c.foto('05-factura-usd', selector='.o_form_view .o_form_sheet_bg')

    # 6. Asistente de pago con su propio tipo de T.C. (sin registrar).
    # Se recarga la factura: quitar el aviso del DOM rompe el formulario.
    c.abrir_registro('account.move', 65, ms=2500)
    c.clic('.o_form_statusbar button[name=action_register_payment]', ms=4000)
    c.js('() => document.activeElement.blur()'); c.esperar(400)
    c.foto('06-registrar-pago', selector='.modal-content')
    c.page.keyboard.press('Escape')
