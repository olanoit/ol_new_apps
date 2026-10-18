import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

function choosePresentation(label) {
    return {
        content: `elegir la presentación ${label}`,
        trigger: `.modal .selection-item:contains("${label}")`,
        run: "click",
    };
}

registry.category("web_tour.tours").add("al_pharmacy_pos_presentation", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // Blíster de 7 a 1,00: la línea muestra 1 blíster y suma 1,00 (no 0,98).
            ProductScreen.clickDisplayedProduct("Paracetamol DEMO"),
            choosePresentation("Blíster x 7"),
            ProductScreen.selectedOrderlineHas("Paracetamol DEMO (Blíster x 7)", "1", "1.00"),
            // Unidad suelta al precio del producto.
            ProductScreen.clickDisplayedProduct("Paracetamol DEMO"),
            choosePresentation("Unidad"),
            ProductScreen.totalAmountIs("1.20"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.00" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
        ].flat(),
});
