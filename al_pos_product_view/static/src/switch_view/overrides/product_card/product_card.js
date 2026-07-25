/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";

/**
 * Patch de ProductCard para mostrar un pequeño botón de "información" en
 * cada tarjeta de la cuadrícula (igual al ya presente en las filas de la
 * lista). El botón abre el ProductInfoPopup nativo vía
 * `pos.onProductInfoClick(...)`.
 *
 * El botón se suprime cuando la tarjeta se renderiza dentro del popup del
 * configurador de combos (`props.isComboPopup`), porque abrir otro modal
 * encima del configurador de combos sería confuso.
 */
patch(ProductCard.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
    },

    get infoLabel() {
        return _t("Más información sobre %s", this.props.name);
    },

    onInfoClick(ev) {
        ev.stopPropagation();
        ev.preventDefault();
        // ProductCard recibe la plantilla de producto vía `props.product`.
        this.pos.onProductInfoClick(this.props.product);
    },
});
