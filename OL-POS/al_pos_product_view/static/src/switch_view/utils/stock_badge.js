/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Getters del badge de stock que comparten la fila de la lista
 * (`ProductListRow`) y la tarjeta de la cuadrícula (`ProductCard`). Ambos
 * componentes exponen `this.pos` y `this.props.product` (un
 * product.template). Se aplica con `patch()`, así otro módulo puede
 * redefinir `showStock` o `rawStockQty` en cada componente.
 */
export const StockBadgeMixin = {
    // Solo los productos almacenables tienen un stock con significado; los
    // servicios y consumibles siempre darían 0, que se leería como «sin
    // stock» sin serlo.
    get showStock() {
        return !!this.props.product?.is_storable;
    },

    // Stock en vivo de la caja (`pos.alpvLocationStock`, ver
    // overrides/pos_store/pos_store.js). Hasta que llega la primera
    // respuesta se usa el `qty_available` cargado al abrir la sesión, para
    // que el badge nunca salga vacío.
    get rawStockQty() {
        const id = this.props.product?.id;
        const live = this.pos.alpvLocationStock || {};
        return id in live ? live[id] : this.props.product?.qty_available ?? 0;
    },

    get stockQty() {
        return this.env.utils.formatProductQty(this.rawStockQty, false);
    },

    get stockUom() {
        return this.props.product?.uom_id?.name || "";
    },

    get stockLabel() {
        return this.stockUom ? `${this.stockQty} ${this.stockUom}` : this.stockQty;
    },

    get outOfStock() {
        return this.showStock && this.rawStockQty <= 0;
    },

    // Tooltip con la ubicación a la que se refiere la cifra.
    get stockTitle() {
        return this.pos.alpvLocationStockName
            ? _t("Stock en %s", this.pos.alpvLocationStockName)
            : "";
    },
};
