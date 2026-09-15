"""Capturas de la ficha de al_hr_pe (datos «DEMO FICHA HR1»).

Solo lee: ningún botón que escriba se pulsa (el diálogo «Dar de baja» y
«Generar periodos» se cancelan; la validación del T-Registro se detiene en
el aviso, antes de generar nada).
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura, _recortar_fondo  # noqa: E402

MODULE = 'al_hr_pe'
LUCIA = 2448          # DEMO FICHA HR1 Salazar Quispe Lucía
BOLETA_LUCIA = 3521   # Boleta julio 2026 (estructura BASE)
DEP_CAMILA = 1030     # hija menor de edad
AFP_INTEGRA = 2
ESTRUCTURA_BASE = 7
SEDE_DEMO = 48        # DEMO FICHA HR1 Sede Lima (código 0001)
BANCO_DEMO = 80       # DEMO FICHA HR1 Banco (T36 002)
# FICHA_DESDE=16 repite solo desde ese bloque de capturas.
DESDE = int(os.environ.get('FICHA_DESDE', '0'))


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


def franja(c, name, height):
    """Parte superior de la pantalla (listas cortas)."""
    c.page.mouse.move(c.viewport['width'] - 2, c.viewport['height'] - 2)
    c.page.wait_for_timeout(250)
    path = c.out / ('%s.png' % name)
    c.page.screenshot(path=str(path), clip={
        'x': 0, 'y': 0, 'width': c.viewport['width'], 'height': height})
    print('captura', path.name)


def buscar(c, texto):
    search = c.page.locator('.o_searchview_input')
    search.fill(texto)
    c.esperar(500)
    c.page.keyboard.press('Enter')
    c.esperar(1200)


# 01. Menú Configuración ▸ Perú (pantalla ancha para que no se pliegue)
if DESDE <= 1:
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

if DESDE <= 2:
    with Captura(MODULE, viewport={'width': 1600, 'height': 900}) as c:
        # 02. Parámetros principales de la compañía
        c.abrir_registro('hr.main.parameter', 90, ms=2000)
        c.foto('02-parametros', selector='.o_form_view .o_form_sheet_bg')

        # 03. UIT por año
        c.abrir_accion('al_hr_pe.l10n_pe_hr_uit_action', ms=1500)
        franja(c, '03-uit', 260)

        # 04. Afiliaciones AFP/ONP con sus tasas
        c.abrir_accion('al_hr_pe.hr_membership_action', ms=1500)
        c.foto('04-afiliaciones')

        # 05. Ficha de una AFP
        c.abrir_registro('hr.membership', AFP_INTEGRA, ms=1800)
        c.foto('05-afiliacion', selector='.o_form_view .o_form_sheet_bg')

        # 06. Seguros sociales
        c.abrir_accion('al_hr_pe.hr_social_insurance_action', ms=1500)
        franja(c, '06-seguros', 230)

        # 07. Generar periodos (con semanas) — se cancela
        c.abrir_accion('al_hr_pe.hr_period_generator_action', ms=1500)
        c.page.locator('.modal-dialog div[name=generate_weekly] input').check()
        c.page.locator('.modal-dialog .modal-title').click()
        c.esperar(400)
        c.foto('07-generar-periodos', selector='.modal-content')
        c.clic('.modal-footer button:has-text("Cancelar")', ms=600)

        # 08. Periodos de nómina
        c.abrir_accion('al_hr_pe.hr_period_action', ms=1800)
        buscar(c, '2026')
        franja(c, '08-periodos', 543)

        # 09. Suspensiones de labores (T21)
        c.abrir_accion('al_hr_pe.hr_work_suspension_action', ms=1800)
        franja(c, '09-suspensiones', 230)

        # 10. Catálogo T33 con su familia de cálculo
        c.abrir_accion('al_hr_pe.action_l10n_pe_labor_regime', ms=1800)
        c.foto('10-regimenes')

        # 11. Ocupaciones T30 con sus columnas
        c.abrir_accion('al_hr_pe.action_l10n_pe_occupation', ms=1800)
        c.foto('11-ocupaciones')

# 12-13. Ficha del trabajador: identificación PLAME, domicilio y T-Registro
if DESDE <= 12:
    with Captura(MODULE, viewport={'width': 1440, 'height': 3400}) as c:
        c.abrir_registro('hr.employee', LUCIA, ms=2500)
        c.texto('Personal', ms=900)
        recorte(c, '12-ficha-plame',
                c.page.get_by_text('Perú — Identificación (PLAME)', exact=True),
                c.page.locator('.o_form_sheet_bg label:has-text("Nacionalidad (T04)")'),
                right='.o_form_sheet')
        c.texto('Nómina', ms=900)
        recorte(c, '13-ficha-tregistro',
                c.page.get_by_text('T-Registro (SUNAT)', exact=True),
                c.page.locator('.o_form_sheet_bg label:has-text("RUC del trabajador")'),
                right='.o_form_sheet')

if DESDE <= 14:
    with Captura(MODULE, viewport={'width': 1440, 'height': 900}) as c:
        # 14. Código de establecimiento en el lugar de trabajo
        c.abrir_registro('hr.work.location', SEDE_DEMO, ms=1800)
        c.foto('14-lugar-trabajo', selector='.o_form_view .o_form_sheet_bg')

        # 15. Entidad SUNAT (T36) en el banco
        c.abrir_registro('res.bank', BANCO_DEMO, ms=1800)
        c.foto('15-banco', selector='.o_form_view .o_form_sheet_bg')

if DESDE <= 16:
    with Captura(MODULE, viewport={'width': 1920, 'height': 900}) as c:
        # 16. Histórico de versiones con las columnas peruanas
        c.abrir('/odoo/action-hr.action_hr_version', ms=2000)
        buscar(c, 'DEMO FICHA HR1')
        c.clic('.o_optional_columns_dropdown_toggle', ms=600)
        for label in ('Tipo de trabajador (T08)', 'Situación (T15)', 'Seguro social',
                      'CUSPP', 'Tipo de comisión AFP (PE)', 'Ocupación (T30)'):
            c.page.locator('.o-dropdown--menu .o-checkbox:has-text("%s") input' % label).first.check()
            c.esperar(500)
        c.page.locator('.o_control_panel .o_breadcrumb').first.click()
        c.esperar(600)
        c.foto('16-versiones')

if DESDE <= 17:
    with Captura(MODULE) as c:
        # 17. Derechohabientes del trabajador (botón de la ficha)
        c.abrir_registro('hr.employee', LUCIA, ms=2500)
        c.clic('button[name=action_open_l10n_pe_dependents]', ms=1500)
        c.page.locator('thead .o_list_record_selector input').first.check()
        c.esperar(700)
        c.foto('17-derechohabientes')

        # 18. Ficha de un derechohabiente
        c.abrir_registro('l10n_pe.hr.dependent', DEP_CAMILA, ms=1500)
        c.foto('18-derechohabiente', selector='.o_form_view .o_form_sheet_bg')

        # 19. «Dar de baja» pide confirmación (se cancela)
        c.clic('.o_form_statusbar button[name=action_set_end]', ms=900)
        c.foto('19-dar-baja', selector='.modal-content')
        c.clic('.modal-footer button:has-text("Cancelar")', ms=600)

        # 20. Tipos de derechohabiente (T19) con sus banderas
        c.abrir_accion('al_hr_pe.action_l10n_pe_dependent_type', ms=1500)
        franja(c, '20-tipos-derechohabiente', 330)

        # 21. Boleta: pestaña Perú con el snapshot del cálculo
        c.abrir_registro('hr.payslip', BOLETA_LUCIA, ms=2000)
        c.texto('Perú', ms=900)
        c.foto('21-boleta-peru', selector='.o_form_view .o_form_sheet_bg')

        # 22. Estructura BASE con sus reglas
        c.abrir_registro('hr.payroll.structure', ESTRUCTURA_BASE, ms=2000)
        c.foto('22-estructura-base', selector='.o_form_view .o_form_sheet_bg')

        # 23. Lote: exportadores PLAME y AFPNet
        c.abrir_accion('hr_payroll.action_hr_payslip_run', ms=2500)
        card = c.page.locator('.o_kanban_record:has-text("DEMO FICHA HR1 Planilla julio")').first
        card.locator('.o_dropdown_kanban .dropdown-toggle, .oe_kanban_action_menu, button.dropdown-toggle').first.click()
        c.esperar(700)
        menu = c.page.locator('.o-dropdown--menu').first.bounding_box()
        cbox = card.bounding_box()
        c.page.mouse.move(5, 895)
        c.page.wait_for_timeout(250)
        path = c.out / '23-lote-plame.png'
        # El menú se abre hacia arriba o hacia abajo según el sitio que quede.
        top = min(menu['y'] - 8, cbox['y'] + 1)
        c.page.screenshot(path=str(path), clip={
            'x': 40, 'y': top, 'width': 1440 - 40,
            'height': max(menu['y'] + menu['height'], cbox['y'] + cbox['height']) - top + 12})
        print('captura', path.name)

        # 24. Empleados: acciones del T-Registro
        c.abrir('/odoo/action-hr.open_view_employee_list_my?view_type=list', ms=2500)
        buscar(c, 'DEMO FICHA HR1')
        for i in range(3):
            c.page.locator('.o_data_row .o_list_record_selector input').nth(i).check()
        c.esperar(500)
        c.clic('.o_control_panel_actions button:has-text("Acciones")', ms=700)
        c.foto('24-tregistro-acciones')

        # 25. Validación previa: lo que el PVS rechazaría, antes de generar
        c.clic('.o-dropdown--menu .dropdown-item:has-text("T-Registro: generar alta")', ms=1500)
        c.foto('25-tregistro-validacion', selector='.modal-content')
