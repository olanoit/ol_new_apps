"""Capturas de la ficha de al_hr_pe_import (datos «DEMO FICHA HR1»).

Importa de verdad, desde la interfaz, con los seis asistentes y solo sobre
registros DEMO:

* Inputs de boletas: novedades de agosto 2026 sobre el lote DEMO
  «DEMO FICHA HR1 Novedades agosto 2026» (antes se borran las entradas de
  esas boletas DEMO para que el resultado sea siempre el mismo).
* Datos PE de versiones: los mismos valores que ya tienen los tres
  trabajadores DEMO (se actualizan sin cambiar nada) y una fila errónea.
* Récord vacacional y Adelantos: saldos y adelantos de los trabajadores
  DEMO; se borran al terminar para no alterar otros módulos.
* Asistencias: marcaciones que ya existen (se actualizan sin cambios) y una
  fila errónea.
* Reglas salariales: sobre la estructura DEMO «DEMO FICHA HR1 Reglas
  importadas» (creada por odoo shell).

El historial de importaciones NO se borra: no hay forma de distinguir las
importaciones DEMO de las reales. Cada ejecución completa añade seis líneas.

Uso: ``python al_hr_pe_import.py [seccion ...]`` (sin argumentos, todas).
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura as _Captura  # noqa: E402

import openpyxl  # noqa: E402


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


MODULE = 'al_hr_pe_import'
LOTE = 'DEMO FICHA HR1 Novedades agosto 2026'
BOLETA_LUCIA = 3524
ESTRUCTURA = 'DEMO FICHA HR1 Reglas importadas'
DEMO = 'DEMO FICHA HR1'
SECCIONES = set(sys.argv[1:])


def quiero(nombre):
    return not SECCIONES or nombre in SECCIONES


FILAS_INPUTS = [
    ['NRO DOCUMENTO', 'CÓDIGO DE INPUT', 'MONTO'],
    ['72418305', 'COMI', 350],        # Salazar: comisiones
    ['70935214', 'ADELANTO', 400],    # Huamán: adelanto de remuneración
    ['75102846', 'BONI_EX', 500],     # Rivas: bonificación extraordinaria
    ['75102846', 'PREST', 180.255],   # Rivas: préstamo (redondeo SUNAT)
    ['70935214', 'HEX25', 150.50],    # código inexistente → error
    ['40000001', 'COMI', 120],        # documento sin boleta en el lote → error
]

# Mismos valores que ya tienen las versiones DEMO: se actualizan sin cambios.
FILAS_VERSIONES = [
    ['NRO DOCUMENTO', 'RÉGIMEN LABORAL', 'CUSPP', 'TIPO COMISIÓN AFP',
     'AFILIACIÓN (AFP/ONP)', 'SEGURO SOCIAL', 'TIPO TRABAJADOR (T08)',
     'SITUACIÓN (T15)', 'EXCEPCIÓN JORNADA (PLAME)', 'TIPO DE LABOR (PLAME)'],
    ['72418305', 'Régimen general', '612840LSQUI3', 'Comisión sobre flujo',
     'AFP INTEGRA', 'EsSalud', '21', '1', None, 'N'],
    ['70935214', 'general', None, None, 'ONP', 'EsSalud', 'EMPLEADO', '1', None, 'N'],
    ['75102846', 'general', '631520ARCAD7', 'mixed', 'AFP PRIMA', 'EsSalud', '21',
     'ACTIVO O SUBSIDIADO', None, 'N — Normal'],
    ['70935214', 'CAS', None, None, None, None, None, None, None, None],  # error
]

FILAS_VACACIONES = [
    ['FECHA DE APLICACIÓN', 'NRO DOCUMENTO', 'DÍAS DE SALDO', 'IMPORTE DE SALDO'],
    ['2026-01-01', '72418305', 12.5, 1166.67],
    ['2026-01-01', '70935214', 30, 1800],
    ['2026-01-01', '75102846', -2, -300],     # saldo negativo: ajuste de adelantos
    ['01/01/2026', '75102846', 5, 750],       # fecha en texto no ISO → error
]

FILAS_ADELANTOS = [
    ['NRO DOCUMENTO', 'TIPO DE ADELANTO', 'FECHA DE ADELANTO',
     'FECHA DE DESCUENTO', 'MONTO', 'OBSERVACIONES'],
    ['72418305', 'Adelanto de sueldo', '2026-10-05', '2026-10-31', 500,
     'DEMO FICHA HR1 solicitud del 04/10'],
    ['75102846', 'Adelanto de gratificación', '2026-10-10', '2026-12-15', 1200,
     'DEMO FICHA HR1 adelanto de gratificación'],
    ['70935214', 'Adelanto de movilidad', '2026-10-05', '2026-10-31', 150,
     'DEMO FICHA HR1 tipo inexistente'],       # error
]

# Marcaciones DEMO que ya existen (hora de Lima): se actualizan sin cambios.
FILAS_ASISTENCIAS = [
    ['EMPLEADO (nombre exacto o documento)', 'ENTRADA (check_in)', 'SALIDA (check_out)'],
    ['DEMO FICHA HR1 Salazar Quispe Lucía', '2026-09-01 08:00:00', '2026-09-01 13:00:00'],
    ['72418305', '2026-09-01 14:00:00', '2026-09-01 17:00:00'],
    ['75102846', '2026-09-01 08:00:00', '2026-09-01 13:00:00'],
    ['75102846', '2026-09-15 17:00:00', '2026-09-15 08:00:00'],   # salida anterior → error
]

FILAS_REGLAS = [
    ['CATEGORÍA (nombre o código)', 'COMPAÑÍA (informativa)', 'CÓDIGO', 'NOMBRE',
     'SECUENCIA', 'CÓDIGO PYTHON', 'CONDICIÓN PYTHON'],
    ['ING', '', 'DEMO_BAS', 'DEMO Básico', 1, 'result = contract.wage',
     "result = rules['NET']['total'] > categories['NET'] * 0.10"],
    ['APORTES TRABAJADOR', '', 'DEMO_ONP', 'DEMO Aporte ONP 13 %', 20,
     "result = -categories['ING'] * 0.13",
     "result = contract.retirement_fund == 'onp'"],
    ['BONOS', '', 'DEMO_BONO', 'DEMO Bono', 5, 'result = 100', ''],   # categoría inexistente
]


def rpc(c, model, method, args, kwargs=None):
    return c.page.evaluate(
        """async ([model, method, args, kwargs]) => {
            const r = await fetch('/web/dataset/call_kw', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                    model, method, args, kwargs}})});
            const j = await r.json();
            if (j.error) { throw new Error(JSON.stringify(j.error)); }
            return j.result;
        }""", [model, method, args, kwargs or {}])


def demo_employees(c):
    return rpc(c, 'hr.employee', 'search', [[['name', '=like', DEMO + ' %']]])


def limpiar_inputs(c):
    slips = rpc(c, 'hr.payslip', 'search', [[['payslip_run_id.name', '=', LOTE]]])
    inputs = rpc(c, 'hr.payslip.input', 'search', [[['payslip_id', 'in', slips]]])
    if inputs:
        rpc(c, 'hr.payslip.input', 'unlink', [inputs])


def limpiar_vacaciones_adelantos(c):
    """Solo lo que crea este guion sobre los trabajadores DEMO."""
    emps = demo_employees(c)
    rests = rpc(c, 'hr.vacation.rest', 'search', [[
        ['employee_id', 'in', emps], ['internal_motive', '=', 'rest'],
        ['date_aplication', '=', '2026-01-01']]])
    if rests:
        rpc(c, 'hr.vacation.rest', 'unlink', [rests])
    advances = rpc(c, 'hr.advance', 'search', [[
        ['employee_id', 'in', emps], ['observations', '=like', DEMO + ' %'],
        ['state', '=', 'not payed']]])
    if advances:
        rpc(c, 'hr.advance', 'unlink', [advances])


def excel(nombre, hoja, filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = hoja
    for fila in filas:
        ws.append(fila)
    path = Path(tempfile.mkdtemp()) / nombre
    wb.save(path)
    return path


def franja(c, name, height):
    c.page.mouse.move(c.viewport['width'] - 2, c.viewport['height'] - 2)
    c.page.wait_for_timeout(250)
    path = c.out / ('%s.png' % name)
    c.page.screenshot(path=str(path), clip={
        'x': 0, 'y': 0, 'width': c.viewport['width'], 'height': height})
    print('captura', path.name)


def importar(c, accion, archivo, antes=None, configurar=None, foto_archivo=None,
             foto_config=None, foto_progreso=None):
    """Recorre el asistente: archivo → Analizar → Configurar → Importar."""
    c.abrir_accion(accion, ms=1800)
    if antes:
        antes()
    c.page.locator('.modal-dialog div[name=file_data] input[type=file]').set_input_files(str(archivo))
    c.esperar(1500)
    if foto_archivo:
        c.foto(foto_archivo, selector='.modal-content')
    c.clic('.modal-footer button[name=action_load_file]', ms=2000)
    if configurar:
        configurar()
    if foto_config:
        c.foto(foto_config, selector='.modal-content')
    c.clic('.modal-footer button[name=action_run_import]', ms=1000)
    c.page.wait_for_selector('.modal-content :text("Importación completada")', timeout=60000)
    c.esperar(800)
    if foto_progreso:
        c.foto(foto_progreso, selector='.modal-content')


def many2one(c, field, texto, opcion):
    inp = c.page.locator('.modal-dialog div[name=%s] input' % field)
    inp.fill(texto)
    c.esperar(900)
    c.page.locator('.o-autocomplete--dropdown-item:has-text("%s")' % opcion).first.click()
    c.esperar(600)


# 1. Menú «Importar desde Excel»
if quiero('menu'):
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
    if quiero('inputs'):
        limpiar_inputs(c)
        importar(
            c, 'al_hr_pe_import.action_al_import_payslip_input_wizard',
            excel('novedades_agosto_2026.xlsx', 'INPUTS', FILAS_INPUTS),
            antes=lambda: many2one(c, 'payslip_run_id', 'DEMO FICHA HR1 Novedades', LOTE),
            foto_archivo='02-archivo', foto_config='03-configurar',
            foto_progreso='04-progreso')
        c.clic('.modal-content button:has-text("Listo")', ms=800)
        c.abrir_registro('hr.payslip', BOLETA_LUCIA, ms=2000)
        c.texto('Entradas salariales', ms=900)
        c.foto('05-boleta', selector='.o_form_view .o_form_sheet_bg')

    if quiero('versiones'):
        importar(
            c, 'al_hr_pe_import.action_al_import_hr_version_wizard',
            excel('datos_pe_versiones.xlsx', 'VERSIONES', FILAS_VERSIONES),
            foto_archivo='06-versiones-archivo', foto_progreso='07-versiones-resultado')
        c.clic('.modal-content button:has-text("Listo")', ms=800)

    if quiero('vacaciones'):
        limpiar_vacaciones_adelantos(c)
        importar(
            c, 'al_hr_pe_import.action_al_import_vacation_rest_wizard',
            excel('saldos_vacaciones.xlsx', 'VACACIONES', FILAS_VACACIONES),
            foto_config='08-vacaciones-configurar')
        c.clic('.modal-content button:has-text("Ver registros")', ms=2000)
        franja(c, '09-vacaciones-registros', 300)

    if quiero('adelantos'):
        importar(
            c, 'al_hr_pe_import.action_al_import_hr_advance_wizard',
            excel('adelantos_octubre.xlsx', 'ADELANTOS', FILAS_ADELANTOS),
            foto_config='10-adelantos-configurar')
        c.clic('.modal-content button:has-text("Ver registros")', ms=2000)
        franja(c, '11-adelantos-registros', 300)

    if quiero('vacaciones') or quiero('adelantos'):
        limpiar_vacaciones_adelantos(c)

    if quiero('asistencias'):
        c.abrir('/odoo/action-hr_attendance.hr_attendance_action?view_type=list', ms=2000)
        franja(c, '12-asistencias-lista', 330)
        c.clic('.o_control_panel button.o_al_import_payroll_btn', ms=1800)
        c.page.locator('.modal-dialog div[name=file_data] input[type=file]').set_input_files(
            str(excel('marcaciones_reloj.xlsx', 'MARCACIONES', FILAS_ASISTENCIAS)))
        c.esperar(1500)
        c.clic('.modal-footer button[name=action_load_file]', ms=2000)
        c.foto('13-asistencias-configurar', selector='.modal-content')
        c.clic('.modal-footer button[name=action_run_import]', ms=1000)
        c.page.wait_for_selector('.modal-content :text("Importación completada")', timeout=60000)
        c.esperar(800)
        c.foto('14-asistencias-resultado', selector='.modal-content')
        c.clic('.modal-content button:has-text("Listo")', ms=800)

    if quiero('reglas'):
        c.abrir_accion('hr_payroll.action_salary_rule_form', ms=2000)
        franja(c, '15-reglas-lista', 330)
        def estructura():
            many2one(c, 'struct_id', ESTRUCTURA, ESTRUCTURA)
        importar(
            c, 'al_hr_pe_import.action_al_import_hr_salary_rule_wizard',
            excel('reglas_v18.xlsx', 'REGLAS', FILAS_REGLAS),
            configurar=estructura, foto_config='16-reglas-configurar')
        c.clic('.modal-content button:has-text("Ver registros")', ms=2000)
        c.page.locator('.o_data_row:has-text("DEMO_ONP")').first.click()
        c.esperar(1800)
        c.foto('17-regla-adaptada', selector='.o_form_view .o_form_sheet_bg')

    if quiero('historial'):
        c.abrir_accion('al_hr_pe_import.action_al_import_payroll_progress', ms=1800)
        c.foto('18-historial')
