/** @odoo-module **/

import { registry } from "@web/core/registry";

const ROW = '.o_cp_supply_table tbody tr:has(.o_cp_supply_product:contains("Melamina tour abastecimiento"))';

/**
 * Abastecimiento de la obra (P-18): la fila del producto con su cantidad a
 * comprar y la alerta de proveedor; marcarla y «Compra masiva» abre W-02 con
 * ese producto.
 */
registry.category("web_tour.tours").add("al_construction_planner_supply_board", {
    steps: () => [
        { trigger: ".o_cp_supply_project", run: "selectByLabel Obra tour abastecimiento" },
        { trigger: `${ROW} td.fw-bold:contains(13)` },
        { trigger: '.o_cp_supply_alerts:contains("sin proveedor habitual")' },
        { trigger: ".o_cp_supply_purchase:disabled" },
        { trigger: `${ROW} input[type=checkbox]`, run: "click" },
        { trigger: ".o_cp_supply_table tfoot:contains(1 productos)" },
        { trigger: ".o_cp_supply_purchase:enabled", run: "click" },
        { trigger: '.modal .o_field_widget[name=product_ids]:contains("Melamina tour abastecimiento")' },
        { trigger: ".modal .o_field_widget[name=line_ids] .o_data_row" },
        { trigger: ".modal .btn-close", run: "click" },
        { trigger: "body:not(:has(.modal))" },
    ],
});
