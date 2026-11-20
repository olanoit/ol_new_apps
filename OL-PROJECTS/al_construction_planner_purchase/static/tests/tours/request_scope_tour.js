/** @odoo-module **/

import { registry } from "@web/core/registry";

const BOX = "div[name=construction_scope]";
const field = (name) => `${BOX} .o_field_widget[name=${name}]`;
const OPTION = ".o-autocomplete--dropdown-item";

/**
 * Paquete 1.24: recorrido del requerimiento de obra con un usuario que pide
 * material. Cabecera sin pestañas (M124-04), «?» de cada campo (M124-03),
 * tipo de ambiente y «Traer materiales del plan» (M124-01) y lista de
 * Ambiente con su camino (M124-02).
 */
registry.category("web_tour.tours").add("al_construction_request_scope_124", {
    steps: () => [
        { trigger: ".o_list_button_add", run: "click" },
        { trigger: ".o_field_widget[name=project_id] input", run: "edit Obra MOMEN" },
        { trigger: `${OPTION}:contains(Obra MOMEN)`, run: "click" },
        // M124-04: almacén, jefe de proyecto e indicaciones en la cabecera; sin pestañas.
        { trigger: ".o_form_sheet:not(:has(.o_notebook))" },
        { trigger: ".o_form_sheet .o_field_widget[name=project_manager_id]" },
        { trigger: ".o_form_sheet .o_field_widget[name=note]" },
        { trigger: ".o_form_sheet .o_horizontal_separator:contains(Materiales)" },
        // M124-03: cada campo del recuadro tiene su «?».
        { trigger: `${BOX} label[for^=construction_stage_ids] sup` },
        { trigger: `${BOX} label[for^=construction_gantt_task_id] sup` },
        { trigger: `${field("construction_scope_2_label")} sup` },
        { trigger: `${field("construction_scope_3_label")} sup` },
        { trigger: `${field("construction_scope_type_label")}:contains(Tipo de ambiente) sup` },
        { trigger: `${field("construction_scope_1_label")} sup`, run: "hover" },
        { trigger: ".o-tooltip:contains(Puede elegir varios)" },
        // Etapa y piso.
        { trigger: `${field("construction_stage_ids")} input`, run: "edit Armado" },
        { trigger: `${OPTION}:contains(Armado)`, run: "click" },
        { trigger: `${field("construction_scope_1_ids")} input`, run: "edit Piso 05" },
        { trigger: `${OPTION}:contains(Piso 05)`, run: "click" },
        { trigger: `${field("construction_scope_1_ids")} .o_tag:contains(Piso 05)` },
        // M124-01: tipos del piso elegido, con su cantidad.
        { trigger: `${field("construction_scope_type_keys")} input`, run: "click" },
        { trigger: ".o_select_menu_item:contains(Closet (1))" },
        { trigger: ".o_select_menu_item:contains(Sin tipo (1))" },
        { trigger: ".o_select_menu_item:contains(Cocina (2))", run: "click" },
        { trigger: `${field("construction_scope_type_keys")} .o_tag:contains(Cocina)` },
        {
            trigger: `${field("construction_fetch_summary")}:contains(2 ambientes de Piso 05: 2 cocinas)`,
        },
        // M124-02: la lista de Ambiente muestra el camino y solo las cocinas.
        { trigger: `${field("construction_scope_3_ids")} input`, run: "edit Dpto" },
        { trigger: `${OPTION}:contains(Piso 05 · Dpto 501 · Cocina · 01)` },
        { trigger: `${OPTION}:contains(Piso 05 · Dpto 502 · Cocina · 01)` },
        { trigger: `${field("construction_scope_3_ids")}:not(:has(${OPTION}:contains(Closet)))` },
        { trigger: `${field("construction_scope_3_ids")} input`, run: "edit 502" },
        { trigger: `${field("construction_scope_3_ids")}:not(:has(${OPTION}:contains(Dpto 501)))` },
        { trigger: `${OPTION}:contains(Dpto 502 · Cocina)`, run: "click" },
        { trigger: `${field("construction_scope_3_ids")} .o_tag:contains(Dpto 502 · Cocina)` },
        { trigger: `${field("construction_scope_3_ids")} .o_tag .o_delete`, run: "click" },
        { trigger: `${field("construction_scope_3_ids")}:not(:has(.o_tag))` },
        // Traer materiales del plan: una línea por material, con su tipo.
        { trigger: `${BOX} button[name=action_construction_fetch_plan]`, run: "click" },
        {
            trigger:
                ".o_field_widget[name=line_ids] .o_data_row:contains(Bisagra):contains(Piso 05):contains(Cocina)",
        },
        { trigger: ".o_form_status_indicator_buttons.invisible, .o_form_saved" },
    ],
});
