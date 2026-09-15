"""Capturas de la ficha de al_l10n_pe_exchange_closure (datos «DEMO TC»).

No se pulsa «Traer T.C.»: si falta la tasa de la fecha intenta descargarla.
Se fotografían los cierres de junio y julio 2026 ya contabilizados."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402
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


with Captura('al_l10n_pe_exchange_closure') as c:
    # 1. Ajustes ▸ Perú: diario del cierre
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    foto_bloque(c, 'Cierre de tipo de cambio', '01-ajustes')

    # 2. Cuenta 1212000 marcada «con detalle» (pestaña Contabilidad)
    c.abrir_registro('account.account', 46, ms=2000)
    tab = c.page.locator('.o_notebook .nav-link:has-text("Contabilidad")')
    if tab.count():
        tab.first.click()
        c.esperar(700)
    c.foto('02-cuenta', selector='.o_form_view .o_form_sheet_bg')

    # 3. Cuentas que entran al cierre
    c.abrir_accion('al_l10n_pe_exchange_closure.action_account_exchange_closing',
                   ms=2000)
    c.foto('03-cuentas-cierre')
    shot = ROOT / c.module / 'static/description/screenshots/03-cuentas-cierre.png'
    Image.open(shot).crop((0, 0, 1440, 300)).save(shot, optimize=True)

    # 4. Lista de cierres mensuales
    c.abrir_accion('al_l10n_pe_exchange_closure.action_exchange_closure', ms=2000)
    c.foto('04-cierres')

    # 5-6. Más ancho: el detalle y el asiento tienen muchas columnas
    c.page.set_viewport_size({'width': 1920, 'height': 1100})
    c.viewport = {'width': 1920, 'height': 1100}

    # 5. Cierre de julio 2026 con su detalle por cuenta y socio
    c.abrir_registro('l10n_pe.exchange.closure', 30, ms=2500)
    c.foto('05-cierre-julio', selector='.o_form_view .o_form_sheet_bg')

    # 6. Asiento de ajuste generado
    c.clic('button[name=action_open_move]', ms=2500)
    c.foto('06-asiento', selector='.o_form_view .o_form_sheet_bg')
