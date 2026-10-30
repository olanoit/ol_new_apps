import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/** Vendedor de la venta en el recibo (mismo dato que pos.order.receipt). */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        data.extra_data.al_seller_name = this.order?.seller_id?.name || false;
        return data;
    },
});
