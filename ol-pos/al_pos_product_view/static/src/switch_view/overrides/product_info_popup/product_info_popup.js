/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductInfoPopup } from "@point_of_sale/app/components/popups/product_info_popup/product_info_popup";
import { getTaxAwareProductPrice } from "@al_pos_product_view/switch_view/utils/product_price";

/**
 * Precio con impuestos para las tarjetas de Productos opcionales (este
 * módulo) y las de Productos bioequivalentes (el módulo de integración
 * Yapp, que llama al mismo método desde su propio xpath). Ambas tarjetas
 * mostraban el `list_price` crudo (sin tarifa, sin impuestos); esto las
 * hace coincidir con la fila "Precio con/sin impuestos" mostrada para el
 * propio producto del popup.
 */
patch(ProductInfoPopup.prototype, {
    /** Finanzas/Pedido: ocultos al rol «minimal» de pos_hr, igual que el
     * bloque nativo `.financials-order` que este módulo reubica. */
    get alShowFinancials() {
        return this.pos.getCashier()?._role !== "minimal";
    },

    getDisplayPrice(product) {
        return getTaxAwareProductPrice(this.pos, product);
    },
});
