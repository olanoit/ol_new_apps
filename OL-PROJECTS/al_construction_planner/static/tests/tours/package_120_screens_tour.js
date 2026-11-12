import { registry } from "@web/core/registry";

/**
 * Paquete 1.20: abre cada opción de Ejecución, Abastecimiento, Contratas y
 * Configuración (M120-01, M120-02), usa «Programar» y «Ejecutar» del plan
 * (M120-08) y abre la ficha de una actividad (M120-06). Falla si algo da error.
 */
const XMLIDS = [
    "al_construction_planner.menu_planner_execution",
    "al_construction_planner.menu_planner_supply",
    "al_construction_planner.menu_planner_contracts",
    "al_construction_planner.menu_planner_config",
];

function leaves(menu, all) {
    const result = [];
    for (const id of menu.children || []) {
        const child = all[id];
        if (!child) {
            continue;
        }
        if (child.actionID) {
            result.push(child);
        }
        result.push(...leaves(child, all));
    }
    return result;
}

registry.category("web_tour.tours").add("al_construction_package_120_screens", {
    steps: () => [
        {
            content: "Cada opción de los menús nuevos abre su vista",
            trigger: ".o_main_navbar",
            // Recorre decenas de opciones: más tiempo que un paso normal.
            timeout: 60000,
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const all = env.services.menu.getAll().reduce((acc, menu) => {
                    acc[menu.id] = menu;
                    return acc;
                }, {});
                const byXmlid = Object.values(all).filter((menu) => XMLIDS.includes(menu.xmlid));
                if (byXmlid.length < 4) {
                    throw new Error(`Faltan menús de la barra: ${byXmlid.map((m) => m.xmlid)}`);
                }
                for (const top of byXmlid) {
                    for (const item of leaves(top, all)) {
                        await env.services.action.doAction(item.actionID, { clearBreadcrumbs: true });
                        // Los asistentes se abren en ventana: se cierra.
                        await env.services.action.doAction({ type: "ir.actions.act_window_close" });
                    }
                }
            },
        },
        {
            content: "Abrir el plan aprobado",
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [plan] = await env.services.orm.searchRead(
                    "construction.resource.plan",
                    [["project_id.name", "=", "Obra pantallas 1.20 (test)"]],
                    ["id"]
                );
                await env.services.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "construction.resource.plan",
                    res_id: plan.id,
                    views: [[false, "form"]],
                });
            },
        },
        { content: "Grupo «Programar»", trigger: ".o_construction_plan_menu_program", run: "click" },
        { trigger: ".o_construction_plan_item:contains('Cambiar fechas')", run: "click" },
        { trigger: ".modal .o_form_view" },
        { trigger: ".modal .btn-close, .modal .o_form_button_cancel", run: "click" },
        { content: "Grupo «Ejecutar»", trigger: ".o_construction_plan_menu_execute", run: "click" },
        { trigger: ".o_construction_plan_item:contains('Registrar avance')", run: "click" },
        { trigger: ".modal .o_form_view" },
        { trigger: ".modal .btn-close, .modal .o_form_button_cancel", run: "click" },
        { trigger: "body:not(:has(.modal))" },
        {
            content: "La ficha de una actividad de obra",
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [activity] = await env.services.orm.searchRead(
                    "construction.labor.activity", [], ["id"], { limit: 1 }
                );
                await env.services.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "construction.labor.activity",
                    res_id: activity.id,
                    views: [[false, "form"]],
                });
            },
        },
        { trigger: ".o_form_view div[name=hang_role]" },
    ],
});
