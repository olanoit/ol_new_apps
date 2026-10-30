import { registry } from "@web/core/registry";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";

// El TPV arranca con la ESC/POS de la caja como impresora de recibo: en 20
// la instancia se creaba con la API de 19 y el TPV no llegaba a cargar.
registry.category("web_tour.tours").add("al_pos_network_printer_boot_tour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm(),
            {
                content: "La pantalla de productos cargó",
                trigger: ".product-screen",
            },
        ].flat(),
});
