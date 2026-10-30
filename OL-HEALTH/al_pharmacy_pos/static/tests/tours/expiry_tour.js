import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
// Odoo 20: la pantalla de recibo es FeedbackScreen.
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("al_pharmacy_pos_expiry_discount", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // El único lote vence en 20 días: escala de 30 días, -40 %.
            ProductScreen.clickDisplayedProduct("Ibuprofeno 400 mg tableta"),
            ProductScreen.selectedOrderlineHas("Ibuprofeno 400 mg tableta", "1", "6.00"),
            {
                content: "nota de lote por vencer",
                trigger: ".orderline .customer-note:contains('Por vencer: vence')",
            },
            ProductScreen.totalAmountIs("6.00"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.00" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
        ].flat(),
});
