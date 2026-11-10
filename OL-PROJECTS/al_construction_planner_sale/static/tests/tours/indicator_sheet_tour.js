/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Paquete 7 de CREVAL, CR-60: desde la obra, «Ficha de indicadores» abre la
 * ficha con los cuatro bloques, el plazo, el gráfico de avance y las tablas;
 * la estrella marca la obra como favorita.
 */
registry.category("web_tour.tours").add("al_construction_planner_indicator_sheet", {
    steps: () => [
        { trigger: '.o_notebook a.nav-link:contains("Calendario e ingresos")', run: "click" },
        { trigger: 'button[name="action_construction_indicator_sheet"]', run: "click" },
        { trigger: ".o_cp_indicator_sheet h4:contains(Obra MOMEN ingresos)" },
        { trigger: ".o_cp_ind_block_today .o_cp_ind_sale .o_cp_ind_card_value" },
        { trigger: ".o_cp_ind_block_close .o_cp_ind_eac" },
        { trigger: ".o_cp_is_timeline .o_cp_is_mark_end" },
        { trigger: ".o_cp_is_progress_chart svg" },
        { trigger: ".o_cp_is_progress_chart .o_cp_is_legend:contains(Avance físico)" },
        { trigger: ".o_cp_is_specialties tbody tr" },
        { trigger: ".o_cp_is_star .fa-star-o", run: "click" },
        { trigger: ".o_cp_is_star .fa-star.text-warning" },
    ],
});
