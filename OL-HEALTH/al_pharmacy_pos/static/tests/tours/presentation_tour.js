import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
// Odoo 20: la pantalla de recibo es FeedbackScreen.
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
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
            ProductScreen.clickDisplayedProduct("Loratadina 10 mg"),
            choosePresentation("Blíster x 7"),
            ProductScreen.selectedOrderlineHas("Loratadina 10 mg (Blíster x 7)", "1", "1.00"),
            // Precio por blíster: 1,00, no 7 × 0,14 = 0,98.
            Order.hasLine({
                withClass: ".selected",
                productName: "Loratadina 10 mg (Blíster x 7)",
                priceUnit: "1.00 / Blíster x 7",
            }),
            // Unidad suelta al precio del producto.
            ProductScreen.clickDisplayedProduct("Loratadina 10 mg"),
            choosePresentation("Unidad"),
            ProductScreen.totalAmountIs("1.20"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.00" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
        ].flat(),
});

registry.category("web_tour.tours").add("al_pharmacy_pos_presentation_pricelist", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Loratadina 10 mg"),
            choosePresentation("Blíster x 7"),
            ProductScreen.selectedOrderlineHas("Loratadina 10 mg (Blíster x 7)", "1", "1.00"),
            // El convenio del 10 % se aplica al precio del blíster, no al de la tableta.
            ProductScreen.clickPriceList("Convenio 10%"),
            ProductScreen.selectedOrderlineHas("Loratadina 10 mg (Blíster x 7)", "1", "0.90"),
            ProductScreen.clickDisplayedProduct("Loratadina 10 mg"),
            choosePresentation("0.90"),
            ProductScreen.totalAmountIs("1.80"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.00" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
        ].flat(),
});
