"""Capturas de la ficha de al_l10n_pe_financial_reports.

Compañía «Comercial Demo Perú S.A.C.», ejercicio 2026 (periodo por defecto).
Solo lectura: no modifica registros.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

ACCION = 'al_l10n_pe_financial_reports.pe_action_statement_changes_equity'

with Captura('al_l10n_pe_financial_reports') as c:
    # 01. App Perú ▸ Estados financieros (se entra por una acción de la app)
    c.abrir_accion('al_l10n_pe_ple.action_ple_withholding', ms=2000)
    c.clic('.o_main_navbar button:has-text("Estados financieros"), '
           '.o_main_navbar a:has-text("Estados financieros")', ms=900)
    menu = c.page.locator('.o-dropdown--menu').first.bounding_box()
    c.foto('01-menu-estados-financieros', clip={
        'x': max(menu['x'] - 260, 0), 'y': 0,
        'width': menu['width'] + 520, 'height': menu['y'] + menu['height'] + 16})
    c.page.keyboard.press('Escape')

with Captura('al_l10n_pe_financial_reports', viewport={'width': 1440, 'height': 1100}) as c:
    # 02. 3.19 del ejercicio 2026
    c.abrir_accion(ACCION, ms=3500)
    c.foto('02-estado-cambios-patrimonio')

    # 03. Líneas editables del saldo inicial
    c.abrir_accion(ACCION, ms=3000)
    c.clic('text=Saldos al inicio del periodo', ms=1200)
    c.foto('03-lineas-editables', clip={'x': 300, 'y': 180, 'width': 840, 'height': 200})
