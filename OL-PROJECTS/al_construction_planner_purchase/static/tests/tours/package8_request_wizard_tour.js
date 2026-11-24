/** @odoo-module **/

import { registry } from "@web/core/registry";

const field = (name) => `.modal .o_field_widget[name=${name}]`;

/**
 * CREVAL 8, CR-70: «Agrupar por» del requerimiento desde el plan ofrece los
 * niveles de la plantilla de la obra, con su nombre, y la primera columna de
 * las líneas se llama como el nivel elegido.
 */
registry.category("web_tour.tours").add("al_construction_package8_request_wizard", {
    steps: () => [
        {
            content: "Abrir el asistente desde el plan",
            trigger: ".o_main_navbar",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [plan] = await env.services.orm.search(
                    "construction.resource.plan", [["name", "=", "PLR-P8"]], { limit: 1 });
                await env.services.action.doAction(
                    "al_construction_planner_purchase.action_plan_request_wizard",
                    { additionalContext: { default_plan_id: plan } });
            },
        },
        { trigger: `${field("group_by")} .o_radio_item:contains(Sub-especialidad) input:checked` },
        { trigger: `${field("group_by")} .o_radio_item:contains(Partida)` },
        { trigger: `${field("group_by")}:not(:contains(Departamento)):not(:contains(Piso)):not(:contains(Ambiente))` },
        { trigger: `${field("line_ids")} th[data-name=floor_task_id]:contains(Sub-especialidad)` },
        { trigger: `${field("group_by")} .o_radio_item:contains(Partida) input`, run: "click" },
        { trigger: `${field("line_ids")} th[data-name=space_task_id]:contains(Partida)` },
        { trigger: `${field("line_ids")}:not(:has(th[data-name=floor_task_id]))` },
        { trigger: ".modal .btn-close", run: "click" },
        { trigger: "body:not(:has(.modal))" },
    ],
});
