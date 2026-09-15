"""Capturas de la ficha de al_hr_pe_attendance (datos «DEMO FICHA HR1»).

Datos usados (todos DEMO): ciclos «DEMO FICHA HR1 …», la asignación 14×7 de
Huamán, los turnos publicados y las marcaciones del 1 al 14 de septiembre de
2026, el tareaje de ese avance (aplicado), la boleta DEMO de Rivas del 1 al 14
de septiembre, el rol «DEMO FICHA HR1 Vigilancia nocturna» con su plantilla de
22:00 a 06:00, un turno de reemplazo en borrador y la configuración de
fotocheck DEMO. No se guarda nada desde la interfaz: el ciclo ilegal se
descarta y el diálogo de ausencia se cierra sin guardar.
"""
import sys
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


MODULE = 'al_hr_pe_attendance'
CICLO = 1               # DEMO FICHA HR1 Atípico 14×7 — 10 horas
ASIGNACION = 2          # ciclo 14×7 de Huamán Torres Jorge Luis (octubre 2026)
TURNO_REEMPLAZO = 81    # Huamán cubre la falta de Salazar el 10/09/2026 (borrador)
TAREAJE = 149           # DEMO FICHA HR1 Tareaje septiembre 2026 (avance al 14), aplicado
PARAMETROS = 90         # Parámetros principales de Comercial Demo Perú S.A.C.
BOLETA_RIVAS = 3527     # Boleta 1–14 septiembre 2026 (tareaje) — Rivas
TIPO_AUSENCIA = 1       # Tiempo personal pagado (solo se mira, no se guarda)
FOTOCHECK = 1           # DEMO FICHA HR1 Fotocheck Comercial Demo
LUCIA, ANDREA = 2448, 2450


def columnas(c, etiquetas):
    """Activa columnas opcionales de la lista visible."""
    c.clic('.o_optional_columns_dropdown_toggle', ms=600)
    for label in etiquetas:
        c.page.locator('.o-dropdown--menu .o-checkbox:has-text("%s") input' % label).first.check()
        c.esperar(500)
    c.page.keyboard.press('Escape')
    c.esperar(500)


def buscar(c, texto):
    search = c.page.locator('.o_searchview_input')
    search.fill(texto)
    c.esperar(500)
    c.page.keyboard.press('Enter')
    c.esperar(1200)


def zona(c, name, top, bottom, margin=16):
    """Foto de la franja vertical entre dos elementos, a lo ancho de la hoja."""
    c.page.mouse.move(c.viewport['width'] - 2, c.viewport['height'] - 2)
    c.page.wait_for_timeout(250)
    sheet = c.page.locator('.o_form_sheet').first.bounding_box()
    t = top.first.bounding_box()
    b = bottom.first.bounding_box()
    clip = {'x': sheet['x'] - margin, 'y': max(t['y'] - margin, 0),
            'width': sheet['width'] + 2 * margin,
            'height': b['y'] + b['height'] - t['y'] + 2 * margin}
    return c.foto(name, clip=clip)


def abrir_monitor(c):
    c.abrir_accion('al_hr_pe_attendance.action_l10n_pe_hr_attendance_monitor', ms=1800)
    c.page.locator('.o_searchview_facet .o_facet_remove').first.click()
    c.esperar(900)
    buscar(c, 'DEMO FICHA HR1 Salazar')
    c.page.locator('.o_group_header').first.click()
    c.esperar(1200)


def paso_01(c):
    # 1. Roles de planificación con el tipo de turno peruano
    c.abrir_accion('planning.planning_action_roles', ms=1800)
    c.foto('01-roles')


def paso_02(c):
    # 2. Plantillas de turno con la marca de jornada nocturna
    c.abrir_accion('planning.planning_action_shift_template', ms=1800)
    c.foto('02-plantillas')


