"""Capturas de la ficha de al_hr_pe_public_holidays (datos «DEMO FICHA HR1»).

Los feriados de 2026 están aplicados solo al calendario DEMO
«DEMO FICHA HR1 Jornada 48h»: el botón «Aplicar a los calendarios» no se
pulsa aquí porque escribiría en todos los calendarios de la compañía.
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

MODULE = 'al_hr_pe_public_holidays'
JUNIN_2026 = 11        # Batalla de Junín, 06/08/2026
CRON = 55              # Peru Holidays: Yearly Auto Apply
BOLETA_JULIO = 3521    # DEMO FICHA HR1 Salazar Quispe Lucía, julio 2026

with Captura(MODULE) as c:
    # 1. Lista agrupada por año, con el grupo 2026 abierto
    c.abrir_accion('al_hr_pe_public_holidays.action_pe_public_holiday', ms=2000)
    c.page.locator('.o_group_header:has-text("2026")').first.click()
    c.esperar(1200)
    c.foto('01-feriados')

    # 2. Selección y botón «Aplicar a los calendarios» (sin pulsarlo)
    c.page.locator('.o_data_row .o_list_record_selector input').nth(0).check()
    for i in range(1, 17):
        c.page.locator('.o_data_row .o_list_record_selector input').nth(i).check()
    c.esperar(600)
    c.page.mouse.move(1439, 899)
    c.page.wait_for_timeout(250)
    path = c.out / '02-aplicar.png'
    c.page.screenshot(path=str(path), clip={'x': 0, 'y': 0, 'width': 1440, 'height': 330})
    print('captura', path.name)

    # 3. Ficha de un feriado aplicado
    c.abrir_registro('pe.public.holiday', JUNIN_2026, ms=1800)
    c.foto('03-feriado')

    # 4. Descansos creados en los calendarios
    c.clic('button[name=action_view_leaves]', ms=1800)
    c.foto('04-descansos')

    # 5. La boleta computa los feriados como días de descanso
    c.abrir_registro('hr.payslip', BOLETA_JULIO, ms=2000)
    c.texto('Días trabajados', ms=900)
    c.foto('05-boleta-feriados', selector='.o_form_view .o_form_sheet_bg')

    # 6. Tarea programada anual
    c.abrir_registro('ir.cron', CRON, ms=1800)
    c.foto('06-cron', selector='.o_form_view .o_form_sheet_bg')
