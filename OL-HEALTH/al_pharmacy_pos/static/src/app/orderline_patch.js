import { formatCurrency } from "@web/core/currency";
import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/components/orderline/orderline";

patch(Orderline.prototype, {
    /** En pantalla y en el ticket: «1 Paracetamol (Caja x 100)» y el precio por caja. */
    get lineScreenValues() {
        const values = super.lineScreenValues;
        const line = this.line;
        const presentation = line.pharmacy_presentation_id;
        const count = line.order_id && line.getPharmacyPresentationCount();
        if (!presentation || !count) {
            return values;
        }
        // Total de la línea entre las presentaciones: el precio unitario ya
        // viene redondeado (0,177 → 0,18) y por 10 daba S/ 1,80 con un total
        // de S/ 1,77.
        const presentationPrice = formatCurrency(line.displayPrice / count, line.currency.id);
        return {
            ...values,
            name: `${values.name} (${presentation.display_name})`,
            unitPart: String(count),
            decimalPart: false,
            displayPriceUnit:
                values.displayPriceUnit && `${presentationPrice} / ${presentation.display_name}`,
        };
    },
});
