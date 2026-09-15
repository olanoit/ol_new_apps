"""Capturas de la ficha de l10n_pe_vat_sunat.

Solo se fotografían formularios y datos ya guardados: no se pulsa ningún botón
que consulte una API (RUC/DNI, padrón SUNAT)."""
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


with Captura('l10n_pe_vat_sunat', viewport={'width': 1440, 'height': 1250}) as c:
    # 1. Ajustes ▸ Perú: bloque «Validación RUC/DNI (PE)»
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    foto_bloque(c, 'Validación RUC/DNI (PE)', '01-ajustes')

    # 2. Conexiones de la compañía, por prioridad (botón de los ajustes)
    c.clic('button[name=action_open_pe_api_connections]', ms=2000)
    c.foto('02-conexiones')

    # 3. Conexión REST con su mapeo de campos (Decolecta)
    c.abrir_registro('l10n_pe.api.connection', 35, ms=2000)
    c.foto('03-conexion-mapeo', selector='.o_form_view .o_form_sheet_bg')

    # 4. Conexión SUNAT (scraping) con importación de representantes y anexos
    c.abrir_registro('l10n_pe.api.connection', 3, ms=2000)
    c.foto('04-conexion-sunat', selector='.o_form_view .o_form_sheet_bg')

    # 5. Contacto con los datos devueltos: estado, condición y padrón
    c.abrir_registro('res.partner', 4645, ms=2000)
    c.foto('05-contacto', selector='.o_form_view .o_form_renderer')

    # 6. Padrón SUNAT agrupado por tipo
    c.abrir('/odoo/action-l10n_pe_vat_sunat.action_l10n_pe_sunat_padron?menu_id=%d' % c.js(
        "async () => { const r = await fetch('/web/dataset/call_kw', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {model: 'ir.model.data', method: 'search_read', args: [[['module', '=', 'al_account_base'], ['name', '=', 'al_l10n_pe_root']], ['res_id']], kwargs: {}}})}); return (await r.json()).result[0].res_id; }"), ms=2000)
    c.clic('.o_searchview_dropdown_toggler', ms=700)
    c.clic('.o-dropdown-item:text-is("Tipo de padrón")', ms=1500)
    c.clic('.o_searchview_dropdown_toggler', ms=700)
    c.clic('.o_group_name:has-text("Agente de retención")', ms=1800)
    c.foto('06-padron')
    recorte = ROOT / c.module / 'static/description/screenshots/06-padron.png'
    from PIL import Image
    Image.open(recorte).crop((0, 0, 1440, 470)).save(recorte, optimize=True)
