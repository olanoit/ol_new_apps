import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

patch(PosOrderline.prototype, {
    /**
     * El precio de una línea de presentación es el de la presentación entre
     * sus unidades (S/ 1,00 / 7): no se redondea a los decimales del precio,
     * o el blíster sumaría S/ 0,98.
     */
    setUnitPrice(price) {
        if (this.pharmacy_presentation_id) {
            const parsed = !isNaN(price) ? price : parseFloat("" + price);
            this.price_unit = parsed || 0;
            return;
        }
        return super.setUnitPrice(price);
    },

    /** Número de presentaciones de la línea, o 0 si es una cantidad suelta. */
    getPharmacyPresentationCount() {
        const presentation = this.pharmacy_presentation_id;
        if (!presentation || !presentation.factor) {
            return 0;
        }
        const count = this.qty / presentation.factor;
        return Math.abs(count - Math.round(count)) < 1e-6 ? Math.round(count) : 0;
    },

    canBeMergedWith(orderline) {
        if (this.pharmacy_presentation_id?.id !== orderline.pharmacy_presentation_id?.id) {
            return false;
        }
        return super.canBeMergedWith(orderline);
    },
});
