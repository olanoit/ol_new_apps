/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * Filtrado del catálogo del TPV por etiquetas de producto (product.tag).
 *
 * El filtrado se engancha en DOS puntos porque el core calcula el catálogo
 * por dos rutas distintas:
 *
 *   1. `getExcludedProductIds()` — se consume DENTRO del bucle de
 *      `productsToDisplay`, ANTES del tope de 100 productos visibles.
 *      Excluir ahí las plantillas que no coinciden garantiza que el tope se
 *      llena solo con productos que sí coinciden. OJO:
 *      `getExcludedProductIds()` también lo llama
 *      `ControlButtons.displayProductInfoBtn()` para decidir si se muestra
 *      el botón "Información de producto" de la línea seleccionada — las
 *      exclusiones del filtro NO deben filtrarse a esa ruta. De ahí el flag
 *      a nivel de módulo `applyTagExclusions`, activo solo mientras corre el
 *      getter (síncrono) `productsToDisplay`.
 *
 *   2. `productToDisplayByCateg` — con "Agrupar por categoría" activo el
 *      core reconstruye las listas desde su índice de categorías sin
 *      consultar los ids excluidos, así que cada grupo se post-filtra aquí.
 *
 * `selectedPosTagIds` es un array plano que se REEMPLAZA en cada toggle
 * (nunca se muta) para que la reactividad de owl re-renderice a todos los
 * suscriptores.
 */

// Guardia síncrona: true solo mientras se computa `productsToDisplay`.
let applyTagExclusions = false;

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.selectedPosTagIds = [];
        // Lo incrementa refreshPosTags(); los consumidores (PosTagSelector)
        // cachean sus derivados con esta versión para que un refresh que no
        // cambia el número de productos cargados recalcule igualmente la
        // lista de etiquetas.
        this.posTagsVersion = 0;
    },

    /**
     * Recarga en caliente las etiquetas desde el backend sin salir de la
     * sesión: upsert de nuevas/renombradas/recoloreadas, borrado de
     * fantasmas, re-lectura de las plantillas cargadas por el MISMO
     * pipeline que "Buscar más" (los unlink de etiquetas se reflejan) y
     * poda de la selección activa.
     */
    async refreshPosTags() {
        const serverTags = await this.data.searchRead("product.tag", []);
        const serverTagIds = new Set(serverTags.map((tag) => tag.id));
        const ghosts = this.models["product.tag"].filter(
            (tag) => !serverTagIds.has(tag.id)
        );
        for (const ghost of ghosts) {
            ghost.delete();
        }

        const templateIds = this.models["product.template"].getAll().map((t) => t.id);
        if (templateIds.length) {
            await this.loadNewProducts([["id", "in", templateIds]]);
        }

        this.selectedPosTagIds = this.selectedPosTagIds.filter((id) =>
            serverTagIds.has(id)
        );
        this.posTagsVersion++;
    },

    isPosTagSelected(tagId) {
        return this.selectedPosTagIds.includes(tagId);
    },

    togglePosTag(tagId) {
        this.selectedPosTagIds = this.isPosTagSelected(tagId)
            ? this.selectedPosTagIds.filter((id) => id !== tagId)
            : [...this.selectedPosTagIds, tagId];
    },

    clearPosTagFilter() {
        this.selectedPosTagIds = [];
    },

    get isFilteringByPosTags() {
        return Boolean(
            this.config.iface_filter_products_by_tag && this.selectedPosTagIds.length
        );
    },

    /**
     * Semántica OR: la plantilla coincide si lleva ALGUNA etiqueta
     * seleccionada. `product_tag_ids` es el m2m a nivel de plantilla que el
     * core del TPV ya carga de serie.
     */
    productTemplateMatchesSelectedTags(template) {
        return Boolean(
            template.product_tag_ids?.some((tag) => this.isPosTagSelected(tag.id))
        );
    },

    get productsToDisplay() {
        if (!this.isFilteringByPosTags) {
            return super.productsToDisplay;
        }
        applyTagExclusions = true;
        try {
            return super.productsToDisplay;
        } finally {
            applyTagExclusions = false;
        }
    },

    getExcludedProductIds() {
        const excludedIds = super.getExcludedProductIds();
        if (!applyTagExclusions || !this.isFilteringByPosTags) {
            return excludedIds;
        }
        for (const template of this.models["product.template"].getAll()) {
            if (!this.productTemplateMatchesSelectedTags(template)) {
                excludedIds.push(template.id);
            }
        }
        return excludedIds;
    },

    get productToDisplayByCateg() {
        const result = super.productToDisplayByCateg;
        if (!this.isFilteringByPosTags || !this.config.iface_group_by_categ) {
            return result;
        }
        return result
            .map(([catId, products]) => [
                catId,
                products.filter((p) => this.productTemplateMatchesSelectedTags(p)),
            ])
            .filter(([, products]) => products.length);
    },
});
