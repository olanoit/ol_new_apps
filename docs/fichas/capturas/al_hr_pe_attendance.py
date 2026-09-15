"""Capturas de la ficha de al_hr_pe_attendance (datos «DEMO FICHA HR1»)."""
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
ASIGNACION = 2          # ciclo 14×7 de Huamán Torres Jorge Luis (octubre 2026)
TAREAJE = 149           # DEMO FICHA HR1 Tareaje septiembre 2026 (avance al 14)
LINEA_ANDREA = 76       # línea de Rivas Cárdenas Andrea
LUCIA = 2448


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


with Captura(MODULE) as c:
    # 1. Ciclos atípicos con su control legal
    c.abrir_accion('al_hr_pe_attendance.action_l10n_pe_hr_shift_cycle', ms=1800)
    c.foto('01-ciclos')

    # 2. El validador rechaza un ciclo que supera las 48 h semanales
    c.clic('.o_control_panel_main_buttons button.o_list_button_add', ms=1500)
    c.page.locator('div[name=name] input').fill('DEMO FICHA HR1 Prueba 14×7 — 12 horas')
    c.page.locator('div[name=days_work] input').fill('14')
    c.page.locator('div[name=days_rest] input').fill('7')
    c.page.locator('div[name=hours_per_day] input').fill('12:00')
    c.page.locator('div[name=hours_per_day] input').press('Tab')
    c.esperar(600)
    c.clic('.o_form_button_save', ms=1500)
    c.foto('02-validacion', selector='.modal-content')
    c.clic('.modal-footer button', ms=600)
    c.clic('.o_form_button_cancel', ms=1000)

    # 3. Asignación del ciclo a un trabajador
    c.abrir_registro('l10n_pe.hr.shift.cycle.assignment', ASIGNACION, ms=1800)
    c.foto('03-asignacion')

    # 4. Turnos generados en la planificación nativa
    c.clic('button[name=action_view_slots]', ms=2000)
    c.foto('04-turnos')

    # 5. Monitor de asistencia: planificado frente a marcado
    c.abrir_accion('al_hr_pe_attendance.action_l10n_pe_hr_attendance_monitor', ms=1800)
    c.page.locator('.o_searchview_facet .o_facet_remove').first.click()
    c.esperar(900)
    buscar(c, 'DEMO FICHA HR1 Salazar')
    c.page.locator('.o_group_header').first.click()
    c.esperar(1200)
    c.foto('05-monitor')

    # 6. Tareaje del periodo
    c.abrir_registro('hr.tareaje.manager', TAREAJE, ms=2000)
    columnas(c, ('Feriado/descanso laborado', 'HE 100 %'))
    c.foto('06-tareaje', selector='.o_form_view .o_form_sheet_bg')

    # 7. Detalle diario de una trabajadora
    c.abrir_registro('hr.tareaje.manager', TAREAJE, ms=1500)
    c.page.locator('.o_data_row:has-text("Rivas") button[name=view_detail]').first.click()
    c.esperar(1800)
    columnas(c, ('Feriado/descanso laborado', 'HE 100 %'))
    c.foto('07-detalle')

