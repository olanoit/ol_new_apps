"""Capturas de la ficha de al_project_gantt_backend.

Datos: proyectos «[DEMO Gantt] Edificio A» (id 18) y «[DEMO Gantt] Migración
ERP» (id 19) de docs/gantt/pruebas/seed_gantt_demo.py y la línea base ya
guardada del Edificio A. El guion no guarda nada: el formulario de tarea se
cierra con Cancelar.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

ACTION = '/odoo/action-al_project_gantt_backend.action_gantt_backend'


def w(c, ms):
    c.page.wait_for_timeout(ms)


def abrir_gantt(c):
    c.abrir(ACTION, ms=4000)
    c.page.wait_for_selector('.gantt_row[data-task-id]', timeout=30000)
    w(c, 1000)
    # Sin el panel del asistente (lo añade al_project_gantt_ai)
    if c.page.locator('.algantt-ai-panel').count():
        c.page.locator('.algantt-ai-toggle').click()
        w(c, 600)


def region(c, name, top_sel, bottom_sel):
    """Recorte vertical entre dos elementos, a todo el ancho."""
    c.page.mouse.move(2, 890)
    w(c, 250)
    top = c.page.locator(top_sel).first.bounding_box()
    bottom = c.page.locator(bottom_sel).first.bounding_box()
    clip = {'x': 0, 'y': top['y'], 'width': c.viewport['width'],
            'height': bottom['y'] + bottom['height'] - top['y']}
    path = c.out / ('%s.png' % name)
    c.page.screenshot(path=str(path), clip=clip)
    print('captura', path.name)


with Captura('al_project_gantt_backend') as c:
    # Navegador en español de Perú: los campos de fecha salen como dd/mm/aaaa
    c.page.close()
    c.page = c.browser.new_page(viewport=c.viewport, locale='es-PE')
    c.page.set_default_timeout(20000)
    c.login()
    p = c.page

    # 1. Botón inteligente en el proyecto
    c.abrir('/odoo/project/18', ms=3000)
    region(c, '01-boton-proyecto', '.o_main_navbar', '.o_form_sheet_bg .o_notebook_headers')

    # 2. Diagrama completo, escala Semana
    abrir_gantt(c)
    c.foto('02-diagrama')

    # 3. Escala Mes con código EDT
    p.select_option('#algantt_zoom', index=2)
    w(c, 1500)
    p.get_by_role('button', name='EDT').click()
    w(c, 1000)
    c.foto('03-escala-mes-edt')

    # 4. Filtros
    c.clic('.algantt-toolbar button:has-text("Filtros")', ms=1000)
    region(c, '04-filtros', '.algantt-toolbar', '.gantt_row[data-task-id="219"]')
    c.clic('.algantt-toolbar button:has-text("Filtros")', ms=800)

    # 5. Ruta crítica (columna Holgura)
    p.get_by_role('button', name='Ruta crítica').click()
    w(c, 2500)
    c.foto('05-ruta-critica')
    p.get_by_role('button', name='Ruta crítica').click()
    w(c, 1500)

    # 6. Línea base
    p.select_option('select[title="Comparar contra una línea base"]', index=1)
    w(c, 2500)
    c.foto('06-linea-base')
    p.select_option('select[title="Comparar contra una línea base"]', index=0)
    w(c, 1500)

    # 7. Formulario de tarea (doble clic) — se cancela
    p.locator('.gantt_row[data-task-id="219"] .gantt_cell').first.dblclick()
    w(c, 2000)
    p.evaluate("() => { document.activeElement.blur(); window.getSelection().removeAllRanges(); }")
    w(c, 300)
    c.foto('07-formulario-tarea', selector='.gantt_cal_light')
    p.locator('.gantt_cancel_btn_set').first.click()
    w(c, 800)

    # 8. Menú contextual
    abrir_gantt(c)
    p.locator('.gantt_row[data-task-id="219"] .gantt_cell').first.click(button='right')
    w(c, 1000)
    c.foto('08-menu-contextual')
