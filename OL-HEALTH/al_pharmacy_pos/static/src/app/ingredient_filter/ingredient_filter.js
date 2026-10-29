import { Component, proxy, t, useProps } from "@odoo/owl";
import { normalize } from "@web/core/l10n/utils";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

/**
 * Catálogo de la caja por principio activo:
 *
 * - Filtro: reemplaza al de etiquetas (el servidor apaga
 *   `iface_filter_products_by_tag` si `pharmacy_ingredient_filter` está
 *   activo). Semántica OR: el producto se muestra si lleva ALGUNO de los
 *   principios elegidos. Como el filtro de etiquetas de al_pos_product_view,
 *   se engancha en `getExcludedProductIds()` (antes del tope de productos
 *   visibles) solo mientras se calcula `productsToDisplay`, y en
 *   `productToDisplayByCateg` cuando se agrupa por categoría.
 * - Búsqueda: el texto buscado también encuentra el principio activo y sus
 *   sinónimos, en lo cargado y en la búsqueda en el servidor.
 */
let applyIngredientExclusions = false;

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.selectedPharmacyIngredientIds = [];
    },

    isPharmacyIngredientSelected(ingredientId) {
        return this.selectedPharmacyIngredientIds.includes(ingredientId);
    },

    togglePharmacyIngredient(ingredientId) {
        this.selectedPharmacyIngredientIds = this.isPharmacyIngredientSelected(ingredientId)
            ? this.selectedPharmacyIngredientIds.filter((id) => id !== ingredientId)
            : [...this.selectedPharmacyIngredientIds, ingredientId];
    },

    clearPharmacyIngredients() {
        this.selectedPharmacyIngredientIds = [];
    },

    get isFilteringByPharmacyIngredient() {
        return Boolean(
            this.config.pharmacy_ingredient_filter && this.selectedPharmacyIngredientIds.length
        );
    },

    productTemplateHasSelectedIngredient(template) {
        return Boolean(
            template.pharmacy_ingredient_ids?.some((ingredient) =>
                this.isPharmacyIngredientSelected(ingredient.id)
            )
        );
    },

    get productsToDisplay() {
        if (!this.isFilteringByPharmacyIngredient) {
            return super.productsToDisplay;
        }
        applyIngredientExclusions = true;
        try {
            return super.productsToDisplay;
        } finally {
            applyIngredientExclusions = false;
        }
    },

    getExcludedProductIds() {
        const excludedIds = super.getExcludedProductIds();
        if (!applyIngredientExclusions || !this.isFilteringByPharmacyIngredient) {
            return excludedIds;
        }
        for (const template of this.models["product.template"].getAll()) {
            if (!this.productTemplateHasSelectedIngredient(template)) {
                excludedIds.push(template.id);
            }
        }
        return excludedIds;
    },

    get productToDisplayByCateg() {
        const result = super.productToDisplayByCateg;
        if (!this.isFilteringByPharmacyIngredient || !this.config.iface_group_by_categ) {
            return result;
        }
        return result
            .map(([categId, products]) => [
                categId,
                products.filter((product) => this.productTemplateHasSelectedIngredient(product)),
            ])
            .filter(([, products]) => products.length);
    },
});

patch(ProductTemplate.prototype, {
    get searchString() {
        const base = super.searchString;
        const ingredients = (this.pharmacy_ingredient_ids || [])
            .map((ingredient) => [ingredient.name, ingredient.synonyms].filter(Boolean).join(" "))
            .join(" ");
        const extra = [this.pharmacy_composition, ingredients].filter(Boolean).join(" ");
        return extra ? `${base} ${normalize(extra)}` : base;
    },
});

/** Buscador de principios activos con desplegable y chips de los elegidos. */
export class PharmacyIngredientSelector extends Component {
    static template = "al_pharmacy_pos.PharmacyIngredientSelector";
    props = useProps({});

    setup() {
        this.pos = usePos();
        this.state = proxy({ query: "", open: false });
        // Caché de conteos: se recalcula solo si cambia el catálogo cargado.
        this._cache = { templateCount: -1, counts: new Map(), ingredients: [] };
    }

    _refreshCache() {
        const templates = this.pos.models["product.template"].getAll();
        if (this._cache.templateCount === templates.length) {
            return;
        }
        const counts = new Map();
        for (const template of templates) {
            if (!template.canBeDisplayed) {
                continue;
            }
            for (const ingredient of template.pharmacy_ingredient_ids || []) {
                counts.set(ingredient.id, (counts.get(ingredient.id) || 0) + 1);
            }
        }
        const ingredients = this.pos.models["pharmacy.ingredient"]
            .filter((ingredient) => counts.has(ingredient.id))
            .sort((a, b) => a.name.localeCompare(b.name));
        this._cache = { templateCount: templates.length, counts, ingredients };
    }

    get selected() {
        return this.pos.selectedPharmacyIngredientIds
            .map((id) => this.pos.models["pharmacy.ingredient"].get(id))
            .filter(Boolean);
    }

    get options() {
        this._refreshCache();
        const query = normalize(this.state.query.trim());
        return this._cache.ingredients.filter(
            (ingredient) =>
                !this.pos.isPharmacyIngredientSelected(ingredient.id) &&
                (!query ||
                    normalize([ingredient.name, ingredient.synonyms, ingredient.atc_code].join(" ")).includes(
                        query
                    ))
        );
    }

    count(ingredient) {
        return this._cache.counts.get(ingredient.id) || 0;
    }

    pick(ingredient) {
        this.pos.togglePharmacyIngredient(ingredient.id);
        this.state.query = "";
    }

    onKeydown(event) {
        if (event.key === "Enter" && this.options.length) {
            this.pick(this.options[0]);
        } else if (event.key === "Escape") {
            this.state.open = false;
            event.target.blur();
        }
    }
}

ProductScreen.components = { ...ProductScreen.components, PharmacyIngredientSelector };

patch(ProductScreen.prototype, {
    loadProductFromDBDomain(searchProductWord) {
        // Búsqueda en el servidor también por principio activo (nombre,
        // sinónimos y código ATC: _rec_names_search de pharmacy.ingredient).
        return [
            "|",
            ["pharmacy_ingredient_line_ids.ingredient_id", "ilike", searchProductWord],
            ...super.loadProductFromDBDomain(searchProductWord),
        ];
    },
});
