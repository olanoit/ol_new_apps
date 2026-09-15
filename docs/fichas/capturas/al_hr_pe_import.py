"""Capturas de la ficha de al_hr_pe_import (datos «DEMO FICHA HR1»).

Importa de verdad, desde la interfaz, las novedades de agosto 2026 sobre el
lote DEMO «DEMO FICHA HR1 Novedades agosto 2026» (boletas en borrador de los
tres trabajadores DEMO). Incluye dos filas erróneas a propósito. Antes de
importar borra, por RPC, las entradas de esas boletas DEMO (el historial de
importaciones no se toca), para que el resultado sea siempre el mismo.
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura as _Captura  # noqa: E402


class Captura(_Captura):
    """Navegador en hora de Lima: el cliente web muestra las fechas con la
    zona horaria del navegador y el ayudante no la fija."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        from capturar import CHROME
        self.browser = self._pw.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
        context = self.browser.new_context(viewport=self.viewport, timezone_id='America/Lima',
                                           locale='es-PE')
        self.page = context.new_page()
        self.page.set_default_timeout(20000)
        self.login()
        return self


import openpyxl  # noqa: E402

MODULE = 'al_hr_pe_import'
LOTE = 'DEMO FICHA HR1 Novedades agosto 2026'
BOLETA_LUCIA = 3524

FILAS = [
    ['NRO DOCUMENTO', 'CÓDIGO DE INPUT', 'MONTO'],
    ['72418305', 'COMI', 350],        # Salazar: comisiones
    ['70935214', 'ADELANTO', 400],    # Huamán: adelanto de remuneración
    ['75102846', 'BONI_EX', 500],     # Rivas: bonificación extraordinaria
    ['75102846', 'PREST', 180.255],   # Rivas: préstamo (redondeo SUNAT)
    ['70935214', 'HEX25', 150.50],    # código inexistente → error
    ['40000001', 'COMI', 120],        # documento sin boleta en el lote → error
]


def rpc(c, model, method, args):
    return c.page.evaluate(
        """async ([model, method, args]) => {
            const r = await fetch('/web/dataset/call_kw', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                    model, method, args, kwargs: {}}})});
            const j = await r.json();
            if (j.error) { throw new Error(JSON.stringify(j.error)); }
            return j.result;
        }""", [model, method, args])


def limpiar(c):
    slips = rpc(c, 'hr.payslip', 'search', [[['payslip_run_id.name', '=', LOTE]]])
    inputs = rpc(c, 'hr.payslip.input', 'search', [[['payslip_id', 'in', slips]]])
    if inputs:
        rpc(c, 'hr.payslip.input', 'unlink', [inputs])
    # El historial de importaciones NO se borra: no hay forma de distinguir las
    # importaciones DEMO de las reales, y la regla es no tocar datos ajenos.


def excel():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'INPUTS'
    for fila in FILAS:
        ws.append(fila)
    path = Path(tempfile.mkdtemp()) / 'novedades_agosto_2026.xlsx'
    wb.save(path)
    return path


def lista(c, name, height=None):
    c.page.mouse.move(c.viewport['width'] - 2, c.viewport['height'] - 2)
    c.page.wait_for_timeout(250)
    path = c.out / ('%s.png' % name)
    c.page.screenshot(path=str(path), clip={
        'x': 0, 'y': 0, 'width': c.viewport['width'], 'height': height})
    print('captura', path.name)


# 1. Menú «Importar desde Excel»
with Captura(MODULE, viewport={'width': 1920, 'height': 900}) as c:
    c.abrir_accion('al_hr_pe_import.action_al_import_payroll_progress', ms=1500)
    c.clic('[data-menu-xmlid="al_hr_pe_import.menu_al_hr_pe_import_root"]', ms=800)
    menu = c.page.locator('.o-dropdown--menu').first.bounding_box()
    c.page.mouse.move(300, 850)
    c.page.wait_for_timeout(250)
    path = c.out / '01-menu.png'
    c.page.screenshot(path=str(path), clip={
        'x': menu['x'] - 700, 'y': 0, 'width': menu['width'] + 900,
        'height': menu['y'] + menu['height'] + 16})
    print('captura', path.name)

with Captura(MODULE) as c:
    limpiar(c)

    # 2. Paso 1: lote y archivo
    c.abrir_accion('al_hr_pe_import.action_al_import_payslip_input_wizard', ms=1800)
    run = c.page.locator('.modal-dialog div[name=payslip_run_id] input')
    run.fill('DEMO FICHA HR1 Novedades')
    c.esperar(900)
    c.page.locator('.o-autocomplete--dropdown-item:has-text("%s")' % LOTE).first.click()
    c.esperar(600)
    c.page.locator('.modal-dialog div[name=file_data] input[type=file]').set_input_files(str(excel()))
    c.esperar(1500)
    c.foto('02-archivo', selector='.modal-content')

    # 3. Paso 2: hoja detectada y opciones
    c.clic('.modal-footer button[name=action_load_file]', ms=2000)
    c.foto('03-configurar', selector='.modal-content')

    # 4. Progreso en vivo hasta completar
    c.clic('.modal-footer button[name=action_run_import]', ms=1000)
    c.page.wait_for_selector('.modal-content :text("Importación completada")', timeout=60000)
    c.esperar(800)
    c.foto('04-progreso', selector='.modal-content')
    c.clic('.modal-content button:has-text("Listo")', ms=800)

    # 5. Historial de importaciones
    c.abrir_accion('al_hr_pe_import.action_al_import_payroll_progress', ms=1800)
    lista(c, '05-historial', height=260)

    # 6. Las novedades en la boleta
    c.abrir_registro('hr.payslip', BOLETA_LUCIA, ms=2000)
    c.texto('Entradas salariales', ms=900)
    c.foto('06-boleta', selector='.o_form_view .o_form_sheet_bg')

    # 7. Botón «Importar desde Excel» en la lista de asistencias
    c.abrir('/odoo/action-hr_attendance.hr_attendance_action?view_type=list', ms=2000)
    lista(c, '07-asistencias', height=330)
