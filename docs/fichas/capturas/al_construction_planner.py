"""Capturas de las fases 3 y 4 de al_construction_planner (línea base,
asignaciones y compras): datos «DEMO PLAN» de tools/planner_demo_data.py,
tools/planner_demo_baseline.py y tools/planner_demo_supply.py. Las capturas
01 a 03 (árbol de recursos) son de la fase 2."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_construction_planner'
PLAN = 'construction.resource.plan'
FULL = '.o_action_manager'
MODAL = '.modal-content'



def buscar(c, model, domain, order='id'):
    """Ids de ``model`` que cumplen ``domain`` (por RPC desde el navegador)."""
    return c.page.evaluate("""async ([model, domain, order]) => {
        const res = await fetch('/web/dataset/call_kw', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                model, method: 'search_read', args: [domain, ['id']],
                kwargs: {order}}})});
        const data = await res.json();
        return data.result.map(r => r.id);
    }""", [model, domain, order])


with Captura(M) as c:
    v1, v2 = buscar(c, PLAN, [['project_id.name', '=', 'DEMO PLAN MOMEN-35-26']], 'version')[:2]

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

    # --- Fase 4: asignaciones y compras ----------------------------------
    # 11. Plan en ejecución: botones de abastecimiento y asignaciones
    c.abrir_registro(PLAN, v1, ms=2000)
    c.foto('11-plan-en-ejecucion', selector=FULL)

    # 12. Compra masiva (W-02) en modo stock general
    c.texto('Compra masiva', ms=2000)
    c.page.locator('.modal-content div[name=mode] input[data-value=general]').click()
    c.esperar(1500)
    c.foto('12-compra-masiva', selector=MODAL)
    c.clic('.modal-footer button.btn-secondary', ms=800)

    # 13. Requerimiento de obra desde el plan (W-03)
    c.texto('Requerimiento de obra', ms=2000)
    c.foto('13-requerimiento-desde-plan', selector=MODAL)
    c.clic('.modal-footer button.btn-secondary', ms=800)

    # 14. Asignaciones del plan por documento
    c.clic('button[name=action_view_allocations]', ms=2000)
    c.clic('.o_group_header', ms=1500)  # abre el primer documento
    c.foto('14-asignaciones', selector=FULL)

    # 15. Requerimiento de obra con control de plan (P-11): excede y justificado
    exceeded = buscar(c, 'construction.material.request', [
        ['construction_plan_id', '=', v1], ['construction_exceed_state', '=', 'exceeded']])
    c.abrir_registro('construction.material.request', exceeded[-1], ms=2000)
    c.foto('15-control-de-plan', selector=FULL)

    # 16. Orden de fabricación desde el plan (W-04)
    productions = buscar(c, 'mrp.production', [['construction_plan_id', '=', v1]])
    c.abrir_registro('mrp.production', productions[-1], ms=2000)
    c.texto('Plan de obra', ms=1200)
    c.foto('16-of-desde-plan', selector=FULL)
