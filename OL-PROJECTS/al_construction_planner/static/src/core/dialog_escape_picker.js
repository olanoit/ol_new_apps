/**
 * Paquete 1.18, M118-05, punto 6: Escape con el calendario abierto cierra solo
 * el calendario (lo hace su campo); el diálogo queda abierto con lo escrito.
 */
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";

patch(Dialog.prototype, {
    onEscape() {
        if (document.querySelector(".o_datetime_picker")) {
            return;
        }
        return super.onEscape(...arguments);
    },
});
