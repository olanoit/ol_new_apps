/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { ProductListRow } from "@al_pos_product_view/switch_view/components/product_list_row/product_list_row";
import { getTaxAwareProductPrice } from "@al_pos_product_view/switch_view/utils/product_price";

// Registra el nuevo componente en ProductScreen para poder referenciarlo
// desde la plantilla QWeb heredada.
ProductScreen.components = {
    ...ProductScreen.components,
    ProductListRow,
};

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);

        // Cascada de prioridad: gana la preferencia guardada del cajero si
        // existe; si no, el valor por defecto configurado en el TPV (elección
        // del admin); si no, "grid". `pos_product_view_mode` queda vacío
        // (falsy) hasta que el cajero cambia de vista al menos una vez, así
        // que los usuarios nuevos siguen aterrizando en el default del TPV.
        this.state.viewMode =
            this.pos.user?.pos_product_view_mode ||
            this.pos.config?.default_product_view ||
            "grid";
    },

    /**
     * Alterna el modo de vista entre `grid` y `list`. Primero se registra
     * localmente (UI ágil) y luego se persiste en el registro del usuario en
     * segundo plano. Un fallo de persistencia NO revierte la UI: el peor
     * caso es que la elección no sobreviva a una recarga de página.
     */
    async toggleProductView() {
        this.state.viewMode = this.state.viewMode === "list" ? "grid" : "list";
        const user = this.pos.user;
        if (!user) {
            return;
        }
        // Actualización local optimista para que otros patches que leen el
        // registro del usuario observen el nuevo valor de inmediato.
        user.pos_product_view_mode = this.state.viewMode;
        try {
            await this.pos.data.call(
                "res.users",
                "set_pos_product_view_mode",
                [[user.id], this.state.viewMode]
            );
        } catch (err) {
            // La persistencia es best-effort. Se registra para depurar y se sigue.
            console.warn("al_pos_product_view: no se pudo persistir el modo de vista", err);
        }
    },

    /**
     * Tooltip / aria-label localizado del botón conmutador de vista.
     * Se computa en JS (en lugar de inline en la plantilla) para que el
     * extractor de i18n detecte las cadenas vía `_t`.
     */
    get switchViewLabel() {
        return this.state.viewMode === "list"
            ? _t("Cambiar a vista de cuadrícula")
            : _t("Cambiar a vista de lista");
    },

    /**
     * Construye la cadena de precio formateada de la vista de lista. Delega
     * en `getTaxAwareProductPrice`, que resuelve la tarifa del pedido Y
     * aplica impuestos según `pos.config.iface_tax_included` — así la cifra
     * coincide exactamente con lo que muestra la línea de pedido al añadir
     * el producto, en vez del importe de tarifa sin impuestos.
     */
    getProductListPrice(product) {
        return getTaxAwareProductPrice(this.pos, product);
    },
});
