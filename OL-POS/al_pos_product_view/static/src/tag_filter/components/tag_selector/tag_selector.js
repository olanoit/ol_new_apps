/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

/**
 * Fila horizontal de chips de etiquetas de producto sobre el catálogo del
 * TPV.
 *
 * Solo se ofrecen las etiquetas usadas por al menos un producto cargado
 * mostrable (el core carga TODOS los product.tag — dominio [] — así que
 * listarlos en crudo mostraría etiquetas que nunca coincidirían con nada).
 *
 * El cálculo de etiquetas usadas es O(productos × etiquetas-por-producto):
 * demasiado pesado para rehacerlo en cada render (el getter se reevalúa en
 * cada pulsación del buscador). Se cachea y solo se recalcula cuando cambia
 * el número de plantillas cargadas o cuando refreshPosTags() incrementa
 * `pos.posTagsVersion`.
 */
export class PosTagSelector extends Component {
    static template = "al_pos_product_view.PosTagSelector";
    static props = {};

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");
        this.state = useState({ refreshing: false });
        // Campo de instancia plano (los componentes no son deep-reactive):
        // solo caché.
        this._tagCache = { templateCount: -1, version: -1, tags: [] };
    }

    get availableTags() {
        const templates = this.pos.models["product.template"].getAll();
        const version = this.pos.posTagsVersion;
        if (
            this._tagCache.templateCount !== templates.length ||
            this._tagCache.version !== version
        ) {
            const usedTagIds = new Set();
            for (const template of templates) {
                if (!template.canBeDisplayed) {
                    continue;
                }
                for (const tag of template.product_tag_ids || []) {
                    usedTagIds.add(tag.id);
                }
            }
            const tags = this.pos.models["product.tag"]
                .filter((tag) => usedTagIds.has(tag.id))
                // `sequence` forma parte de la carga del TPV (lo añade este
                // módulo): se respeta el orden del backend, con el nombre
                // como desempate.
                .sort((a, b) => a.sequence - b.sequence || a.name.localeCompare(b.name));
            this._tagCache = { templateCount: templates.length, version, tags };
        }
        // La visibilidad del chip (`show_in_pos_filter`) se aplica FUERA de
        // la caché: es O(etiquetas) — barato — y depende de la selección
        // actual, que cambia entre renders sin invalidar la caché. Reglas:
        //   - `!== false` en vez de truthiness: registros cacheados por un
        //     dispositivo antes de existir el campo lo cargan como
        //     `undefined` → visibles (default del campo).
        //   - Una etiqueta SELECCIONADA sigue visible aunque esté oculta
        //     (solo puede pasar vía el botón de recarga con el filtro
        //     activo): si no, su chip desaparecería con el filtro aplicado
        //     y sin forma de desmarcarla. Ocultar nunca afecta al filtrado.
        return this._tagCache.tags.filter(
            (tag) =>
                tag.show_in_pos_filter !== false || this.pos.isPosTagSelected(tag.id)
        );
    }

    /** Punto de color inline: `color` es un HEX Char (p.ej. "#3C3C3C"). */
    dotStyle(tag) {
        return `background-color: ${tag.color || "#3C3C3C"};`;
    }

    get refreshLabel() {
        return _t("Recargar las etiquetas desde el backend");
    }

    async onRefreshTags() {
        if (this.state.refreshing) {
            return;
        }
        this.state.refreshing = true;
        try {
            await this.pos.refreshPosTags();
            this.notification.add(_t("Etiquetas actualizadas"), { type: "success" });
        } catch (error) {
            // Causa típica: modo sin conexión (ConnectionLostError). Los
            // datos locales quedan intactos: avisar y seguir.
            console.warn("al_pos_product_view: refresh failed", error);
            this.notification.add(
                _t("No se pudieron actualizar las etiquetas. Revise su conexión."),
                { type: "danger" }
            );
        } finally {
            this.state.refreshing = false;
        }
    }
}
