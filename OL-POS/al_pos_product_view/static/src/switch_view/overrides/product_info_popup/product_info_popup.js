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

    // --- Tarjetas de inventario (una por almacén) ---------------------------
    formatStockQty(qty) {
        return this.env.utils.formatProductQty(qty ?? 0, false);
    },

    /** Solo los almacenables pueden estar «sin stock» (misma regla que el
     * badge de filas y tarjetas). */
    isOutOfStock(warehouse) {
        return !!this.props.productTemplate?.is_storable && warehouse.free_qty <= 0;
    },

    /** Almacén de esta caja: el core lo pone primero en la lista cuando el
     * tipo de operación de la caja tiene almacén. */
    isCurrentWarehouse(warehouse, index) {
        const warehouseId = this.pos.config.picking_type_id?.warehouse_id?.id;
        return warehouseId ? warehouse.id === warehouseId : index === 0;
    },
});
