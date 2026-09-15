"""Capturas de la ficha de al_hr_pe_construction (datos «DEMO FICHA HR2»)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

with Captura('al_hr_pe_construction') as c:
    # 1. Tabla salarial del convenio 2026 con los importes derivados
    c.abrir_registro('l10n_pe.hr.construction.wage.table', 1, ms=2000)
    c.foto('01-tabla-salarial', selector='.o_form_view .o_form_sheet_bg')

    # 2. Catálogo de bonificaciones (BAE y condiciones de trabajo)
    c.abrir_accion('al_hr_pe_construction.action_construction_bonus', ms=2000)
    c.foto('02-bonificaciones')

    # 3. Obra con las bonificaciones que activa
    c.abrir_registro('l10n_pe.hr.construction.site', 133, ms=2000)
    c.foto('03-obra', selector='.o_form_view .o_form_sheet_bg')

    # 4. Parámetros del régimen en la compañía
    c.abrir_registro('res.company', 1, ms=2000)
    c.clic('.o_notebook_headers a[name=l10n_pe_construction]', ms=800)
    c.foto('04-compania', selector='.o_notebook .tab-content')

    # 5. Trabajador: categoría, obra, BAE y jornal calculado
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
    c.page.screenshot(path=str(c.out / '05-trabajador.png'), clip={
        'x': sheet['x'], 'y': box['y'] - 16, 'width': sheet['width'],
        'height': gbox['y'] + gbox['height'] - box['y'] + 32})

    # 6. Boleta semanal: cálculo del salario
    c.page.set_viewport_size({'width': 1440, 'height': 1900})
    c.abrir_registro('hr.payslip', 3512, ms=2500)
    c.clic('.o_notebook_headers a[name=salary_computation]', ms=1000)
    c.foto('06-boleta-semanal', selector='.o_form_view .o_form_sheet_bg')

    # 7. Boleta impresa del régimen (vista previa HTML del PDF). El logotipo
    #    de la compañía de pruebas se oculta: no es parte del módulo.
    c.page.set_viewport_size({'width': 1440, 'height': 1200})
    c.abrir('/report/html/al_hr_pe_construction.report_l10n_pe_boleta_construccion_document/3509', ms=2000)
    c.js("document.querySelectorAll('.article img').forEach(i => i.style.visibility = 'hidden')")
    c.foto('07-boleta-impresa', selector='.article', padding=12)

    # 8. CONAFOVICER de agosto 2026 (más ancho para leer los nombres)
    c.page.set_viewport_size({'width': 1760, 'height': 1000})
    c.abrir_registro('l10n_pe.hr.conafovicer', 178, ms=2000)
    c.foto('08-conafovicer', selector='.o_form_view .o_form_sheet_bg')
