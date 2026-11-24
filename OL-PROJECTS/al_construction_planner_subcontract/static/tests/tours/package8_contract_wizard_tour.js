/** @odoo-module **/

import { registry } from "@web/core/registry";

const field = (name) => `.modal .o_field_widget[name=${name}]`;
const OPTION = ".o-autocomplete--dropdown-item";

/**
 * CREVAL 8, CR-71: «Asignar contrata» abierto desde el menú ofrece los planes
 * de la compañía, y «Toda la obra» sigue a la «Selección».
 */
registry.category("web_tour.tours").add("al_construction_package8_contract_wizard", {
    steps: () => [
        {
            content: "Abrir «Asignar contrata» sin plan, como el menú",
            trigger: ".o_main_navbar",
            run: async () => {
                await odoo.__WOWL_DEBUG__.root.env.services.action.doAction(
                    "al_construction_planner_subcontract.action_plan_contract_wizard");
            },
        },
        { trigger: `${field("plan_id")} input`, run: "edit PLR-P8" },
        { trigger: `${OPTION}:contains(PLR-P8)`, run: "click" },
        { trigger: `${field("whole_project")} input:checked` },
        { trigger: `${field("task_ids")} input`, run: "edit Muro del eje B" },
        { trigger: `${OPTION}:contains(Muro del eje B)`, run: "click" },
        { trigger: `${field("task_ids")} .o_tag:contains(Muro del eje B)` },
        { trigger: `${field("whole_project")} input:not(:checked)` },
        { trigger: `${field("task_ids")} .o_tag .o_delete`, run: "click" },
        { trigger: `${field("whole_project")} input:checked` },
        { trigger: ".modal .btn-close", run: "click" },
        { trigger: "body:not(:has(.modal))" },
    ],
});
