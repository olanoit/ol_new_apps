import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PosLoyalty from "@pos_loyalty/../tests/tours/utils/pos_loyalty_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import { registry } from "@web/core/registry";

// Con la boleta por defecto y sin cliente, la caja pediría el cliente del
// comprobante: una venta solo de tarjeta de regalo sale con ticket.
registry.category("web_tour.tours").add("al_l10n_pe_pos_gift_card_ticket", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Gift Card"),
            PosLoyalty.orderTotalIs("50.00"),
            PosLoyalty.finalizeOrder("Cash", "50"),
        ].flat(),
});

// Venta mixta con boleta: la tarjeta se cobra en caja pero el ticket CPE la
// muestra fuera del comprobante.
registry.category("web_tour.tours").add("al_l10n_pe_pos_gift_card_mixed", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("Rosa Huamán Ccori"),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            ProductScreen.clickDisplayedProduct("Gift Card"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            {
                // El comprobante intenta enviarse a SUNAT y la prueba no tiene red.
                content: "Ticket emitido",
                trigger: ".pos .receipt-screen",
                timeout: 30000,
            },
            {
                content: "La tarjeta vendida va fuera del comprobante",
                trigger: ".alpe-receipt .alpe-words:contains('no forma parte del comprobante')",
            },
            {
                content: "La tarjeta no figura entre las líneas del comprobante",
                trigger: ".alpe-receipt .alpe-lines:not(:contains('Gift Card'))",
            },
        ].flat(),
});