def paso_03(c):
    # 3. Ciclos atípicos con su control legal
    c.abrir_accion('al_hr_pe_attendance.action_l10n_pe_hr_shift_cycle', ms=1800)
    c.foto('03-ciclos')


def paso_04(c):
    # 4. Ficha de un ciclo
    c.abrir_registro('l10n_pe.hr.shift.cycle', CICLO, ms=1500)
    c.foto('04-ciclo', selector='.o_form_view .o_form_sheet_bg')


def paso_05(c):
    # 5. El validador rechaza un ciclo que supera las 48 h semanales
    c.abrir_accion('al_hr_pe_attendance.action_l10n_pe_hr_shift_cycle', ms=1500)
    c.clic('.o_control_panel_main_buttons button.o_list_button_add', ms=1500)
    c.page.locator('div[name=name] input').fill('DEMO FICHA HR1 Prueba 14×7 — 12 horas')
    c.page.locator('div[name=days_work] input').fill('14')
    c.page.locator('div[name=days_rest] input').fill('7')
    c.page.locator('div[name=hours_per_day] input').fill('12:00')
    c.page.locator('div[name=hours_per_day] input').press('Tab')
    c.esperar(600)
    c.clic('.o_form_button_save', ms=1500)
    c.foto('05-validacion', selector='.modal-content')
    # El ciclo inválido no se puede guardar: el paso siguiente sale de la
    # página y el borrador se pierde.


def paso_06(c):
    # 6. Asignación del ciclo a un trabajador
    c.abrir_registro('l10n_pe.hr.shift.cycle.assignment', ASIGNACION, ms=1800)
    c.foto('06-asignacion', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 400})


def paso_07(c):
    # 7. Turnos generados en la planificación nativa
    c.abrir_registro('l10n_pe.hr.shift.cycle.assignment', ASIGNACION, ms=1800)
    c.clic('button[name=action_view_slots]', ms=2000)
    c.foto('07-turnos', clip={'x': 0, 'y': 0, 'width': 1440, 'height': 480})


def paso_08(c):
    # 8. Turno con el rastro del reemplazo (grupo «Perú»)
    c.abrir_registro('planning.slot', TURNO_REEMPLAZO, ms=2000)
    c.foto('08-turno-reemplazo', selector='.o_form_view .o_form_sheet_bg')


def paso_09(c):
    # 9. Monitor de asistencia: planificado frente a marcado
    abrir_monitor(c)
    c.foto('09-monitor')


def paso_10(c):
    # 10. Registrar la ausencia desde la falta (no se guarda)
    abrir_monitor(c)
    c.page.locator('.o_data_row button[name=action_set_justificante]').first.click()
    c.esperar(1800)
    # Quita el foco del empleado: si no, su nombre sale seleccionado.
    c.page.evaluate("document.activeElement && document.activeElement.blur()")
    c.page.locator('.modal-content .modal-title').first.click()
    c.esperar(400)
    c.foto('10-registrar-ausencia', selector='.modal-content')
    c.page.keyboard.press('Escape')
    c.esperar(800)


def paso_11(c):
    # 11. Tipo de ausencia: casilla «Es vacaciones (Perú)» (solo se mira)
    c.abrir_registro('hr.leave.type', TIPO_AUSENCIA, ms=2000)
    campo = c.page.locator('.o_form_sheet div[name=l10n_pe_is_vacation]')
    campo.first.scroll_into_view_if_needed()
    c.esperar(400)
    label = c.page.locator('.o_form_sheet label:has-text("Es vacaciones (Perú)")')
    grupo = label.locator('xpath=ancestor::div[contains(@class,"o_inner_group")][1]')
    c.foto('11-tipo-ausencia', clip=(lambda b: {
        'x': b['x'] - 12, 'y': b['y'] - 12, 'width': b['width'] + 24,
        'height': b['height'] + 24})(grupo.first.bounding_box()))


