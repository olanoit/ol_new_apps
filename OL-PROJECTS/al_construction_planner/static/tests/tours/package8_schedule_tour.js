/** @odoo-module **/

import { registry } from "@web/core/registry";

function env() {
    return odoo.__WOWL_DEBUG__.root.env;
}

/**
 * CREVAL 8, CR-67, CR-68 y CR-70: la partida muestra «Nivel de obra» con el
 * nombre de la plantilla y las fechas de la pestaña PLAN (13 al 26 de julio);
 * «Etapas del cronograma» lleva las columnas de la plantilla.
 */
registry.category("web_tour.tours").add("al_construction_package8_schedule", {
    steps: () => [
        {
            content: "Abrir la partida",
            trigger: ".o_main_navbar",
            run: async () => {
                const [task] = await env().services.orm.search(
                    "project.task", [["name", "ilike", "Muro del eje B"],
                                     ["project_id.name", "ilike", "OBR-03"]], { limit: 1 });
                await env().services.action.doAction({
                    type: "ir.actions.act_window", res_model: "project.task", res_id: task,
                    views: [[false, "form"]], target: "current",
                });
            },
        },
        { trigger: ".o_form_view .o_field_widget[name=construction_level_label]:contains(Partida)" },
        {
            content: "Fecha planeada: los días de PLAN",
            trigger: ".o_form_view .o_field_widget[name=date_deadline]",
            run() {
                const texts = [this.anchor.textContent];
                for (const input of this.anchor.querySelectorAll("input")) {
                    texts.push(input.value);
                }
                const text = texts.join(" ");
                if (!/\b13\b/.test(text) || !/\b26\b/.test(text) || /\b12\b|\b25\b/.test(
                        text.replace(/\d{1,2}:\d{2}(:\d{2})?/g, ""))) {
                    throw new Error(`Fecha planeada fuera de los días de PLAN: ${text}`);
                }
            },
        },
        {
            content: "Etapas del cronograma",
            trigger: ".o_form_view",
            run: async () => {
                await env().services.action.doAction(
                    "al_construction_planner.action_construction_space_stage",
                    { clearBreadcrumbs: true });
            },
        },
        { trigger: ".o_list_view th[data-name=floor_task_id]:contains(Sub-especialidad)" },
        { trigger: ".o_list_view th[data-name=space_task_id]:contains(Partida)" },
        { trigger: ".o_list_view:not(:has(th[data-name=apartment_task_id]))" },
    ],
});
