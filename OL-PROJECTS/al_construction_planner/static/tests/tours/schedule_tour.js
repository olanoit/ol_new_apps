/** @odoo-module **/

import { registry } from "@web/core/registry";

const row = (name) => `.gantt_row:has(.gantt_tree_content:contains("${name}"))`;
const CONTRACT = "al_construction_planner.action_plan_contract_wizard";

/**
 * Cronograma con recursos (P-15), criterio 11: con el filtro «Instalación»,
 * marcar el piso 05 marca sus filas hijas y «Asignar contrata» abre W-05 con
 * las 8 actividades de instalación del piso por S/ 941.17 (se busca «941»: el
 * separador decimal depende del idioma del usuario).
 */
registry.category("web_tour.tours").add("al_construction_planner_schedule", {
    steps: () => [
        { trigger: ".o_cp_schedule_plan" },
        { trigger: `${row("Piso 05")}` },
        { trigger: `${row("Producción")}` },
        { trigger: ".o_cp_stage_filter", run: "select installation" },
        { trigger: `${row("Instalación")}:not(:has(.algantt-check-on))` },
        { trigger: `.o_cp_load_table td:contains(Instalación)` },
        { trigger: `${row("Piso 05")} .algantt-check`, run: "click" },
        { trigger: `${row("Piso 05")} .algantt-check-on` },
        { trigger: `${row("Dpto 501")} .algantt-check-on` },
        { trigger: `${row("Instalación")} .algantt-check-on` },
        { trigger: ".algantt-selection-count:contains(1)" },
        { trigger: ".o_cp_summary_modules:contains(66)" },
        { trigger: ".o_cp_schedule_summary:contains(941)" },
        { trigger: `.algantt-extra-button[data-key="${CONTRACT}"]:enabled`, run: "click" },
        { trigger: ".modal .o_field_widget[name=amount_total]:contains(941)" },
        { trigger: ".modal .o_field_widget[name=line_ids]:has(.o_data_row:eq(7)):not(:has(.o_data_row:eq(8)))" },
        { trigger: ".modal .o_form_button_cancel, .modal .btn-close", run: "click" },
        { trigger: "body:not(:has(.modal))" },
    ],
});
