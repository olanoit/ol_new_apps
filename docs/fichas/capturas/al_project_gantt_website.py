"""Capturas de la ficha de al_project_gantt_website (página /gantt).

Datos: proyectos «[DEMO Gantt]» 18 y 19. Solo consulta: no se guarda nada.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402


def w(c, ms):
    c.page.wait_for_timeout(ms)


def abrir(c):
    c.abrir('/gantt', ms=4000)
    c.page.wait_for_selector('.gantt_row[data-task-id]', timeout=30000)
    w(c, 1000)


with Captura('al_project_gantt_website') as c:
    p = c.page

    # 1. Página del sitio web
    abrir(c)
    c.foto('01-pagina')

    # 2. Filtros
    p.locator('.algantt-filters-toggle').click()
    w(c, 1000)
    c.foto('02-filtros')
    p.locator('.algantt-filters-toggle').click()
    w(c, 600)

    # 3. Búsqueda instantánea (conserva los ancestros)
    p.locator('.algantt-search').fill('Obra')
    w(c, 1200)
    c.page.mouse.move(1430, 890)
    w(c, 300)
    box = p.locator('.gantt_row[data-task-id]').last.bounding_box()
    p.screenshot(path=str(c.out / '03-busqueda.png'),
                 clip={'x': 0, 'y': 60, 'width': 1440, 'height': box['y'] + box['height'] + 40 - 60})
    print('captura 03-busqueda.png')
    p.locator('.algantt-search').fill('')
    w(c, 800)

    # 4. Menú contextual
    abrir(c)
    p.locator('.gantt_row[data-task-id="219"] .gantt_cell').first.click(button='right')
    w(c, 1000)
    p.add_style_tag(content='.gantt_tooltip { display: none !important; }')
    w(c, 500)
    c.foto('04-menu-contextual')
