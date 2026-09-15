"""Capturas de la ficha de al_hr_pe_benefits.

Datos: planilla de pruebas de «Comercial Demo Perú S.A.C.» (trabajadores
ficticios de docs/planillas/pruebas) y los datos «DEMO FICHA HR2»: lotes
de julio y agosto de 2026 de la trabajadora Salazar Ríos Andrea (provisión
51 y liquidación de cese 3), préstamo 27 y adelanto 1. Los asistentes se
abren y se cierran sin confirmar; no se genera ni exporta nada.

Uso: python capturas/al_hr_pe_benefits.py [nombre …] para repetir solo
algunas capturas.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

SOLO = set(sys.argv[1:])
SHEET = '.o_form_view .o_form_sheet_bg'


def quiero(nombre):
    return not SOLO or nombre in SOLO


def alto(c, h):
    c.page.set_viewport_size({'width': 1440, 'height': h})
    c.viewport = {'width': 1440, 'height': h}


with Captura('al_hr_pe_benefits') as c:
    # 01. Parámetros principales ▸ Beneficios sociales (cuatro primeros grupos)
    if quiero('01-parametros'):
        alto(c, 2000)
        c.abrir_registro('hr.main.parameter', 90, ms=2500)
        c.clic('.o_notebook_headers a[name=benefits]', ms=1000)
        pane = c.page.locator('.o_notebook .tab-content').first.bounding_box()
        stop = c.page.locator(
            '.tab-pane.active .o_horizontal_separator:has-text("Liquidación de cese")'
        ).first.bounding_box()
        c.foto('01-parametros', clip={
            'x': pane['x'], 'y': pane['y'] + 8, 'width': pane['width'],
            'height': stop['y'] - pane['y'] - 16})

    # 02. Parámetros principales ▸ Quinta categoría con los tramos
    if quiero('02-quinta-tramos'):
        alto(c, 1200)
        c.abrir_registro('hr.main.parameter', 90, ms=2500)
        c.clic('.o_notebook_headers a[name=fifth_category]', ms=1000)
        c.foto('02-quinta-tramos', selector='.o_notebook .tab-content')

    # 03-04. CTS: documento y línea. (El «Detalle histórico» no se captura:
    #        regenera las líneas de detalle de un registro real.)
    if quiero('03-cts'):
        alto(c, 900)
        c.abrir_registro('hr.cts', 50, ms=2000)
        c.foto('03-cts', selector=SHEET)
    if quiero('04-cts-trabajador'):
        alto(c, 1000)
        c.abrir_registro('hr.cts.line', 140, ms=2000)
        c.foto('04-cts-trabajador', selector=SHEET)

    # 06. Gratificación de Fiestas Patrias
    if quiero('06-gratificacion'):
        alto(c, 900)
        c.abrir_registro('hr.gratification', 20, ms=2000)
        c.foto('06-gratificacion', selector=SHEET)

    # 07-09. Renta de 5ta: afectos, excluidos y línea
    if quiero('07-renta-5ta') or quiero('08-renta-5ta-excluidos'):
        alto(c, 900)
        c.abrir_registro('hr.fifth.category', 1, ms=2000)
        c.foto('07-renta-5ta', selector=SHEET)
        c.clic('.o_notebook_headers a[name=excluidos]', ms=900)
        c.foto('08-renta-5ta-excluidos', selector=SHEET)
    if quiero('09-renta-5ta-linea'):
        alto(c, 1000)
        c.abrir_registro('hr.fifth.category.line', 81, ms=2000)
        c.foto('09-renta-5ta-linea', selector=SHEET)

    # 10-11. Liquidación de cese DEMO
    if quiero('10-liquidacion') or quiero('11-liquidacion-vacaciones'):
        alto(c, 900)
        c.abrir_registro('hr.liquidation', 3, ms=2000)
        c.foto('10-liquidacion', selector=SHEET)
        # Pestaña ancha: se reduce la escala para que quepa la columna Neto.
        c.clic('.o_notebook_headers a[name=vacation]', ms=900)
        c.page.locator('.tab-pane.active .o_list_renderer').first.evaluate(
            "e => e.style.zoom = '0.82'")
        c.esperar(500)
        c.foto('11-liquidacion-vacaciones', selector=SHEET)

    # 12. Provisión DEMO de julio
    if quiero('12-provisiones'):
        alto(c, 900)
        c.abrir_registro('hr.provisiones', 51, ms=2000)
        c.foto('12-provisiones', selector=SHEET)

    # 13. Subsidio: formulario nuevo (no hay subsidios registrados)
    if quiero('13-subsidio'):
        alto(c, 900)
        c.abrir('/odoo/hr.subsidies/new', ms=2500)
        c.foto('13-subsidio', selector=SHEET)

    # 14. Utilidades D.L. 892
    if quiero('14-utilidades'):
        alto(c, 1100)
        c.abrir_registro('hr.utilities', 9, ms=2000)
        c.foto('14-utilidades', selector=SHEET)

    # 15-16. Récord vacacional: asistente y saldos
    if quiero('15-record-vacacional'):
        alto(c, 900)
        c.abrir_accion('al_hr_pe_benefits.action_hr_vacation_rest_wizard', ms=2000)
        c.foto('15-record-vacacional', selector='.modal-content')
    if quiero('16-saldos-vacaciones'):
        alto(c, 900)
        c.abrir_accion('al_hr_pe_benefits.action_hr_vacation_rest', ms=2000)
        c.foto('16-saldos-vacaciones')

    # 17-18. Adelanto y préstamo DEMO
    if quiero('17-adelanto'):
        alto(c, 900)
        c.abrir_registro('hr.advance', 1, ms=2000)
        c.foto('17-adelanto', selector=SHEET)
    if quiero('18-prestamo'):
        alto(c, 900)
        c.abrir_registro('hr.loan', 27, ms=2000)
        c.foto('18-prestamo', selector=SHEET)

    # 19. Adelanto quincenal: formulario nuevo (no se generan boletas)
    if quiero('19-quincena'):
        alto(c, 900)
        c.abrir('/odoo/action-al_hr_pe_benefits.action_hr_fortnightly/new', ms=2500)
        c.foto('19-quincena', selector=SHEET)

    # 20. Menú del lote de nómina con las importaciones
    if quiero('20-lote-importar'):
        alto(c, 900)
        c.abrir_accion('hr_payroll.action_hr_payslip_run', ms=2500)
        card = c.page.locator(
            '.o_kanban_record:has-text("DEMO FICHA HR2 Planilla agosto 2026")').first
        card.locator('button.dropdown-toggle').first.click()
        c.esperar(900)
        menu = c.page.locator('.o-dropdown--menu').last
        mb = menu.bounding_box()
        cb = card.bounding_box()
        x = min(cb['x'], mb['x']) - 12
        y = min(cb['y'], mb['y']) - 12
        w = max(cb['x'] + cb['width'], mb['x'] + mb['width']) - x + 12
        h = max(cb['y'] + cb['height'], mb['y'] + mb['height']) - y + 12
        c.foto('20-lote-importar', clip={'x': max(x, 0), 'y': max(y, 0), 'width': w, 'height': h},
               recortar=False)
