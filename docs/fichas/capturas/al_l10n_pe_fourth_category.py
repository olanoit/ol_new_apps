"""Capturas de la ficha de al_l10n_pe_fourth_category (datos de demostración,
cargados con al_l10n_pe_fourth_category/tools/fourth_category_demo_data.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capturar  # noqa: E402
from capturar import Captura  # noqa: E402

M = 'al_l10n_pe_fourth_category'
FORM = '.o_form_view .o_form_sheet_bg'
RECEIPT, PROVIDER_SUSPENDED = 28788, 24841



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


with Captura(M) as c:
    # 1. Recibo por honorarios con retención: Contabilidad PE ▸ Renta de 4.ª
    c.abrir_registro('account.move', RECEIPT, ms=2500)
    c.texto('Contabilidad PE', ms=1200)
    c.page.locator('a.nav-link:text-is("Renta de 4.ª categoría")').last.click()
    c.esperar(900)
    c.foto('01-recibo', selector=FORM)

    # 2. Recibos por honorarios del periodo
    c.abrir_accion(f'{M}.action_fourth_category_receipts', ms=2000)
    c.foto('02-recibos', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 360})

    # 3. Suspensiones de retención (Formulario 1609)
    c.abrir_accion(f'{M}.action_fourth_category_suspension', ms=2000)
    c.texto('TORRES PAZ LUIS', ms=1500)
    c.foto('03-suspension', selector=FORM)

    # 4. Retenciones del mes para la PLAME
    c.abrir_accion(f'{M}.action_fourth_category_report', ms=2000)
    # Año y mes por defecto: los del día (octubre de 2026 en los datos demo).
    c.texto('Calcular', ms=2500)
    c.texto('Generar archivo .4ta', ms=2000)
    c.foto('04-plame', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(600)

    # 5. Certificado de rentas y retenciones
    c.abrir(f'/report/html/{M}.report_certificate/{PROVIDER_SUSPENDED - 1}', ms=2500)
    c.foto('05-certificado', full_page=True)

    # 6. Ajustes ▸ Perú ▸ Renta de 4.ª categoría
    c.abrir('/odoo/settings#al_account_base', ms=3000)
    foto_bloque(c, 'Renta de 4.ª categoría', '06-ajustes')
