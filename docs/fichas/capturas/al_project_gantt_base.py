"""Capturas de la ficha de al_project_gantt_base.

El módulo base no tiene interfaz propia: se muestran su configuración (colores,
grupos), el informe PDF que define y el diagrama que dibujan las interfaces con
su adaptador. Datos: proyectos «[DEMO Gantt]» 18 y 19.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402


def w(c, ms):
    c.page.wait_for_timeout(ms)


with Captura('al_project_gantt_base') as c:
    p = c.page

    # 1. Colores por estado
    c.abrir('/odoo/action-al_project_gantt_base.al_gantt_state_color_action', ms=2500)
    c.foto('01-colores')

    # 2. Grupos de acceso en la ficha del usuario
    c.abrir('/odoo/action-base.action_res_users/2', ms=3000)
    c.foto('02-permisos', selector='.o_form_view .o_form_sheet_bg')

    # 3. Diagrama en escala Día (días no laborables sombreados)
    c.abrir('/odoo/action-al_project_gantt_backend.action_gantt_backend', ms=4000)
    p.wait_for_selector('.gantt_row[data-task-id]', timeout=30000)
    p.select_option('#algantt_zoom', index=0)
    w(c, 2000)
    c.foto('03-escala-dia')

    # 4. Informe PDF (versión HTML del mismo informe)
    c.abrir('/report/html/al_project_gantt_base.report_gantt/18,19', ms=3000)
    c.foto('04-informe-pdf', selector='main, .page, body', padding=0)
