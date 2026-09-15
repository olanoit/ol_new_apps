"""Capturas de la ficha de al_hr_pe (datos «DEMO FICHA HR1»)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura, _recortar_fondo  # noqa: E402

MODULE = 'al_hr_pe'
LUCIA = 2448          # DEMO FICHA HR1 Salazar Quispe Lucía
BOLETA_LUCIA = 3521   # Boleta julio 2026 (estructura BASE)
LOTE_JULIO = 1197     # DEMO FICHA HR1 Planilla julio 2026
DEP_CAMILA = 1030     # hija menor de edad


def recorte(c, name, top, bottom, left=None, right=None, margin=14):
    """Foto de la franja entre el borde superior de ``top`` y el inferior
    de ``bottom`` (selectores o localizadores)."""
    page = c.page
    page.mouse.move(c.viewport['width'] - 2, c.viewport['height'] - 2)
    page.wait_for_timeout(250)

    def box(target):
        loc = page.locator(target) if isinstance(target, str) else target
        return loc.first.bounding_box()

    t, b = box(top), box(bottom)
    x0 = box(left)['x'] if left else 0
    x1 = (lambda r: r['x'] + r['width'])(box(right)) if right else c.viewport['width']
    clip = {'x': max(x0 - margin, 0), 'y': max(t['y'] - margin, 0),
            'width': (x1 - x0) + 2 * margin,
            'height': b['y'] + b['height'] - t['y'] + 2 * margin}
    path = c.out / ('%s.png' % name)
    page.screenshot(path=str(path), clip=clip)
    _recortar_fondo(path)
    print('captura', path.name)


# 1. Menú Configuración ▸ Perú (pantalla ancha para que no se pliegue)
with Captura(MODULE, viewport={'width': 1920, 'height': 1700}) as c:
    c.abrir_accion('al_hr_pe.hr_main_parameter_action', ms=1500)
    c.clic('[data-menu-xmlid="hr_work_entry_enterprise.menu_hr_payroll_configuration"]', ms=900)
    c.page.mouse.move(600, 1500)
    c.page.wait_for_timeout(300)
    menu = c.page.locator('.o-dropdown--menu').first.bounding_box()
    last = c.page.locator('.o-dropdown--menu .dropdown-item:has-text("Plantillas de contrato")').first.bounding_box()
    path = c.out / '01-menu-peru.png'
    c.page.screenshot(path=str(path), clip={
        'x': menu['x'] - 900, 'y': 0, 'width': menu['width'] + 916,
        'height': last['y'] + last['height'] + 14})
    print('captura', path.name)

with Captura(MODULE, viewport={'width': 1600, 'height': 900}) as c:
    # 2. Parámetros principales de la compañía
    c.abrir_registro('hr.main.parameter', 90, ms=2000)
    c.foto('02-parametros', selector='.o_form_view .o_form_sheet_bg')

    # 3. Afiliaciones AFP/ONP con sus tasas
    c.abrir_accion('al_hr_pe.hr_membership_action', ms=1500)
    c.foto('03-afiliaciones')

    # 4. Generar periodos (con semanas)
    c.abrir_accion('al_hr_pe.hr_period_generator_action', ms=1500)
    c.page.locator('.modal-dialog div[name=generate_weekly] input').check()
    c.page.locator('.modal-dialog .modal-title').click()
    c.esperar(400)
    c.foto('04-generar-periodos', selector='.modal-content')
    c.clic('.modal-footer button:has-text("Cancelar")', ms=600)

# 5-6. Ficha del trabajador: identificación PLAME, domicilio y T-Registro
with Captura(MODULE, viewport={'width': 1440, 'height': 3000}) as c:
    c.abrir_registro('hr.employee', LUCIA, ms=2500)
    c.texto('Personal', ms=900)
    recorte(c, '05-ficha-plame',
            c.page.get_by_text('Perú — Identificación (PLAME)', exact=True),
            c.page.locator('.o_form_sheet_bg label:has-text("Distrito (2)")'),
            right='.o_form_sheet')
    c.texto('Nómina', ms=900)
    recorte(c, '06-ficha-tregistro',
            c.page.get_by_text('Condición laboral', exact=True),
            c.page.locator('.o_form_sheet_bg label:has-text("RUC del trabajador")'),
            right='.o_form_sheet')

with Captura(MODULE, viewport={'width': 1920, 'height': 900}) as c:
    # 7. Histórico de versiones con las columnas peruanas
    c.abrir('/odoo/action-hr.action_hr_version', ms=2000)
    search = c.page.locator('.o_searchview_input')
    search.fill('DEMO FICHA HR1')
    c.esperar(500)
    c.page.keyboard.press('Enter')
    c.esperar(1200)
    c.clic('.o_optional_columns_dropdown_toggle', ms=600)
    for label in ('Tipo de trabajador (T08)', 'Situación (T15)', 'Seguro social',
                  'CUSPP', 'Tipo de comisión AFP (PE)', 'Ocupación (T30)'):
        c.page.locator('.o-dropdown--menu .o-checkbox:has-text("%s") input' % label).first.check()
        c.esperar(500)
    c.page.locator('.o_control_panel .o_breadcrumb').first.click()
    c.esperar(600)
    c.foto('07-versiones')

with Captura(MODULE) as c:

    # 8. Derechohabientes del trabajador (botón de la ficha)
    c.abrir_registro('hr.employee', LUCIA, ms=2500)
    c.clic('button[name=action_open_l10n_pe_dependents]', ms=1500)
    c.page.locator('thead .o_list_record_selector input').first.check()
    c.esperar(700)
    c.foto('08-derechohabientes')

    # 9. Ficha de un derechohabiente
    c.abrir_registro('l10n_pe.hr.dependent', DEP_CAMILA, ms=1500)
    c.foto('09-derechohabiente', selector='.o_form_view .o_form_sheet_bg')

    # 10. Boleta: pestaña Perú con el snapshot del cálculo
    c.abrir_registro('hr.payslip', BOLETA_LUCIA, ms=2000)
    c.texto('Perú', ms=900)
    c.foto('10-boleta-peru', selector='.o_form_view .o_form_sheet_bg')

with Captura(MODULE) as c:
    # 11. Lote: exportadores PLAME y AFPNet
    c.abrir_accion('hr_payroll.action_hr_payslip_run', ms=2500)
    card = c.page.locator('.o_kanban_record:has-text("DEMO FICHA HR1 Planilla julio")').first
    card.locator('.o_dropdown_kanban .dropdown-toggle, .oe_kanban_action_menu, button.dropdown-toggle').first.click()
    c.esperar(700)
    menu = c.page.locator('.o-dropdown--menu').first.bounding_box()
    cbox = card.bounding_box()
    c.page.mouse.move(5, 895)
    c.page.wait_for_timeout(250)
    path = c.out / '11-lote-plame.png'
    top = cbox['y'] + 1
    c.page.screenshot(path=str(path), clip={
        'x': 40, 'y': top, 'width': 1440 - 40,
        'height': max(menu['y'] + menu['height'], cbox['y'] + cbox['height']) - top + 12})
    print('captura', path.name)

    # 12. Empleados: acciones del T-Registro
    c.abrir('/odoo/action-hr.open_view_employee_list_my?view_type=list', ms=2500)
    search = c.page.locator('.o_searchview_input')
    search.fill('DEMO FICHA HR1')
    c.esperar(500)
    c.page.keyboard.press('Enter')
    c.esperar(1200)
    c.page.locator('.o_list_record_selector input').first.check()
    c.esperar(300)
    for i in (1, 2):
        c.page.locator('.o_data_row .o_list_record_selector input').nth(i).check()
    c.esperar(500)
    c.clic('.o_control_panel_actions button:has-text("Acciones")', ms=700)
    c.foto('12-tregistro-acciones')

    # 13. Validación previa: lo que el PVS rechazaría, antes de generar
    c.clic('.o-dropdown--menu .dropdown-item:has-text("T-Registro: generar alta")', ms=1500)
    c.foto('13-tregistro-validacion', selector='.modal-content')
