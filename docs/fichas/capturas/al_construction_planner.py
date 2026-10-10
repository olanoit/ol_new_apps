"""Capturas de la fase 3 de al_construction_planner (línea base): datos «DEMO
PLAN» de tools/planner_demo_data.py y tools/planner_demo_baseline.py. Las
capturas 01 a 03 (árbol de recursos) son de la fase 2."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_construction_planner'
PLAN = 'construction.resource.plan'
FULL = '.o_action_manager'
MODAL = '.modal-content'

with Captura(M) as c:
    v1, v2 = c.js("""async () => {
        const res = await fetch('/web/dataset/call_kw', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                model: 'construction.resource.plan', method: 'search_read',
                args: [[['project_id.name', '=', 'DEMO PLAN MOMEN-35-26']], ['id', 'version']],
                kwargs: {order: 'version'}}})});
        const data = await res.json();
        return data.result.map(r => r.id);
    }""")[:2]

    # 4. Versión aprobada: resumen por etapa, presupuesto y versiones
    c.abrir_registro(PLAN, v1, ms=2000)
    c.texto('Resumen por etapa', ms=1200)
    c.foto('04-resumen-etapa', selector=FULL)

    # 5. Presupuesto analítico creado por la aprobación
    c.clic('button[name=action_view_budget]', ms=2000)
    c.foto('05-presupuesto', selector=FULL)

    # 6. Asistente «Nueva versión» (W-09)
    c.abrir_registro(PLAN, v1, ms=2000)
    c.clic('button[name=action_open_replan_wizard]', ms=1500)
    c.foto('06-nueva-version', selector=MODAL)
    c.clic('.modal-footer button.btn-secondary', ms=800)

    # 7. Versión 2 en borrador: «Sin etapa» en el resumen
    c.abrir_registro(PLAN, v2, ms=2000)
    c.texto('Resumen por etapa', ms=1200)
    c.foto('07-version-borrador', selector=FULL)

    # 8. «Solicitar aprobación» bloqueada con la lista de líneas
    c.clic('button[name=action_request_approval]', ms=1500)
    c.foto('08-aprobacion-bloqueada', selector=MODAL)
    c.clic('.modal-footer button', ms=800)

    # 9. Aplicar costo (W-12) con las compras de la melamina blanca
    c.clic('button[name=action_open_price_wizard]', ms=1500)
    field = c.page.locator('.modal-content div[name=product_id] input')
    field.fill('Melamina MDP blanco')
    c.esperar(1200)
    c.page.locator('.o-autocomplete--dropdown-item').first.click()
    c.esperar(1500)
    c.foto('09-aplicar-costo', selector=MODAL)
    c.clic('.modal-footer button.btn-secondary', ms=800)

    # 10. Análisis de las líneas (gráfico por etapa y tipo de recurso)
    c.abrir_accion(f'{M}.action_construction_resource_plan_line_analysis', ms=2000)
    c.clic('.o_switch_view.o_graph', ms=2000)
    c.foto('10-analisis', selector=FULL)
