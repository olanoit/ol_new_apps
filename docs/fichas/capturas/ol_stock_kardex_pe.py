"""Capturas de la ficha de ol_stock_kardex_pe (movimientos de julio 2026).

La imagen del PDF sale del kardex generado en segundo plano (registro 3 de
«Kardex generados»), rasterizado con ``pdftoppm``.
"""
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import URL, Captura  # noqa: E402

PDF_REPORT_ID = 3
ARROZ_TMPL_ID = 33

with Captura('ol_stock_kardex_pe', viewport={'width': 1440, 'height': 1000}) as c:
    # 1. Asistente: formato 13.1, julio 2026
    c.abrir_accion('ol_stock_kardex_pe.action_l10n_pe_kardex_wizard', ms=2000)
    c.clic('.modal-dialog div[name=month] input', ms=500)
    c.page.locator('.o_select_menu_item:has-text("Julio")').first.click()
    c.esperar(400)
    year = c.page.locator('.modal-dialog div[name=year] input')
    year.fill('2026')
    year.press('Tab')
    c.esperar(500)
    c.foto('01-generar', selector='.modal-content')

    # 2. Ver en pantalla: saldo corrido por producto
    # Sin agrupar: las filas de grupo suman costos unitarios y saldos, que no
    # tienen sentido como total. Se abre la misma lista (mismo dominio y
    # contexto del botón «Ver en pantalla») sin agrupar y con dos productos.
    c.clic('.modal-header .btn-close', ms=800)
    c.js("""odoo.__WOWL_DEBUG__.root.env.services.action.doAction({
        type: 'ir.actions.act_window', name: 'Kardex 13.1 (2026-07-01 a 2026-07-31)',
        res_model: 'l10n_pe.kardex.line', views: [[false, 'list']],
        domain: [['date', '>=', '2026-07-01'], ['date', '<=', '2026-07-31 23:59:59'],
                 ['product_id.default_code', 'in', ['ACE-001', 'ARR-001']]],
        context: {kardex_physical: false, kardex_by_warehouse: false},
    })""")
    c.esperar(2500)
    c.foto('02-en-pantalla')

    # 3. Kardex generados en segundo plano
    c.abrir_accion('ol_stock_kardex_pe.action_l10n_pe_kardex_report', ms=2000)
    c.foto('03-generados')

    # 4. PDF del formato 13.1 (bloque de un producto)
    respuesta = c.page.request.get(
        '%s/web/content/l10n_pe.kardex.report/%s/output_file' % (URL, PDF_REPORT_ID))
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / 'kardex.pdf'
        pdf.write_bytes(respuesta.body())
        subprocess.run(['pdftoppm', '-r', '150', '-f', '1', '-l', '1', '-png',
                        str(pdf), str(Path(tmp) / 'k')], check=True)
        from PIL import Image
        image = Image.open(next(Path(tmp).glob('k-*.png')))
        escala = image.size[1] / 662.0
        recorte = image.crop((int(25 * escala), int(185 * escala),
                              int(915 * escala), int(362 * escala)))
        destino = c.out / '04-pdf-131.png'
        recorte.save(destino, optimize=True)
        print('captura', destino)

    # 5. Botón «Ver Kardex» en el producto
    c.abrir_registro('product.template', ARROZ_TMPL_ID, ms=2000)
    c.foto('05-ver-kardex', selector='.o_form_view .o_form_sheet_bg')
