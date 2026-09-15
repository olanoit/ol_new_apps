"""Capturas de la ficha de al_hr_pe_account.

Datos: planilla de pruebas de «Comercial Demo Perú S.A.C.» (trabajadores
ficticios de docs/planillas/pruebas) y los registros «DEMO FICHA HR2»:
lotes de julio y agosto de 2026 de la trabajadora DEMO, su provisión
(asiento PROVISION202607) y su liquidación de cese (asiento LIQUI202608).
Los asistentes sobre datos reales se abren y se cierran sin confirmar.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

PARAMETROS = 90           # Parámetros principales de la compañía de pruebas
REGLA_BASICO = 1255       # Regla BAS de la estructura BASE MG
AFILIACION = 2            # AFP INTEGRA
CTS = 50                  # CTS noviembre 2025 – abril 2026 (asiento CTS202604)
GRATIFICACION = 20        # Fiestas Patrias 2026 (asiento GRA202606)
PROVISION_REAL = 15       # Provisión de Planilla 2026-06 (borrador, sin asiento)
PROVISION_DEMO = 51       # Provisión DEMO de julio 2026 (asiento PROVISION202607)
LIQUIDACION_DEMO = 3      # Liquidación DEMO de agosto 2026 (asiento LIQUI202608)
ASIENTO_LOTE = 837        # PLA042026
ASIENTO_CTS = 838         # CTS202604
ASIENTO_GRA = 839         # GRA202606
ASIENTO_PROVISION = 2421  # PROVISION202607
ASIENTO_LIQUIDACION = 2422  # LIQUI202608


def con_botones(c, nombre):
    """Formulario con la barra de botones inteligentes (en v19 van en el
    panel de control, fuera de la hoja)."""
    hoja = c.page.locator('.o_form_view .o_form_sheet_bg').first.bounding_box()
    arriba = 50
    return c.foto(nombre, clip={'x': 0, 'y': arriba, 'width': c.viewport['width'],
                                'height': hoja['y'] + hoja['height'] - arriba})


def tamano(c, alto):
    c.viewport = {'width': 1440, 'height': alto}
    c.page.set_viewport_size(c.viewport)


with Captura('al_hr_pe_account') as c:
    # 1. Parámetros principales: pestaña Contabilidad (asiento de lote)
    c.abrir_registro('hr.main.parameter', PARAMETROS, ms=2500)
    c.clic('.o_notebook_headers a[name=account]', ms=900)
    c.foto('01-parametros-lote', selector='.o_notebook .tab-content')

    # 2. Parámetros principales: pestaña Contabilidad BBSS
    c.clic('.o_notebook_headers a[name=benefits_accounts]', ms=900)
    c.foto('02-parametros-bbss', selector='.o_notebook .tab-content')

    # 3. Regla salarial: cuentas de debe y haber y detalle por empleado
    c.abrir_registro('hr.salary.rule', REGLA_BASICO, ms=2500)
    c.page.locator('.o_notebook_headers a:has-text("Contabilidad")').first.click()
    c.esperar(900)
    c.foto('03-regla-cuentas', selector='.o_form_view .o_form_sheet_bg')

    # 4. Afiliación AFP con su cuenta contable
    c.abrir_registro('hr.membership', AFILIACION, ms=2500)
    c.foto('04-afiliacion', selector='.o_form_view .o_form_sheet_bg')

    # 5. Lote de nómina: «Asiento PE por lote» en el menú de la tarjeta
    tamano(c, 1000)
    c.abrir_accion('hr_payroll.action_hr_payslip_run', ms=2500)
    buscar = c.page.locator('.o_searchview_input').first
    buscar.fill('Planilla 2026-06')
    buscar.press('Enter')
    c.esperar(1500)
    card = c.page.locator('.o_kanban_record:has-text("Planilla 2026-06")').first
    card.locator('button.dropdown-toggle').first.click()
    c.esperar(900)
    box = card.bounding_box()
    menu = c.page.locator('.o-dropdown--kanban-record-menu').first.bounding_box()
    top = min(box['y'], menu['y']) - 12
    bottom = max(box['y'] + box['height'], menu['y'] + menu['height']) + 12
    c.foto('05-lote-menu', clip={'x': box['x'] - 12, 'y': top,
                                 'width': box['width'] + 24, 'height': bottom - top})
    c.page.keyboard.press('Escape')
    tamano(c, 900)

    # 6-7. Asistente del asiento de planilla por lote (previsualización)
    tamano(c, 1700)
    c.abrir_accion('al_hr_pe_account.hr_payslip_run_move_wizard_action', ms=2000)
    field = c.page.locator('.modal-dialog div[name=payslip_run_id] input').first
    field.fill('Planilla 2026-06')
    c.esperar(1200)
    c.page.locator('.o-autocomplete--dropdown-item:has-text("Planilla 2026-06")').first.click()
    c.esperar(2500)
    c.foto('06-asistente-lote', selector='.modal-content')
    c.clic('.modal-dialog div[name=with_analytic] input', ms=2500)
    modal = c.page.locator('.modal-content').first.bounding_box()
    c.foto('07-asistente-analitica', clip={'x': modal['x'], 'y': modal['y'],
                                           'width': modal['width'], 'height': 480})
    c.clic('.modal-footer button:has-text("Cancelar")', ms=800)

    # 8. Asiento de planilla del lote de abril (PLA042026)
    tamano(c, 1500)
    c.abrir_registro('account.move', ASIENTO_LOTE, ms=2500)
    hoja = c.page.locator('.o_form_view .o_form_sheet_bg').first.bounding_box()
    c.foto('08-asiento-lote', clip={'x': hoja['x'], 'y': hoja['y'],
                                    'width': hoja['width'], 'height': 1110})

    # 9-10. CTS con sus botones contables y su asiento
    tamano(c, 900)
    c.abrir_registro('hr.cts', CTS, ms=2000)
    con_botones(c, '09-cts')
    tamano(c, 1100)
    c.abrir_registro('account.move', ASIENTO_CTS, ms=2500)
    c.foto('10-asiento-cts', selector='.o_form_view .o_form_sheet_bg')

    # 11-12. Gratificación exportada con su asiento
    tamano(c, 900)
    c.abrir_registro('hr.gratification', GRATIFICACION, ms=2000)
    con_botones(c, '11-gratificacion')
    tamano(c, 1100)
    c.abrir_registro('account.move', ASIENTO_GRA, ms=2500)
    c.foto('12-asiento-gratificacion', selector='.o_form_view .o_form_sheet_bg')

    # 13. Asistente de la provisión mensual (sin generar)
    tamano(c, 900)
    c.abrir_registro('hr.provisiones', PROVISION_REAL, ms=2000)
    c.clic('.o_form_statusbar button[name=get_move_wizard]', ms=2000)
    c.foto('13-asistente-provision', selector='.modal-content')
    c.clic('.modal-footer button:has-text("Cancelar")', ms=800)

    # 14-15. Provisión DEMO contabilizada y su asiento
    c.abrir_registro('hr.provisiones', PROVISION_DEMO, ms=2000)
    con_botones(c, '14-provision-hecha')
    tamano(c, 1200)
    c.abrir_registro('account.move', ASIENTO_PROVISION, ms=2500)
    c.foto('15-asiento-provision', selector='.o_form_view .o_form_sheet_bg')

    # 16-17. Liquidación de cese DEMO: pestaña de asientos y asiento
    tamano(c, 900)
    c.abrir_registro('hr.liquidation', LIQUIDACION_DEMO, ms=2500)
    c.clic('.o_notebook_headers a[name=benefits_moves]', ms=900)
    con_botones(c, '16-liquidacion-asientos')
    tamano(c, 1100)
    c.abrir_registro('account.move', ASIENTO_LIQUIDACION, ms=2500)
    c.foto('17-asiento-liquidacion', selector='.o_form_view .o_form_sheet_bg')
