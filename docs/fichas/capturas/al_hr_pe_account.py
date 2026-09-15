"""Capturas de la ficha de al_hr_pe_account.

Usa la planilla de pruebas de «Comercial Demo Perú S.A.C.» (trabajadores
ficticios de docs/planillas/pruebas). No genera asientos: los asistentes se
abren y se cierran sin confirmar.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_hr_pe_account') as c:
    # 1. Parámetros principales: pestaña Contabilidad (asiento de lote)
    c.abrir_registro('hr.main.parameter', 90, ms=2500)
    c.clic('.o_notebook_headers a[name=account]', ms=900)
    c.foto('01-parametros-lote', selector='.o_notebook .tab-content')

    # 2. Parámetros principales: pestaña Contabilidad BBSS
    c.clic('.o_notebook_headers a[name=benefits_accounts]', ms=900)
    c.foto('02-parametros-bbss', selector='.o_notebook .tab-content')

    # 3. Asistente del asiento de planilla por lote (previsualización)
    c.page.set_viewport_size({'width': 1440, 'height': 1700})
    c.abrir_accion('al_hr_pe_account.hr_payslip_run_move_wizard_action', ms=2000)
    field = c.page.locator('.modal-dialog div[name=payslip_run_id] input').first
    field.fill('Planilla 2026-06')
    c.esperar(1200)
    c.page.locator('.o-autocomplete--dropdown-item:has-text("Planilla 2026-06")').first.click()
    c.esperar(2500)
    c.foto('03-asistente-lote', selector='.modal-content')
    c.clic('.modal-footer button:has-text("Cancelar")', ms=800)
    c.page.set_viewport_size({'width': 1440, 'height': 900})

    # 4. CTS con su asiento
    c.page.set_viewport_size({'width': 1440, 'height': 900})
    c.abrir_registro('hr.cts', 50, ms=2000)
    c.foto('04-cts-asiento', selector='.o_form_view .o_form_sheet_bg')

    # 5. Asiento de la CTS
    c.page.set_viewport_size({'width': 1440, 'height': 1500})
    c.abrir_registro('account.move', 838, ms=2500)
    c.foto('05-asiento-cts', selector='.o_form_view .o_form_sheet_bg')

    # 6. Asistente del asiento de provisiones (sin generar)
    c.page.set_viewport_size({'width': 1440, 'height': 900})
    c.abrir_registro('hr.provisiones', 15, ms=2000)
    c.clic('.o_form_statusbar button[name=get_move_wizard]', ms=2000)
    c.foto('06-asistente-provision', selector='.modal-content')
    c.clic('.modal-footer button:has-text("Cancelar")', ms=800)
