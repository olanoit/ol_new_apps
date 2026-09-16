"""Capturas de la ficha de al_hr_pe_construction (datos «DEMO FICHA HR2»).

Obreros 2444 (operario, BAE equipo pesado), 2445 (oficial) y 2446 (peón) en
la obra 132; obra 133 a 3 850 m; boletas semanales 3509–3520 de agosto 2026
(validadas) y resumen CONAFOVICER 178. No se pulsa ningún botón que cambie
datos.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

FORM = '.o_form_view .o_form_sheet_bg'


def ancho(c, width, height):
    c.page.set_viewport_size({'width': width, 'height': height})
    c.viewport = {'width': width, 'height': height}


with Captura('al_hr_pe_construction') as c:
    # --- Maestros del convenio -----------------------------------------
    # 1. Lista de tablas salariales
    c.abrir_accion('al_hr_pe_construction.action_construction_wage_table', ms=2000)
    c.foto('01-tablas-salariales')

    # 2. Tabla salarial del convenio 2026 con todos los derivados visibles
    ancho(c, 1920, 1000)
    c.abrir_registro('l10n_pe.hr.construction.wage.table', 1, ms=2000)
    c.clic('.o_optional_columns_dropdown_toggle', ms=600)
    for label in ('Grat. F. Patrias diaria', 'Grat. Navidad diaria', 'Asig. escolar diaria'):
        item = c.page.locator('.o-dropdown--menu .dropdown-item:has-text("%s") input' % label).first
        if not item.is_checked():
            item.click()
            c.esperar(400)
    c.page.keyboard.press('Escape')
    c.page.locator('.o_form_sheet h1').first.click()
    c.esperar(500)
    c.foto('02-tabla-salarial', selector=FORM)
    ancho(c, 1440, 900)

    # 3. Categorías
    c.abrir_accion('al_hr_pe_construction.action_construction_category', ms=2000)
    c.foto('03-categorias')

    # 4. Catálogo de bonificaciones (BAE y condiciones de trabajo)
    ancho(c, 1600, 900)
    c.abrir_accion('al_hr_pe_construction.action_construction_bonus', ms=2000)
    c.foto('04-bonificaciones')
    ancho(c, 1440, 900)

    # --- Obras ------------------------------------------------------------
    # 5. Lista de obras con sus trabajadores
    c.abrir_accion('al_hr_pe_construction.action_construction_site', ms=2000)
    c.foto('05-obras')

    # 6. Obra con el botón Trabajadores (en v19 va en el panel de control)
    #    y la bonificación por riesgo bajo la cota cero que activa
    c.abrir_registro('l10n_pe.hr.construction.site', 132, ms=2000)
    c.foto('06-obra')

    # --- Compañía -----------------------------------------------------------
    # 7. Parámetros del régimen en la compañía
    c.abrir_registro('res.company', 1, ms=2000)
    c.clic('.o_notebook_headers a[name=l10n_pe_construction]', ms=800)
    c.foto('07-compania', selector='.o_notebook .tab-content')

    # --- Trabajador --------------------------------------------------------
    # 8. Trabajador: categoría, obra, BAE y jornal calculado
    c.abrir_registro('hr.employee', 2444, ms=2500)
    c.clic('.o_notebook_headers a[name=payroll_information]', ms=1000)
    sep = c.page.locator('.tab-pane.active .o_horizontal_separator:text-is("Construcción civil")').first
    sep.evaluate("e => e.scrollIntoView({block: 'start'})")
    c.esperar(600)
    c.page.mouse.move(1438, 898)
    box = sep.bounding_box()
    group = sep.locator('xpath=following-sibling::div[contains(@class, "o_inner_group") or contains(@class, "o_group")][1]')
    gbox = group.bounding_box()
    sheet = c.page.locator('.o_form_sheet').first.bounding_box()
    c.foto('08-trabajador', clip={
        'x': sheet['x'], 'y': box['y'] - 16, 'width': sheet['width'],
        'height': gbox['y'] + gbox['height'] - box['y'] + 32})

    # --- Planilla semanal ---------------------------------------------------
    # 9. Boletas semanales DEMO de agosto 2026
    ancho(c, 1440, 1000)
    c.abrir_accion('hr_payroll.action_view_hr_payslip_month_form', ms=2500)
    search = c.page.locator('.o_searchview_input').first
    search.click()
    search.type('DEMO FICHA HR2 Semana', delay=20)
    c.esperar(1200)
    c.page.locator(".o_searchview_autocomplete .o-dropdown-item").nth(2).locator("a").last.click()
    c.esperar(1500)
    c.foto('09-boletas-semanales')

    # 10. Boleta semanal: días trabajados y horas extras al 60 %
    ancho(c, 1440, 1100)
    c.abrir_registro('hr.payslip', 3512, ms=2500)
    c.clic('.o_notebook_headers a[name=worked_days]', ms=1000)
    c.foto('10-boleta-dias', selector=FORM)

    # 11. Boleta semanal: cálculo del salario
    ancho(c, 1440, 1900)
    c.clic('.o_notebook_headers a[name=salary_computation]', ms=1000)
    c.foto('11-boleta-semanal', selector=FORM)

    # 12. Boleta impresa del régimen (vista previa HTML del PDF). El logotipo
    #     de la compañía de pruebas se oculta: no es parte del módulo.
    ancho(c, 1440, 1200)
    c.abrir('/report/html/al_hr_pe_construction.report_l10n_pe_boleta_construccion_document/3509', ms=2000)
    c.js("document.querySelectorAll('.article img').forEach(i => i.style.visibility = 'hidden')")
    c.foto('12-boleta-impresa', selector='.article', padding=12)

    # --- CONAFOVICER ----------------------------------------------------------
    # 13. Lista de resúmenes mensuales
    ancho(c, 1440, 900)
    c.abrir_accion('al_hr_pe_construction.action_conafovicer', ms=2000)
    c.foto('13-conafovicer-lista')

    # 14. CONAFOVICER de agosto 2026 (más ancho para leer los nombres)
    ancho(c, 1760, 1000)
    c.abrir_registro('l10n_pe.hr.conafovicer', 178, ms=2000)
    c.foto('14-conafovicer', selector=FORM)

    # --- Importar tabla del convenio -------------------------------------
    # 15. Lista de tablas salariales con el botón de importación
    ancho(c, 1440, 900)
    c.abrir_accion('al_hr_pe_construction.action_construction_wage_table', ms=2000)
    c.foto('15-importar-tabla-boton')

    # 16. Asistente con origen «Dirección web» y la revisión mensual
    c.clic('.o_al_import_wage_table_btn', ms=1500)
    c.texto('Dirección web')
    c.foto('16-importar-tabla-asistente', selector='.modal-content')
