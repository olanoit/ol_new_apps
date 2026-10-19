import { patch } from "@web/core/utils/patch";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";

patch(ReceiptScreen.prototype, {
    /** Líneas vendidas por unidad suelta de un producto con caja o blíster. */
    get pharmacyFractionLines() {
        return this.currentOrder
            .getOrderlines()
            .filter(
                (line) =>
                    line.qty > 0 &&
                    !line.pharmacy_presentation_id &&
                    line.product_id.product_tmpl_id.pharmacy_ok &&
                    this.pos.getPharmacyPresentations(line.product_id.product_tmpl_id).length
            );
    },

    /** Rótulo del envase de la venta fraccionada (DS 020-2024-SA, art. 48). */
    printPharmacyFractionLabel() {
        const orderId = this.currentOrder.id;
        if (typeof orderId !== "number") {
            return;
        }
        window.open(`/report/pdf/al_pharmacy_pos.report_pos_fraction_label/${orderId}`, "_blank");
    },
});
