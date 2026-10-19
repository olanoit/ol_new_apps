import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("al_pharmacy_insurance_pay", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("María Torres Quispe"),
            ProductScreen.addOrderline("Losartán 50 mg", "1"),
            ProductScreen.clickPayButton(),
            // El convenio cubre 80 % de 20 − copago 2 = 14; quedan 6.
            PaymentScreen.clickPaymentMethod("Salud Andina", true, { remaining: "6.00" }),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.00" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
        ].flat(),
});
