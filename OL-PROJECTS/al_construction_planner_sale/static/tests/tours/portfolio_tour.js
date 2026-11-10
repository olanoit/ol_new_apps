/** @odoo-module **/

import { registry } from "@web/core/registry";

const ROW = '.o_cp_home_portfolio tbody tr.o_cp_home_row_budget:contains("Obra MOMEN ingresos")';

/**
 * Paquete 7 de CREVAL, CR-59 y CR-65: el Inicio abre en «En ejecución» con el
 * total de la cartera y dos filas por obra; la favorita queda primera con
 * cualquier orden; tocar la obra abre su ficha.
 */
registry.category("web_tour.tours").add("al_construction_planner_portfolio", {
    steps: () => [
        { trigger: ".o_cp_home_tab_execution.active" },
        { trigger: ".o_cp_home_totals .o_cp_ind_block_today .o_cp_ind_sale" },
        { trigger: ".o_cp_home_totals .o_cp_ind_block_month:contains(venta proyectada de la empresa)" },
        { trigger: `${ROW} + tr.o_cp_home_row_executed td.fw-bold` },
        { trigger: ".o_cp_home_pending .o_cp_home_pending_total" },
        { trigger: `${ROW} .o_cp_home_star`, run: "click" },
        { trigger: `${ROW} .o_cp_home_star .fa-star.text-warning` },
        { trigger: '.o_cp_home_portfolio tbody tr:first-child:contains("Obra MOMEN ingresos")' },
        { trigger: ".o_cp_home_sort", run: "click" },
        { trigger: ".o_cp_home_sort_late", run: "click" },
        { trigger: '.o_cp_home_portfolio tbody tr:first-child:contains("Obra MOMEN ingresos")' },
        { trigger: ".o_cp_home_f_favorites", run: "click" },
        { trigger: '.o_cp_home_portfolio tbody:not(:has(tr.o_cp_home_row_budget:not(:contains("Obra MOMEN ingresos"))))' },
        { trigger: `${ROW} a.o_cp_home_work`, run: "click" },
        { trigger: ".o_cp_indicator_sheet h4:contains(Obra MOMEN ingresos)" },
    ],
});
