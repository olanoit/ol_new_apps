"""Capturas de la ficha de al_hr_pe_public_holidays (datos «DEMO FICHA HR1»).

Los feriados de 2026 están aplicados solo al calendario DEMO
«DEMO FICHA HR1 Jornada 48h»: el botón «Aplicar a los calendarios» no se
pulsa aquí porque escribiría en todos los calendarios de la compañía. El
formulario de medio día se abre como registro nuevo y se descarta sin guardar.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

MODULE = 'al_hr_pe_public_holidays'
JUNIN_2026 = 11        # Batalla de Junín, 06/08/2026
DESCANSO_JUNIN = 57    # su descanso en «DEMO FICHA HR1 Jornada 48h»
CRON = 55              # Peru Holidays: Yearly Auto Apply
BOLETA_JULIO = 3521    # DEMO FICHA HR1 Salazar Quispe Lucía, julio 2026


def franja(c, name, height, width=None):
    c.page.mouse.move(c.viewport['width'] - 2, c.viewport['height'] - 2)
    c.page.wait_for_timeout(250)
    path = c.out / ('%s.png' % name)
    c.page.screenshot(path=str(path), clip={
        'x': 0, 'y': 0, 'width': width or c.viewport['width'], 'height': height})
    print('captura', path.name)


with Captura(MODULE) as c:
    # 1. Lista agrupada por año, con el grupo 2026 abierto
    c.abrir_accion('al_hr_pe_public_holidays.action_pe_public_holiday', ms=2000)
    c.page.locator('.o_group_header:has-text("2026")').first.click()
    c.esperar(1200)
    c.foto('01-feriados')

    # 2. Filtros y agrupaciones de la búsqueda
    c.clic('.o_searchview_dropdown_toggler', ms=900)
    menu = c.page.locator('.o_search_bar_menu').first.bounding_box()
    franja(c, '02-filtros', menu['y'] + menu['height'] + 16)
    c.page.keyboard.press('Escape')
    c.esperar(400)

    # 3. Ficha de un feriado aplicado
    c.abrir_registro('pe.public.holiday', JUNIN_2026, ms=1800)
    c.foto('03-feriado')

    # 4. Feriado de medio día (registro nuevo, se descarta sin guardar)
    c.abrir('/odoo/action-al_hr_pe_public_holidays.action_pe_public_holiday/new', ms=1800)
    c.page.locator('div[name=name] input').fill('Feriado de medio día (ejemplo)')
    c.page.locator('div[name=is_full_day] input').uncheck()
    c.esperar(700)
    c.foto('04-medio-dia')
    c.clic('.o_form_button_cancel:visible', ms=1200)

    # 5. Selección y botón «Aplicar a los calendarios» (sin pulsarlo)
    c.abrir_accion('al_hr_pe_public_holidays.action_pe_public_holiday', ms=2000)
    c.page.locator('.o_group_header:has-text("2026")').first.click()
    c.esperar(1200)
    for i in range(17):
        c.page.locator('.o_data_row .o_list_record_selector input').nth(i).check()
    c.esperar(600)
    franja(c, '05-aplicar', 330)

    # 6. Descansos creados en los calendarios
    c.abrir_registro('pe.public.holiday', JUNIN_2026, ms=1800)
    c.clic('button[name=action_view_leaves]', ms=1800)
    c.foto('06-descansos')

    # 7. Ficha del descanso
    c.abrir_registro('resource.calendar.leaves', DESCANSO_JUNIN, ms=1800)
    c.foto('07-descanso')

    # 8. Días festivos nativos de Vacaciones
    c.abrir_accion('hr_holidays.open_view_public_holiday', ms=2000)
    c.foto('08-dias-festivos')

    # 10. La boleta computa los feriados como días de descanso
    c.abrir_registro('hr.payslip', BOLETA_JULIO, ms=2000)
    c.texto('Días trabajados', ms=900)
    c.foto('10-boleta-feriados', selector='.o_form_view .o_form_sheet_bg')

    # 11. Tarea programada anual
    c.abrir_registro('ir.cron', CRON, ms=1800)
    c.foto('11-cron', selector='.o_form_view .o_form_sheet_bg')


# Pantalla ancha: el mes completo del gantt, con los tres feriados de julio
with Captura(MODULE, viewport={'width': 1920, 'height': 700}) as c:
    # 9. Entradas de trabajo de julio: los feriados como días de descanso
    c.abrir_accion('hr_work_entry.hr_work_entry_action', ms=2500)
    search = c.page.locator('.o_searchview_input')
    search.fill('DEMO FICHA HR1')
    c.esperar(700)
    c.page.keyboard.press('Enter')
    c.esperar(1200)
    for _ in range(2):
        c.clic('button:has(> i.oi-arrow-left)', ms=1200)
    c.foto('09-entradas', clip={'x': 0, 'y': 172, 'width': 1920, 'height': 262})