def paso_12(c):
    # 12. Parámetros principales ▸ Tareaje
    c.abrir_registro('hr.main.parameter', PARAMETROS, ms=2000)
    c.page.locator('.o_notebook .nav-link:has-text("Tareaje")').first.click()
    c.esperar(900)
    notebook = c.page.locator('.o_notebook').first.bounding_box()
    sheet = c.page.locator('.o_form_sheet').first.bounding_box()
    c.foto('12-parametros-tareaje', clip={
        'x': sheet['x'], 'y': notebook['y'] - 8, 'width': sheet['width'],
        'height': notebook['height'] + 24})


def paso_13(c):
    # 13. «Sujeto a horas extras (PE)» en las versiones
    c.abrir('/odoo/action-hr.action_hr_version', ms=2000)
    buscar(c, 'DEMO FICHA HR1')
    columnas(c, ('Sujeto a horas extras (PE)',))
    c.foto('13-versiones-he', clip={'x': 0, 'y': 0, 'width': 1920, 'height': 300})


def paso_14(c):
    # 14. Lista de tareajes
    c.abrir_accion('al_hr_pe_attendance.hr_tareaje_manager_action', ms=1800)
    buscar(c, 'DEMO FICHA HR1')
    c.foto('14-tareajes')


def paso_15(c):
    # 15. Tareaje del periodo (aplicado)
    c.abrir_registro('hr.tareaje.manager', TAREAJE, ms=2000)
    columnas(c, ('Feriado/descanso laborado', 'HE 100 %'))
    c.foto('15-tareaje', selector='.o_form_view .o_form_sheet_bg')


def paso_16(c):
    # 16. Detalle diario de una trabajadora
    c.abrir_registro('hr.tareaje.manager', TAREAJE, ms=2000)
    c.page.locator('.o_data_row:has-text("Rivas") button[name=view_detail]').first.click()
    c.esperar(1800)
    columnas(c, ('Feriado/descanso laborado', 'HE 100 %'))
    c.foto('16-detalle')


def paso_17(c):
    # 17. La boleta lee el tareaje aplicado
    c.abrir_registro('hr.payslip', BOLETA_RIVAS, ms=2200)
    c.texto('Días trabajados', ms=900)
    c.foto('17-boleta-tareaje', selector='.o_form_view .o_form_sheet_bg')


def paso_18(c):
    # 18. Configuración de fotocheck de la compañía
    c.abrir_registro('hr.fotocheck.config', FOTOCHECK, ms=1800)
    c.foto('18-fotocheck-config', selector='.o_form_view .o_form_sheet_bg')


def paso_19(c):
    # 19. Reporte «Fotocheck (Perú)» desde el empleado
    c.abrir('/odoo/action-hr.open_view_employee_list_my?view_type=list', ms=2500)
    buscar(c, 'DEMO FICHA HR1')
    c.page.locator('.o_list_record_selector input').first.check()
    c.esperar(500)
    c.clic('.o_control_panel_actions button:has-text("Imprimir")', ms=700)
    c.foto('19-imprimir')
    c.page.keyboard.press('Escape')

    c.abrir('/report/html/al_hr_pe_attendance.report_hr_employee_fotocheck/%d,%d' % (LUCIA, ANDREA),
            ms=2500)
    c.foto('20-fotocheck', full_page=True)



VIEWPORTS = {
    'paso_12': {'width': 1440, 'height': 1500},
    'paso_13': {'width': 1920, 'height': 900},
}
PASOS = sorted(k for k in globals() if k.startswith('paso_'))

if __name__ == '__main__':
    elegidos = {int(a) for a in sys.argv[1:]}
    # Una sesión por paso: el paso 5 deja un formulario inválido sin guardar
    # y el navegador ya no sale de esa página.
    for nombre in PASOS:
        if not elegidos or int(nombre[5:]) in elegidos:
            print('>', nombre)
            viewport = VIEWPORTS.get(nombre)
            with Captura(MODULE, viewport=viewport) as c:
                globals()[nombre](c)
