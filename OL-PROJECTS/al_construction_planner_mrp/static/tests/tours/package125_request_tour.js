/** @odoo-module **/

import { registry } from "@web/core/registry";

const env = () => odoo.__WOWL_DEBUG__.root.env;

/**
 * Paquete 1.25, M125-01 y M125-02: la jefatura de proyectos pide a producción
 * desde el asistente y termina en el requerimiento; sus botones inteligentes
 * abren las órdenes y la orden muestra su requerimiento.
 */
registry.category("web_tour.tours").add("al_construction_package125_create", {
    steps: () => [
        // Por el árbol de recursos, como el usuario: así la prueba ve si el
        // diálogo del asistente se cierra al abrir el requerimiento.
        {
            content: "Abrir el árbol de recursos",
            trigger: ".o_main_navbar",
            run: async () => {
                await env().services.action.doAction(
                    "al_construction_planner.action_construction_plan_tree");
            },
        },
        {
            content: "Elegir el plan de la obra",
            trigger: ".o_action select:has(option:contains(PLR-M125))",
            run: ({ anchor }) => {
                const option = [...anchor.options].find((o) => o.text.includes("PLR-M125"));
                anchor.value = option.value;
                anchor.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Marcar toda la obra",
            trigger: "tr.o_cp_tree_row:first-child:contains(MOMEN) .o_cp_check",
            run: "click",
        },
        {
            content: "Abrir «Requerimiento de fabricación»",
            trigger: ".o_action button:contains(Requerimiento de fabricación)",
            run: "click",
        },
        { trigger: ".modal .o_field_widget[name=line_ids] .o_data_row" },
        {
            content: "Crear el requerimiento",
            trigger: ".modal button[name=action_create]",
            run: "click",
        },
        { trigger: "body:not(:has(.modal))" },
        { trigger: ".o_form_view .oe_title:contains(Requerimiento de fabricación) h1:contains(RQF/)" },
        { trigger: ".o_statusbar_status .o_arrow_button_current:contains(Borrador)" },
        { trigger: ".o_field_widget[name=space_labels]:contains(Piso 05 / Dpto 501 / Cocina)" },
        { trigger: ".o_field_widget[name=production_ids] .o_data_row:nth-child(2)" },
        {
            content: "Botón «Órdenes de fabricación»",
            trigger: "button[name=action_view_productions]:contains(2)",
            run: "click",
        },
        // Esperar la lista de órdenes: sin esto el clic siguiente puede caer
        // en la lista incrustada del requerimiento, antes de que cargue.
        { trigger: ".o_control_panel .o_last_breadcrumb_item:contains(Órdenes de fabricación)" },
        {
            content: "Abrir la primera orden",
            trigger: ".o_view_controller.o_list_view .o_data_row:first-child .o_data_cell[name=name]",
            run: "click",
        },
        { trigger: ".o_form_view button[name=action_view_construction_request]:contains(Requerimiento de fabricación ·)" },
        // En Odoo 19 los botones inteligentes van en el panel de control (.o-form-buttonbox).
        { trigger: ".o-form-buttonbox button[name=action_view_construction_request]:contains(RQF/)" },
        {
            content: "La etiqueta abre el requerimiento",
            trigger: ".oe_title button[name=action_view_construction_request]",
            run: "click",
        },
        { trigger: ".o_form_view .oe_title h1:contains(RQF/)" },
        { trigger: ".o_form_view button[name=action_cancel]" },
    ],
});

/**
 * M125-02 y M125-04: el jefe de producción abre las órdenes del planificador,
 * agrupadas por requerimiento, y cancela el requerimiento.
 */
registry.category("web_tour.tours").add("al_construction_package125_cancel", {
    steps: () => [
        {
            content: "Menú «Órdenes de fabricación» del planificador",
            trigger: ".o_main_navbar",
            run: async () => {
                await env().services.action.doAction(
                    "al_construction_planner_mrp.action_planner_productions");
            },
        },
        { trigger: ".o_list_view .o_group_header:contains(RQF/):contains(Obra MOMEN)" },
        { trigger: ".o_searchview .o_facet_values:contains(Requerimiento de fabricación)" },
        {
            content: "Menú «Requerimientos de fabricación»",
            trigger: ".o_list_view",
            run: async () => {
                await env().services.action.doAction(
                    "al_construction_planner_mrp.action_construction_manufacturing_request");
            },
        },
        {
            trigger: ".o_list_view .o_data_row:first-child .o_data_cell[name=name]:contains(RQF/)",
            run: "click",
        },
        {
            content: "Cancelar el requerimiento",
            trigger: ".o_form_view .o_form_statusbar button[name=action_cancel]",
            run: "click",
        },
        { trigger: ".modal .modal-title:contains(Cancelar RQF/)" },
        { trigger: ".modal .o_field_widget[name=draft_production_ids] .o_data_row:nth-child(2)" },
        {
            trigger: ".modal button[name=action_cancel_drafts]",
            run: "click",
        },
        { trigger: "body:not(:has(.modal))" },
        { trigger: ".o_statusbar_status .o_arrow_button_current:contains(Cancelado)" },
        { trigger: ".o_form_view:not(:has(.o_form_statusbar button[name=action_cancel]))" },
    ],
});
