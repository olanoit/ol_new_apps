/** @odoo-module **/

import { useEffect } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { debounce } from "@web/core/utils/timing";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { ProductListRow } from "@al_pos_product_view/switch_view/components/product_list_row/product_list_row";
import { AlpvCatalogFilter } from "@al_pos_product_view/switch_view/components/catalog_filter/catalog_filter";
import {
    getProductPriceDetail,
    getTaxAwareProductPrice,
} from "@al_pos_product_view/switch_view/utils/product_price";

// Registra los componentes nuevos en ProductScreen para poder
// referenciarlos desde la plantilla QWeb heredada.
ProductScreen.components = {
    ...ProductScreen.components,
    ProductListRow,
    AlpvCatalogFilter,
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
        // Giro y bloqueo del botón «Actualizar stock» (ver refreshStockNow).
        this.state.refreshingStock = false;

        // Con debounce: escribir rápido en el buscador no lanza una petición
        // por tecla, solo la pausa final.
        const debouncedRefresh = debounce(
            (ids) => this.pos.alpvRefreshLocationStock(ids),
            400
        );

        // Badges de stock al día (filas y tarjetas): se piden para lo que se
        // ve cada vez que cambia la vista, la búsqueda, la categoría o la
        // página, lo mismo que cambia `productToDisplayByCateg`.
        useEffect(
            () => {
                debouncedRefresh(this._alpvVisibleProductIds());
            },
            () => [
                this.state.viewMode,
                this.pos.searchProductWord,
                this.pos.selectedCategory?.id,
                this.state.currentOffset,
            ]
        );
    },

    _alpvVisibleProductIds() {
        return this.pos.productToDisplayByCateg.flatMap(([, products]) =>
            products.map((product) => product.id)
        );
    },

    /**
     * Tras añadir un producto se refresca su stock: una venta en otra caja
     * puede cambiarlo en cualquier momento.
     */
    async addProductToOrder(product) {
        const result = await super.addProductToOrder(...arguments);
        if (product?.is_storable) {
            this.pos.alpvRefreshLocationStock([product.id]);
        }
        return result;
    },

    /**
     * Vacía el buscador en cuanto el producto entra al pedido, para buscar
     * el siguiente sin borrar (ajuste «Limpiar la búsqueda al añadir»). Va
     * aquí y no en `addProductToOrder` porque el core solo llama a este
     * método cuando de verdad se creó la línea, con clic o con lector:
     * cancelar el configurador de producto conserva la búsqueda.
     */
    showOptionalProductPopupIfNeeded(product) {
        if (this.pos.config.iface_clear_search_on_add) {
            this.pos.searchProductWord = "";
        }
        return super.showOptionalProductPopupIfNeeded(...arguments);
    },

    /**
     * Control segmentado «Cuadrícula | Lista»: cada botón fija su vista; la
     * persistencia de la preferencia sigue en `toggleProductView`.
     */
    async setProductView(mode) {
        if (this.state.viewMode !== mode) {
            await this.toggleProductView();
        }
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
     * Construye la cadena de precio formateada de la vista de lista. Delega
     * en `getTaxAwareProductPrice`, que resuelve la tarifa del pedido Y
     * aplica impuestos según `pos.config.iface_tax_included` — así la cifra
     * coincide exactamente con lo que muestra la línea de pedido al añadir
     * el producto, en vez del importe de tarifa sin impuestos.
     */
    getProductListPrice(product) {
        return getTaxAwareProductPrice(this.pos, product);
    },

    /**
     * Desglose bajo el precio en la lista: descuento o recargo de la tarifa
     * sobre el precio de venta.
     */
    getProductListPriceDetail(product) {
        return getProductPriceDetail(this.pos, product);
    },

    /**
     * Botón «Actualizar stock» de la barra del catálogo: pide ya el stock de
     * lo visible, sin esperar al debounce, y rehace el filtro de stock si
     * está activo. `state.refreshingStock` evita un segundo clic mientras la
     * petición sigue en curso.
     */
    async refreshStockNow() {
        if (this.state.refreshingStock) {
            return;
        }
        this.state.refreshingStock = true;
        try {
            await this.pos.alpvRefreshLocationStock(this._alpvVisibleProductIds());
            if (this.pos.alpvStockFilter !== "all") {
                await this.pos.alpvSetStockFilter(this.pos.alpvStockFilter);
            }
        } finally {
            this.state.refreshingStock = false;
        }
    },

    get refreshStockLabel() {
        return _t("Actualizar stock");
    },
});
