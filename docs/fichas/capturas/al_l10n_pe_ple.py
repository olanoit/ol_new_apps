"""Capturas de la ficha de al_l10n_pe_ple (datos «DEMO PLE», ejercicio 2026).

Solo lectura salvo el propio asistente «Exportar PLE» (modelo transitorio):
ningún paso modifica registros de la base.

La 22 es una hoja del Excel, no una pantalla: el bloque 5 la genera con
``odoo shell`` y LibreOffice (``soffice``) y no necesita el servidor web.
"""
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

ALTO = {'width': 1440, 'height': 1400}
# Bloques a ejecutar (todos por defecto): p. ej. ``... al_l10n_pe_ple.py 3 4``
BLOQUES = {int(a) for a in sys.argv[1:]} or {1, 2, 3, 4, 5}


def escoger_anio(c, boton, pasos=1):
    """Abre el filtro de fecha del informe y avanza el año."""
    c.clic('.o_control_panel button:has-text("%s")' % boton, ms=800)
    for _ in range(pasos):
        c.clic('.date_filter_year .btn_next_date', ms=2000)
    c.page.keyboard.press('Escape')
    c.esperar(1500)


def ajustes(c, bloque, nombre, alto):
    c.page.set_viewport_size({'width': 1440, 'height': alto})
    c.abrir('/odoo/settings#al_account_base', ms=2500)
    c.page.get_by_text(bloque, exact=True).first.evaluate(
        "e => e.scrollIntoView({block: 'start'})")
    c.esperar(600)
    c.foto(nombre)
    c.page.set_viewport_size(c.viewport)


if 1 in BLOQUES:
    with Captura('al_l10n_pe_ple', viewport=ALTO) as c:
        # 01. Ajustes ▸ Perú: formatos simplificados
        ajustes(c, 'Libros electrónicos PLE', '01-ajustes', 420)

        # 02. Clasificación RCE en el producto «DEMO PLE Producto Consignado»
        c.abrir_registro('product.template', 155, ms=2000)
        c.texto('Contabilidad')
        c.foto('02-producto-rce', selector='.o_form_view .o_form_sheet_bg')

        # 03. Asistente Exportar PLE con 7.1 y 4.1 generados (julio 2026)
        c.abrir_accion('al_l10n_pe_ple.action_ple_export_wizard', ms=2000)
        c.clic('.modal-dialog div[name=export_41] input', ms=600)
        c.clic('.modal-dialog div[name=month] input', ms=500)
        c.page.locator('.o_select_menu_item:has-text("07")').first.click()
        c.esperar(400)
        c.clic('.modal-dialog button[name=action_export]', ms=3000)
        c.foto('03-exportar-ple', selector='.modal-content')
        c.clic('.modal-header .btn-close', ms=800)

        # 04. El mismo asistente con el Libro 3 al 31/07/2026 (fecha de los
        # registros DEMO de 3.8 y 3.19): aparecen Fecha de los EEFF y Oportunidad
        c.abrir_accion('al_l10n_pe_ple.action_ple_export_wizard', ms=2000)
        c.clic('.modal-dialog div[name=export_71] input', ms=500)
        for campo in ('export_38', 'export_39', 'export_319'):
            c.clic('.modal-dialog div[name=%s] input' % campo, ms=500)
        # En Odoo 19 la fecha es un botón que se convierte en campo al pulsarlo
        c.clic('.modal-dialog div[name=balance_date] button', ms=800)
        fecha = c.page.locator('.modal-dialog div[name=balance_date] input').first
        fecha.fill('31/07/2026')
        fecha.press('Enter')
        c.esperar(600)
        c.clic('.modal-header', ms=600)
        c.clic('.modal-dialog button[name=action_export]', ms=3000)
        c.foto('04-exportar-libro3', selector='.modal-content')
        c.clic('.modal-header .btn-close', ms=800)

        # 05. Pestaña PLE SUNAT del activo en arrendamiento financiero
        c.abrir_registro('account.asset', 27, ms=2000)
        c.texto('PLE SUNAT')
        c.foto('05-activo-ple-sunat', selector='.o_form_view .o_form_sheet_bg')

        # 06. Pestaña PLE SUNAT del activo comprado en dólares (7.3)
        c.abrir_registro('account.asset', 28, ms=2000)
        c.texto('PLE SUNAT')
        c.foto('06-activo-moneda-extranjera', selector='.o_form_view .o_form_sheet_bg')

        # 16. Albarán marcado como consignación (Libro 9)
        c.abrir_registro('stock.picking', 176, ms=2000)
        c.foto('16-consignacion', selector='.o_form_view .o_form_sheet_bg')

if 2 in BLOQUES:
    with Captura('al_l10n_pe_ple', viewport={'width': 1440, 'height': 760}) as c:
        # 07. Registro de Activos Fijos en pantalla, con los botones del libro
        c.abrir_accion('al_l10n_pe_ple.action_report_ple_asset_7_1', ms=3000)
        escoger_anio(c, 'Al 31/12/2025')
        c.clic('.o_control_panel .fa-cog', ms=800)
        c.foto('07-libro7-pantalla')
        c.page.keyboard.press('Escape')
        c.esperar(500)

        # 08. El mismo informe, bloque de uso, método y depreciación
        c.js("document.querySelectorAll('*').forEach(e => {"
             " if (e.scrollWidth > e.clientWidth + 50"
             " && getComputedStyle(e).overflowX != 'visible') e.scrollLeft = 5000; })")
        c.esperar(600)
        c.foto('08-libro7-depreciacion')

