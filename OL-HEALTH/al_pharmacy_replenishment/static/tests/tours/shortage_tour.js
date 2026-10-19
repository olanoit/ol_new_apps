import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import { registry } from "@web/core/registry";

function saveShortage() {
    return {
        content: "registrar el faltante",
        trigger: ".modal .o_pharmacy_shortage_save:not([disabled])",
        run: "click",
    };
}

registry.category("web_tour.tours").add("al_pharmacy_replenishment_shortage", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // Faltante del producto de la línea: 3 unidades sin stock.
            ProductScreen.clickDisplayedProduct("Enalapril 10 mg"),
            ProductScreen.clickControlButton("Faltante"),
            {
                content: "el diálogo propone el producto de la línea",
                trigger: ".modal label:contains('Enalapril 10 mg')",
            },
            { trigger: ".modal #shortage_quantity", run: "edit 3" },
            saveShortage(),
            {
                content: "aviso de faltante registrado",
                trigger: ".o_notification:contains('Faltante registrado')",
            },
            // Faltante de algo que la botica no trabaja: texto libre.
            ProductScreen.clickControlButton("Faltante"),
            { trigger: ".modal #shortage_use_product", run: "click" },
            { trigger: ".modal #shortage_description", run: "edit Colirio lubricante 15 ml" },
            { trigger: ".modal #shortage_reason", run: "select not_carried" },
            saveShortage(),
            {
                content: "el diálogo se cerró",
                trigger: "body:not(:has(.modal .o_pharmacy_shortage_dialog))",
            },
        ].flat(),
});
