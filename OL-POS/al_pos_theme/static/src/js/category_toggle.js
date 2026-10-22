import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * «Mostrar u ocultar categorías»: con la opción activa en la caja, el
 * cajero oculta o muestra la barra de categorías con un botón de la barra
 * superior. La elección se recuerda en el dispositivo, por caja.
 */
patch(PosStore.prototype, {
    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);
        let hidden = false;
        if (this.config.al_theme_category_toggle) {
            try {
                hidden = localStorage.getItem(this._alptCategoriesKey()) === "1";
            } catch {
                // Almacenamiento bloqueado: se muestran.
            }
        }
        this.alptCategoriesHidden = hidden;
    },

    _alptCategoriesKey() {
        return `al_pos_theme.categories_hidden.${this.config.id}`;
    },

    toggleAlptCategories() {
        this.alptCategoriesHidden = !this.alptCategoriesHidden;
        if (this.alptCategoriesHidden && this.selectedCategory) {
            // Oculta la barra con una categoría elegida: se ve todo el catálogo.
            this.selectedCategory = null;
        }
        try {
            localStorage.setItem(this._alptCategoriesKey(), this.alptCategoriesHidden ? "1" : "0");
        } catch {
            // Sin almacenamiento: vale para esta sesión.
        }
    },
});
