/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * CREVAL 8, CR-66: el comercial confirma la cotización de una obra que ya
 * existe.
 */
registry.category("web_tour.tours").add("al_construction_package8_confirm", {
    steps: () => [
        { trigger: ".o_form_view .o_field_widget[name=name]" },
        { trigger: ".o_statusbar_buttons button[name=action_confirm]", run: "click" },
        { trigger: ".o_statusbar_status .o_arrow_button_current[data-value=sale]" },
    ],
});

/**
 * CREVAL 8, CR-66: la obra muestra la orden en «Calendario e ingresos» y el
 * historial dice qué cotización la puso.
 */
registry.category("web_tour.tours").add("al_construction_package8_contract_order", {
    steps: () => [
        { trigger: ".o_form_view .o_notebook .nav-link:contains(Calendario e ingresos)", run: "click" },
        { trigger: ".o_field_widget[name=construction_sale_order_id]", run() {
            const input = this.anchor.querySelector("input");
            const text = ((input && input.value) || this.anchor.textContent || "").trim();
            if (!text) {
                throw new Error("La obra no tiene la orden de venta del contrato");
            }
        } },
        { trigger: ".o-mail-Message:contains(Al confirmar la cotización)" },
        { trigger: ".o-mail-Message:contains(Al confirmar la cotización):contains(Comercial)" },
    ],
});
