/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

console.log("[al_pos_vendedor] order.js cargado — aplicando patch a PosOrder");

patch(PosOrder.prototype, {
    get vendedorName() {
        return this.seller_id?.name || null;
    },
});