if 3 in BLOQUES:
    with Captura('al_l10n_pe_ple', viewport={'width': 1440, 'height': 700}) as c:
        # 09-15. Listas de captura
        for nombre, accion in (
                ('09-retenciones-41', 'action_ple_withholding'),
                ('10-inversiones-38', 'action_ple_investment'),
                ('11-patrimonio-319', 'action_ple_equity'),
                ('12-costo-ventas-101', 'action_ple_cost_sales'),
                ('13-costos-102', 'action_ple_cost_element'),
                ('14-costo-produccion-103', 'action_ple_cost_production'),
                ('15-centros-costos-104', 'action_ple_cost_center')):
            c.abrir_accion('al_l10n_pe_ple.%s' % accion, ms=2000)
            c.foto(nombre)

if 4 in BLOQUES:
    with Captura('al_l10n_pe_ple') as c:
        # 19. Menú Libros PLE con el submenú de reportes nativos
        c.abrir_accion('al_l10n_pe_ple.action_ple_withholding', ms=2000)
        c.clic('.o_main_navbar button:has-text("Libros PLE"), '
               '.o_main_navbar a:has-text("Libros PLE")', ms=900)
        menu = c.page.locator('.o-dropdown--menu').first
        caja = menu.bounding_box()
        c.foto('19-menu-libros-ple', clip={
            'x': max(caja['x'] - 260, 0), 'y': 0,
            'width': caja['width'] + 520, 'height': caja['y'] + caja['height'] + 16})
        c.page.keyboard.press('Escape')

        # 17. RCE 8.4 (septiembre 2026, periodo por defecto) con los botones TXT y XLSX
        c.abrir_accion('al_l10n_pe_ple.action_report_ple_purchase_8_1', ms=3000)
        c.clic('.o_control_panel .fa-cog', ms=800)
        c.foto('17-rce-84')
        c.page.keyboard.press('Escape')

        # 18. RVIE 14.4 (septiembre 2026) con el botón XLSX RVIE 14.4
        c.abrir_accion('al_l10n_pe_ple.action_report_ple_sales_14_1', ms=3000)
        c.clic('.o_control_panel .fa-cog', ms=800)
        c.foto('18-rvie-144')
        c.page.keyboard.press('Escape')

        # 20. Libro Mayor: botones XLSX junto a los TXT del PLE
        c.abrir_accion('account_reports.action_account_report_general_ledger', ms=3000)
        c.clic('.o_control_panel .fa-cog', ms=800)
        caja = c.page.locator('.o-dropdown--menu').first.bounding_box()
        c.foto('20-libro-mayor-xlsx', clip={
            'x': 0, 'y': 0, 'width': 760, 'height': caja['y'] + caja['height'] + 12})
        c.page.keyboard.press('Escape')

        # 21. Asistente del inventario permanente con XLSX 12.1 y 13.1
        c.abrir_accion('al_l10n_pe_ple.action_ple_stock_wizard', ms=2500)
        c.page.keyboard.press('Escape')        # cierra el calendario
        c.page.locator('.modal-title').first.click()
        c.esperar(500)
        c.foto('21-inventario-xlsx', selector='.modal-content')

if 5 in BLOQUES:
    # 22. XLSX 13.1 de julio 2026 («Comercial Demo Perú S.A.C.»), apaisado y
    # recortado a sus primeras 12 columnas.
    from openpyxl import load_workbook
    from PIL import Image, ImageChops

    ODOO = Path('/home/och/odoo/ce19')
    destino = Path(__file__).resolve().parents[3] / 'al_l10n_pe_ple' / 'static' / 'description' / 'screenshots' / '22-excel-13-1.png'
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        xlsx = tmp / 'ple_13_1.xlsx'
        script = (
            "import base64\n"
            "company = env['res.company'].search([('name', '=', 'Comercial Demo Perú S.A.C.')], limit=1)\n"
            "env = env(context=dict(env.context, allowed_company_ids=company.ids))\n"
            "w = env['l10n_pe.stock.ple.wizard'].with_company(company).create("
            "{'date_from': '2026-07-01', 'date_to': '2026-07-31'})\n"
            "w.get_ple_xlsx_13_1()\n"
            "open(%r, 'wb').write(base64.b64decode(w.report_data))\n"
            "env.cr.rollback()\n" % str(xlsx))
        subprocess.run([str(ODOO / '.venv/bin/python'), 'odoo-bin', 'shell', '-c',
                        'cfg/my/pe.cfg', '-d', 'ol_pe_v19', '--no-http'],
                       input=script, text=True, cwd=ODOO, check=True,
                       capture_output=True)
        libro = load_workbook(xlsx)
        hoja = libro.active
        hoja.page_setup.orientation = 'landscape'
        hoja.page_setup.paperSize = hoja.PAPERSIZE_A3
        hoja.sheet_properties.pageSetUpPr.fitToPage = True
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0
        hoja.page_margins.left = hoja.page_margins.right = hoja.page_margins.top = 0.2
        impresion = tmp / 'impresion.xlsx'
        libro.save(impresion)
        subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', str(tmp),
                        str(impresion)], check=True, capture_output=True)
        subprocess.run(['pdftoppm', '-png', '-r', '200', '-f', '1', '-l', '1',
                        str(tmp / 'impresion.pdf'), str(tmp / 'pagina')], check=True)
        imagen = Image.open(tmp / 'pagina-1.png').convert('RGB')
        borde = ImageChops.difference(imagen, Image.new('RGB', imagen.size, 'white')).getbbox()
        imagen = imagen.crop((max(borde[0] - 12, 0), max(borde[1] - 12, 0),
                              min(borde[2] + 12, imagen.width), min(borde[3] + 12, imagen.height)))
        imagen = imagen.crop((0, 0, int(imagen.width * 0.46), imagen.height))
        imagen = imagen.resize((1100, int(imagen.height * 1100 / imagen.width)), Image.LANCZOS)
        imagen.save(destino, optimize=True)
        print('captura', destino.name)
