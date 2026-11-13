/** @odoo-module **/

import { toRaw } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

// El core muestra como mucho estos productos en el catálogo
// (`filterExcludedProducts`).
const CATALOG_DISPLAY_LIMIT = 100;

// Solo los almacenables tienen stock (misma regla que el badge): servicios y
// consumibles no entran en ninguna de las dos opciones del filtro.
function* filterByStock(products, stockFilter, inStockIds) {
    for (const product of products) {
        if (product.is_storable && inStockIds.has(product.id) === (stockFilter === "in_stock")) {
            yield product;
        }
    }
}

/**
 * Stock en vivo y filtro de stock del catálogo.
 *
 * `qty_available` se carga una vez por sesión y el core no lo vuelve a pedir.
 * `alpvLocationStock` ({id de plantilla: cantidad}) se refresca desde el
 * servidor con lo que se ve en cada momento (ver product_screen.js) y al
 * cerrar un pedido se descuenta localmente lo vendido, sin esperar al
 * siguiente refresco. Es solo visual: el stock real lo mueven los
 * movimientos del pedido al sincronizarse.
 */
patch(PosStore.prototype, {
    // `async` + `await super.setup()`: el setup del core es asíncrono y el
    // servicio del TPV lo espera antes de pintar.
    async setup() {
        await super.setup(...arguments);
        this.alpvLocationStock = {};
        this.alpvLocationStockName = "";
        // Solo se aplica la respuesta de la ÚLTIMA petición: una lenta de
        // una búsqueda ya abandonada no pisa datos más recientes.
        this._alpvLocationStockRequestId = 0;
        // Filtro de stock: "all", "in_stock" u "out_of_stock", y los ids con
        // stock en que se apoya (null hasta que hace falta). El Set se
        // reemplaza en cada cambio, nunca se muta, para que el catálogo se
        // repinte sin rastrear cada consulta sobre miles de productos.
        this.alpvStockFilter = "all";
        this.alpvInStockTemplateIds = null;
        // Desplegable «Filtros» del catálogo (también lo abren las facetas).
        this.alpvFiltersOpen = false;
    },

    /** Algún filtro del catálogo (stock o etiquetas) acota los productos. */
    get alpvHasCatalogFilter() {
        return this.alpvStockFilter !== "all" || Boolean(this.isFilteringByPosTags);
    },

    /**
     * Se aplica antes del tope de 100 productos del core, así el tope se
     * llena solo con productos que cumplen. `productsToDisplay` y la ruta
     * «Agrupar por categoría» de `productToDisplayByCateg` pasan por aquí.
     */
    filterExcludedProducts(products) {
        const inStockIds = toRaw(this.alpvInStockTemplateIds);
        if (this.alpvStockFilter !== "all" && inStockIds) {
            products = filterByStock(products, this.alpvStockFilter, inStockIds);
        }
        return super.filterExcludedProducts(products);
    },

    /**
     * El TPV solo tiene parte del catálogo en el navegador
     * (`limited_product_count`): trae los productos que un filtro necesita
     * y no están cargados, hasta lo que el catálogo puede mostrar. Si falla,
     * el filtro sigue funcionando sobre lo cargado.
     */
    async alpvLoadMissingTemplates(templateIds) {
        const templates = this.models["product.template"];
        const missingIds = templateIds
            .filter((id) => !templates.get(id))
            .slice(0, CATALOG_DISPLAY_LIMIT);
        if (!missingIds.length) {
            return;
        }
        try {
            await this.loadNewProducts([["id", "in", missingIds]]);
        } catch (error) {
            console.warn("al_pos_product_view: no se pudieron cargar los productos", error);
        }
    },

    /**
     * Elige la opción del filtro de stock pidiendo el stock al día. Sin
     * ningún dato en que apoyarse (primer uso sin conexión) vuelve a «Todos»
     * en vez de mostrar una lista arbitraria.
     */
    async alpvSetStockFilter(stockFilter) {
        this.alpvStockFilter = stockFilter;
        if (stockFilter === "all") {
            return;
        }
        const ids = await this.data.silentCall(
            "product.template",
            "get_pos_in_stock_template_ids",
            [this.config.id]
        );
        if (ids) {
            this.alpvInStockTemplateIds = new Set(ids);
            if (stockFilter === "in_stock") {
                await this.alpvLoadMissingTemplates(ids);
            }
        } else if (!this.alpvInStockTemplateIds) {
            this.alpvStockFilter = "all";
            this.notification.add(_t("No se pudo cargar el stock de los productos."), {
                type: "warning",
            });
        }
    },

    /** «Limpiar filtros»: stock y etiquetas. */
    alpvClearCatalogFilters() {
        this.alpvSetStockFilter("all");
        this.clearPosTagFilter?.();
    },

    // Mantiene el filtro de stock al paso de las cifras en vivo.
    _alpvUpdateInStockTemplateIds(stockByTemplateId) {
        if (!this.alpvInStockTemplateIds) {
            return;
        }
        const ids = new Set(toRaw(this.alpvInStockTemplateIds));
        for (const [id, qty] of Object.entries(stockByTemplateId)) {
            if (qty > 0) {
                ids.add(Number(id));
            } else {
                ids.delete(Number(id));
            }
        }
        this.alpvInStockTemplateIds = ids;
    },

    orderDone(order) {
        this._alpvDecrementLocalStock(order);
        return super.orderDone(...arguments);
    },

    _alpvDecrementLocalStock(order) {
        for (const line of order?.lines || []) {
            const template = line.product_id?.product_tmpl_id;
            if (!template?.is_storable) {
                continue;
            }
            template.qty_available -= line.getQuantity();
            if (template.id in this.alpvLocationStock) {
                this.alpvLocationStock[template.id] -= line.getQuantity();
                this._alpvUpdateInStockTemplateIds({
                    [template.id]: this.alpvLocationStock[template.id],
                });
            }
        }
    },

    /**
     * Pide el stock en vivo de `productTmplIds` y lo funde en
     * `alpvLocationStock`. Best-effort: si la petición falla quedan los
     * valores anteriores (o el `qty_available` de la carga).
     */
    async alpvRefreshLocationStock(productTmplIds) {
        const ids = [...new Set(productTmplIds)].filter(Boolean);
        if (!ids.length) {
            return;
        }
        const requestId = ++this._alpvLocationStockRequestId;
        const result = await this.data.silentCall(
            "product.template",
            "get_pos_location_stock",
            [ids, this.config.id]
        );
        if (!result || requestId !== this._alpvLocationStockRequestId) {
            return;
        }
        this.alpvLocationStockName = result.location_name || "";
        Object.assign(this.alpvLocationStock, result.stock);
        this._alpvUpdateInStockTemplateIds(result.stock);
    },
});
