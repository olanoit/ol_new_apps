import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("al_pharmacy_care_refill", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("Julia Ramos"),
            {
                content: "aviso del tratamiento por reponer",
                trigger: '.modal .o_pharmacy_treatment_item:contains("Levotiroxina 100 mcg tableta")',
            },
            {
                content: "agregar al pedido",
                trigger: ".modal .o_pharmacy_treatment_add",
                run: "click",
            },
            ProductScreen.selectedOrderlineHas("Levotiroxina 100 mcg tableta", "1", "0.50"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.00" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
        ].flat(),
});
