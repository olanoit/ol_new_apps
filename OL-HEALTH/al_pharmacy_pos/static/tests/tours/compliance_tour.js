import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("al_pharmacy_pos_compliance", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // Empresa vinculada: aviso al agregar y leyenda en la línea.
            ProductScreen.clickDisplayedProduct("Ibuprofeno Botica 400 mg"),
            {
                content: "aviso de empresa vinculada",
                trigger: ".o_notification:contains('empresa vinculada')",
            },
            ProductScreen.selectedOrderlineHas("Ibuprofeno Botica 400 mg · Empresa vinculada"),
            // Unidad suelta de un producto con blíster: rótulo en el recibo.
            ProductScreen.clickDisplayedProduct("Loratadina 10 mg"),
            {
                content: "vender por unidad",
                trigger: `.modal .selection-item:contains("Unidad")`,
                run: "click",
            },
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank", true, { remaining: "0.00" }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.receiptIsThere(),
            {
                content: "botón del rótulo de venta fraccionada",
                trigger: ".o_pharmacy_fraction_label:not([disabled])",
            },
        ].flat(),
});
