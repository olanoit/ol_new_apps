"""Capturas de las fases 3 a 7 de al_construction_planner (línea base,
asignaciones y compras, contratas, liquidación semanal, control y personal
propio): datos «DEMO PLAN» de tools/planner_demo_data.py,
planner_demo_baseline.py, planner_demo_supply.py, planner_demo_contracts.py
y planner_demo_control.py. Las capturas 01 a 03 (árbol de recursos) son de
la fase 2.

``CAPTURAS_DESDE=17`` rehace solo las de las fases 5 a 7 y
``CAPTURAS_DESDE=24`` solo las de la fase 7 (las anteriores dependen del
estado de los datos de su fase)."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_construction_planner'
PLAN = 'construction.resource.plan'
FULL = '.o_action_manager'
MODAL = '.modal-content'
DESDE = int(os.environ.get('CAPTURAS_DESDE', '1'))



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


def elegir(c, campo, texto):
    """Elige ``texto`` en el many2one ``campo`` del asistente abierto."""
    field = c.page.locator(f'.modal-content div[name={campo}] input')
    field.fill(texto)
    c.esperar(1200)
    c.page.locator('.o-autocomplete--dropdown-item').first.click()
    c.esperar(1500)


def fases_5_6(c, v1):
    """Fases 5 y 6: contratas, avance y liquidación semanal (P-05 a P-09)."""
    # 17. Asignar contrata (W-05, P-05): armado del piso a Gonza
    c.abrir_registro(PLAN, v1, ms=2000)
    c.texto('Asignar contrata', ms=2000)
    c.page.locator('.modal-content div[name=stage] input').click()
    c.esperar(600)
    c.page.locator('.o_select_menu_item', has_text='Armado').first.click()
    c.esperar(1500)
    elegir(c, 'partner_id', 'DEMO PLAN Armado Gonza')
    c.foto('17-asignar-contrata', selector=MODAL)
    c.clic('.modal-footer button.btn-secondary', ms=800)

    # 18. OC de servicio de Leandro en la obra (8 actividades, S/ 941.17)
    orders = buscar(c, 'purchase.order', [['construction_is_service_order', '=', True],
                                          ['partner_id.name', '=like', 'DEMO PLAN Leandro%']])
    c.abrir_registro('purchase.order', orders[-1], ms=2000)
    c.foto('18-oc-de-servicio', selector=FULL)

    # 19. Registrar avance (W-07, P-06): instalación mueble alto del piso
    c.abrir_registro(PLAN, v1, ms=2000)
    c.texto('Registrar avance', ms=2000)
    elegir(c, 'activity_id', 'DEMO PLAN Instalación mueble alto')
    c.foto('19-registrar-avance', selector=MODAL)
    c.clic('.modal-footer button.btn-secondary', ms=800)

    # 20. Avances por validar (P-07), por obra, contrata y semana
    c.abrir_accion(f'{M}.action_construction_progress_to_validate', ms=2000)
    for _i in range(3):
        headers = c.page.locator('.o_group_header:not(.o_group_open)')
        if headers.count():
            headers.first.click()
            c.esperar(1000)
    c.foto('20-avances-por-validar', selector=FULL)

    # 21. Liquidación semanal (P-08)
    settlements = buscar(c, 'construction.contract.settlement',
                         [['project_id.name', '=', 'DEMO PLAN MOMEN-35-26']])
    c.abrir_registro('construction.contract.settlement', settlements[0], ms=2000)
    c.foto('21-liquidacion-semanal', selector=FULL)

    # 22. Ambiente: pestaña «Recursos y avance» (P-09), cocina del Dpto 504
    space = buscar(c, 'project.task', [['project_id.name', '=', 'DEMO PLAN MOMEN-35-26'],
                                       ['parent_id.name', '=', 'Dpto 504'],
                                       ['construction_level', '=', 'space']])
    c.abrir_registro('project.task', space[0], ms=2000)
    c.texto('Recursos y avance', ms=1500)
    c.foto('22-recursos-y-avance', selector=FULL)

    # 23. Árbol de recursos con la medida «Avance»
    c.abrir_registro(PLAN, v1, ms=2000)
    c.clic('button[name=action_open_tree]', ms=2500)
    c.clic('.o_cp_toolbar button:has-text("Avance")', ms=1000)
    c.clic('tr[data-name="Piso 05"] .o_cp_caret', ms=1500)
    c.foto('23-arbol-avance', selector=FULL)


def fase_7(c, v1):
    """Fase 7: control (P-13), cuadrilla (W-06) y cambiar fechas (W-08)."""
    # 24. Pestaña «Control» del plan (P-13)
    c.abrir_registro(PLAN, v1, ms=2000)
    c.clic('a.nav-link[name=control]', ms=1500)
    c.foto('24-control', selector=FULL)

    # 25. Análisis de control en pivote: etapa › tipo de recurso
    c.clic('button[name=action_open_control_analysis]', ms=2500)
    c.foto('25-analisis-control', selector=FULL)

    # 26. Asignar cuadrilla (W-06): toda la obra con el rol propio
    c.abrir_registro(PLAN, v1, ms=2000)
    c.texto('Asignar cuadrilla', ms=2000)
    elegir(c, 'role_id', 'DEMO PLAN Instalador propio')
    resources = c.page.locator('.modal-content div[name=resource_ids] input')
    for name in ('DEMO PLAN Obrero propio 1', 'DEMO PLAN Obrero propio 2'):
        resources.fill(name)
        c.esperar(1200)
        c.page.locator('.o-autocomplete--dropdown-item').first.click()
        c.esperar(1200)
    c.page.locator('.modal-content div[name=hours_per_week] input').fill('8')
    c.page.locator('.modal-content div[name=weeks] input').fill('2')
    c.page.locator('.modal-content div[name=weeks] input').press('Tab')
    c.esperar(1500)
    c.foto('26-asignar-cuadrilla', selector=MODAL)
    c.clic('.modal-footer button.btn-secondary', ms=800)

    # 27. Cambiar fechas (W-08): postergar la instalación 7 días
    c.texto('Cambiar fechas', ms=2000)
    for stage in ('stage_production', 'stage_assembly', 'stage_finishing'):
        c.page.locator(f'.modal-content div[name={stage}] input').uncheck()
        c.esperar(600)
    c.esperar(1200)
    c.foto('27-cambiar-fechas', selector=MODAL)
    c.clic('.modal-footer button.btn-secondary', ms=800)


with Captura(M) as c:
    v1, v2 = buscar(c, PLAN, [['project_id.name', '=', 'DEMO PLAN MOMEN-35-26']], 'version')[:2]
    if DESDE >= 24:
        fase_7(c, v1)
        raise SystemExit
    if DESDE >= 17:
        fases_5_6(c, v1)
        fase_7(c, v1)
        raise SystemExit

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

    # --- Fases 5 a 7: contratas, liquidación, control y personal propio ---
    fases_5_6(c, v1)
    fase_7(c, v1)
