import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("al_pharmacy_pos_dispensation", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // La marca ofrece el genérico en DCI (Ley 32033).
            ProductScreen.clickDisplayedProduct("Cipro Marca 500 mg"),
            {
                content: "el genérico aparece entre las alternativas",
                trigger: '.modal .selection-item:contains("Ciprofloxacino 500 mg tableta")',
                run: "click",
            },
            // Producto con receta: se registra en la caja.
            { trigger: ".modal #rx_number", run: "edit 000321" },
            { trigger: ".modal #rx_prescriber", run: "edit Dra. Ana Torres" },
            { trigger: ".modal #rx_license", run: "edit 067890" },
            { trigger: ".modal #rx_patient", run: "edit Rosa Mendoza" },
            {
                content: "registrar la receta",
                trigger: '.modal button:contains("Registrar receta")',
                run: "click",
            },
            ProductScreen.selectedOrderlineHas("Ciprofloxacino 500 mg tableta", "1", "2.00"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.00" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
        ].flat(),
});
