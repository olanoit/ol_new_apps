/** @odoo-module **/

import { Component, useExternalListener } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

export function getStockFilterOptions() {
    return new Map([
        ["all", { text: _t("Todos los productos") }],
        ["in_stock", { text: _t("Con stock") }],
        ["out_of_stock", { text: _t("Sin stock") }],
    ]);
}

/**
 * Filtros del catálogo, en la barra del conmutador de vista: el desplegable
 * «Filtros» (disponibilidad de stock y «Limpiar filtros») y, a su lado, una
 * faceta por cada filtro aplicado —stock y etiquetas—, como las del buscador
 * del backend: quitar una faceta quita todos sus valores.
 *
 * Va en la barra del catálogo y no en el buscador de la barra superior para
 * no tocar el `Input` del core, que otros módulos (y el tema) reubican.
 *
 * El filtrado está en overrides/pos_store/pos_store.js (`alpvSetStockFilter`)
 * y, para las etiquetas, en tag_filter/overrides/pos_store_patch.js.
 */
export class AlpvCatalogFilter extends Component {
    static template = "al_pos_product_view.CatalogFilter";
    static props = {};

    setup() {
        this.pos = usePos();
        this.ui = useService("ui");
        useExternalListener(window, "click", () => {
            this.pos.alpvFiltersOpen = false;
        });
    }

    get options() {
        return getStockFilterOptions();
    }

    get optionKeys() {
        return [...this.options.keys()];
    }

    toggleMenu() {
        this.pos.alpvFiltersOpen = !this.pos.alpvFiltersOpen;
    }

    selectStock(key) {
        this.pos.alpvSetStockFilter(key);
    }

    get selectedTags() {
        if (!this.pos.isFilteringByPosTags) {
            return [];
        }
        const tags = this.pos.models["product.tag"];
        return this.pos.selectedPosTagIds.map((id) => tags.get(id)).filter(Boolean);
    }

    // En pantallas pequeñas no hay sitio para las facetas: el botón lleva
    // el número de filtros aplicados.
    get activeFilterCount() {
        return this.selectedTags.length + (this.pos.alpvStockFilter === "all" ? 0 : 1);
    }

    /** Filtros aplicados, una faceta por tipo. */
    get facets() {
        const facets = [];
        const stockFilter = this.pos.alpvStockFilter;
        if (stockFilter !== "all") {
            const text = this.options.get(stockFilter).text;
            facets.push({
                id: "stock",
                icon: "fa-cubes",
                text,
                title: text,
                remove: () => this.pos.alpvSetStockFilter("all"),
            });
        }
        const tagNames = this.selectedTags.map((tag) => tag.name);
        if (tagNames.length) {
            const others = tagNames.length - 1;
            facets.push({
                id: "tags",
                icon: "fa-tags",
                text: others ? `${tagNames[0]} +${others}` : tagNames[0],
                title: tagNames.join(", "),
                remove: () => this.pos.clearPosTagFilter(),
            });
        }
        return facets;
    }

    get removeLabel() {
        return _t("Quitar filtro");
    }
}
