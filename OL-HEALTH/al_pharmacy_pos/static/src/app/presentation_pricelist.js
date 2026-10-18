import { patch } from "@web/core/utils/patch";
import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

// Mientras se calcula el precio de una presentación: diferencia entre su
// precio por unidad y el precio de lista (ver getPrice).
let presentationOffset = 0;

const isSamePrice = (a, b) => Math.abs(a - b) < 1e-9;

patch(ProductTemplate.prototype, {
    /**
     * Precio por unidad de una línea de presentación con la lista de precios.
     * Las reglas sobre el precio de venta (porcentaje, fórmula) se aplican al
     * precio de la presentación entre sus unidades: un 10 % de convenio deja
     * la caja de S/ 50,00 en S/ 45,00. Un precio fijo o sobre el costo es por
     * unidad del producto, como en el resto de Odoo.
     */
    getPharmacyPresentationUnitPrice(presentation, pricelist, quantity) {
        const variant = this.product_variant_ids[0];
        presentationOffset = presentation.price / presentation.factor - variant.lst_price;
        try {
            return this.getPrice(
                pricelist,
                Math.abs(quantity) || presentation.factor,
                presentationOffset,
                false,
                variant
            );
        } finally {
            presentationOffset = 0;
        }
    },

    getPrice(pricelist, quantity, price_extra = 0, recurring = false, ...args) {
        // Regla basada en otra lista de precios: Odoo la vuelve a calcular sin
        // el precio extra; se conserva la base de la presentación.
        if (recurring && presentationOffset) {
            price_extra = presentationOffset;
        }
        return super.getPrice(pricelist, quantity, price_extra, recurring, ...args);
    },
});

patch(PosOrderline.prototype, {
    getPharmacyPresentationUnitPrice(pricelist = this.order_id.pricelist_id, quantity = this.qty) {
        return this.product_id.product_tmpl_id.getPharmacyPresentationUnitPrice(
            this.pharmacy_presentation_id,
            pricelist,
            quantity
        );
    },

    /** Precio de la presentación sin cambios a mano del cajero. */
    hasPharmacyPresentationPrice(pricelist = this.order_id.pricelist_id) {
        return (
            Boolean(this.pharmacy_presentation_id) &&
            isSamePrice(this.price_unit, this.getPharmacyPresentationUnitPrice(pricelist))
        );
    },

    /** La regla de la lista de precios puede depender de la cantidad. */
    setQuantity(quantity, keep_price) {
        const repricing = !keep_price && this.hasPharmacyPresentationPrice();
        const result = super.setQuantity(...arguments);
        if (repricing && result === true) {
            this.setUnitPrice(this.getPharmacyPresentationUnitPrice());
        }
        return result;
    },
});

patch(PosOrder.prototype, {
    /**
     * Las líneas de presentación llevan su precio como «manual» (Odoo no lo
     * vuelve a calcular): al cambiar la lista de precios, por ejemplo al
     * elegir un cliente con convenio, se recalculan si nadie las cambió.
     */
    setPricelist(pricelist) {
        const oldPricelist = this.pricelist_id;
        const lines = this.lines.filter((line) => line.hasPharmacyPresentationPrice(oldPricelist));
        const result = super.setPricelist(...arguments);
        for (const line of lines) {
            line.setUnitPrice(line.getPharmacyPresentationUnitPrice(pricelist || false));
        }
        return result;
    },
});
