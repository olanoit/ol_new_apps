/** @odoo-module **/

import { registry } from "@web/core/registry";

const row = (name) => `.gantt_row:has(.gantt_tree_content:contains("${name}"))`;
const CONTRACT = "al_construction_planner_subcontract.action_plan_contract_wizard";
const PURCHASE = "al_construction_planner_purchase.action_plan_purchase_wizard";

/**
 * Cronograma con recursos (P-15), criterio 11: con el filtro «2.1 Instalación»
 * (filtro de etapas en árbol, v1.8),
 * marcar el piso 05 marca sus filas hijas y «Asignar contrata» abre W-05 con
 * las 8 actividades de instalación del piso por S/ 941.17 (se busca «941»: el
 * separador decimal depende del idioma del usuario).
 *
 * Paquete 1.15: la barra en filas por tipo de acción con los nombres de las
 * acciones (M115-01 y M115-02) y el panel ampliable (M115-03).
 */
registry.category("web_tour.tours").add("al_construction_planner_schedule", {
    steps: () => [
        { trigger: ".o_cp_schedule_plan" },
        { trigger: `${row("Piso 05")}` },
        { trigger: `${row("1.1 Producción de piezas")}` },
        { trigger: ".o_cp_stage_filter .dropdown-toggle", run: "click" },
        { trigger: '.o_cp_stage_node[data-code="installation"]', run: "click" },
        { trigger: '.o_cp_stage_node[data-code="installation"] .o_cp_on' },
        { trigger: `body:not(:has(${row("Producción de piezas")}))` },
        { trigger: `${row("2.1 Instalación")}:not(:has(.algantt-check-on))` },
        { trigger: `.o_cp_load_table td:contains(Instalación)` },
        { trigger: `${row("Piso 05")} .algantt-check`, run: "click" },
        { trigger: `${row("Piso 05")} .algantt-check-on` },
        { trigger: `${row("Dpto 501")} .algantt-check-on` },
        { trigger: `${row("2.1 Instalación")} .algantt-check-on` },
        { trigger: ".algantt-selection-count:contains(1)" },
        { trigger: ".o_cp_summary_modules:contains(66)" },
        { trigger: ".o_cp_schedule_summary:contains(941)" },
        // M115-01 y M115-02: una fila por grupo, con el nombre de la acción.
        { trigger: '.algantt-actionbar-row[data-group="consult"] .algantt-extra-button[data-key="io_matrix"]' },
        { trigger: `.algantt-actionbar-row[data-group="program"] .algantt-extra-button[data-key="${PURCHASE}"]:contains(Programar compra masiva)` },
        { trigger: `.algantt-actionbar-row[data-group="execute"] .algantt-extra-button[data-key="${CONTRACT}"]` },
        { trigger: '.algantt-actionbar-row[data-group="consult"] .algantt-selection-count' },
        // M115-03: ampliar muestra contrata, cantidad, ejecutado y saldo.
        { trigger: ".o_cp_schedule_panel:not(:has(th.o_cp_col_partner))" },
        { trigger: ".o_cp_panel_expand", run: "click" },
        { trigger: ".o_cp_schedule_panel th.o_cp_col_partner" },
        { trigger: ".o_cp_schedule_panel th.o_cp_col_executed" },
        { trigger: ".o_cp_schedule_panel th.o_cp_col_balance" },
        { trigger: ".o_cp_panel_fullscreen", run: "click" },
        { trigger: ".o_cp_schedule_panel.o_cp_panel_full" },
        { trigger: ".o_cp_panel_fullscreen", run: "click" },
        { trigger: ".o_cp_schedule_panel:not(.o_cp_panel_full)" },
        { trigger: ".o_cp_panel_expand", run: "click" },
        { trigger: ".o_cp_schedule_panel:not(:has(th.o_cp_col_partner))" },
        { trigger: `.algantt-extra-button[data-key="${CONTRACT}"]:enabled`, run: "click" },
        { trigger: ".modal .o_field_widget[name=amount_total]:contains(941)" },
        { trigger: ".modal .o_field_widget[name=line_ids]:has(.o_data_row:eq(7)):not(:has(.o_data_row:eq(8)))" },
        { trigger: ".modal .o_form_button_cancel, .modal .btn-close", run: "click" },
        { trigger: "body:not(:has(.modal))" },
    ],
});
