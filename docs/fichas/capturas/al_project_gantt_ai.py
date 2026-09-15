"""Capturas de la ficha de al_project_gantt_ai.

Sin llamadas a proveedores de IA: se captura la configuración ya guardada en la
base (la clave sale enmascarada) y el panel del chat recién abierto, sin enviar
ninguna pregunta. No se pulsa «Guardar» en los ajustes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402


def w(c, ms):
    c.page.wait_for_timeout(ms)


with Captura('al_project_gantt_ai') as c:
    p = c.page

    # 1. Ajustes (Gantt ▸ Configuración ▸ Ajustes)
    c.abrir('/odoo/action-al_project_gantt_ai.action_gantt_ai_settings', ms=3000)
    assert p.locator('div[name=al_gantt_ai_api_key] input[type=password]').count() == 1
    c.foto('01-ajustes-conexion')

    # 2. Panel abierto, sin conversación
    c.abrir('/odoo/action-al_project_gantt_backend.action_gantt_backend', ms=4000)
    p.wait_for_selector('.gantt_row[data-task-id]', timeout=30000)
    w(c, 800)
    if not p.locator('.algantt-ai-panel').count():
        p.locator('.algantt-ai-toggle').click()
        w(c, 1500)
    c.foto('02-panel')
