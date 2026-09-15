"""Capturas de la ficha de al_hr_pe_benefits.

Usa los datos de las pruebas funcionales de «Comercial Demo Perú S.A.C.»
(trabajadores ficticios de docs/planillas/pruebas) y un préstamo
«DEMO FICHA HR2».
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_hr_pe_benefits') as c:
    # 1. Parámetros principales: pestaña del motor de beneficios
    c.page.set_viewport_size({'width': 1440, 'height': 2000})
    c.abrir_registro('hr.main.parameter', 90, ms=2500)
    c.clic('.o_notebook_headers a[name=benefits]', ms=1000)
    # Solo los cuatro primeros grupos: CTS, gratificación, promedios y días.
    pane = c.page.locator('.o_notebook .tab-content').first.bounding_box()
    stop = c.page.locator(
        '.tab-pane.active .o_horizontal_separator:has-text("Liquidación de cese")'
    ).first.bounding_box()
    c.page.mouse.move(1438, 1998)
    c.page.screenshot(path=str(c.out / '01-parametros.png'), clip={
        'x': pane['x'], 'y': pane['y'] + 8, 'width': pane['width'],
        'height': stop['y'] - pane['y'] - 16})
    c.page.set_viewport_size({'width': 1440, 'height': 900})

    print('captura 01-parametros')

    # 2. CTS del semestre noviembre-abril
    c.abrir_registro('hr.cts', 50, ms=2000)
    c.foto('02-cts', selector='.o_form_view .o_form_sheet_bg')

    # 3. Detalle de la CTS de un trabajador
    c.abrir_registro('hr.cts.line', 140, ms=2000)
    c.foto('03-cts-trabajador', selector='.o_form_view .o_form_sheet_bg')

    # 4. Gratificación de Fiestas Patrias con bono extraordinario
    c.abrir_registro('hr.gratification', 20, ms=2000)
    c.foto('04-gratificacion', selector='.o_form_view .o_form_sheet_bg')

    # 5. Renta de 5ta categoría de junio
    c.abrir_registro('hr.fifth.category', 1, ms=2000)
    c.foto('05-renta-5ta', selector='.o_form_view .o_form_sheet_bg')

    # 6. Provisiones del mes
    c.abrir_registro('hr.provisiones', 15, ms=2000)
    c.foto('06-provisiones', selector='.o_form_view .o_form_sheet_bg')

    # 7. Utilidades D.L. 892
    c.page.set_viewport_size({'width': 1440, 'height': 1100})
    c.abrir_registro('hr.utilities', 9, ms=2000)
    c.foto('07-utilidades', selector='.o_form_view .o_form_sheet_bg')
    c.page.set_viewport_size({'width': 1440, 'height': 900})

    # 8. Préstamo con cronograma de cuotas
    c.abrir_registro('hr.loan', 27, ms=2000)
    c.foto('08-prestamo', selector='.o_form_view .o_form_sheet_bg')
