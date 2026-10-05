/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

const AVATAR_COLORS = [
    "#4A90E2", "#7B68EE", "#50C878", "#FF7043",
    "#FFA726", "#26A69A", "#AB47BC", "#EC407A",
    "#5C6BC0", "#00ACC1", "#66BB6A", "#FFA000",
];

export class SelectionPopupCustom extends Component {
    static template = "al_pos_vendedor.SelectionPopupCustom";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        list: { type: Array },
        cancelText: { type: String, optional: true },
        defaultId: { type: [Number, { value: null }], optional: true },
        onSetDefault: { type: Function, optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        title: _t("Seleccionar"),
        cancelText: _t("Cancelar"),
        defaultId: null,
    };

    setup() {
        this.state = useState({
            inputValue: "",
            filteredList: this.props.list,
            defaultId: this.props.defaultId,
        });
        this.inputRef = useRef("input");
        onMounted(() => this.inputRef.el?.focus());
    }

    get allowDefault() {
        return Boolean(this.props.onSetDefault);
    }

    // Alterna el vendedor predeterminado de la sesión sin cerrar el popup,
    // para diferenciar "marcar como predeterminado" de "seleccionar para la venta".
    toggleDefault(listItem, ev) {
        ev.stopPropagation();
        const newId = this.state.defaultId === listItem.id ? null : listItem.id;
        this.state.defaultId = newId;
        this.props.onSetDefault?.(newId ? listItem.item : null);
    }

    get currentSelection() {
        return this.props.list.find((i) => i.isSelected) || null;
    }

    searchLabel() {
        const term = this.state.inputValue.toLowerCase().trim();
        this.state.filteredList = term
            ? this.props.list.filter((i) => i.label.toLowerCase().includes(term))
            : this.props.list;
    }

    selectItem(listItem) {
        // Clic sobre el vendedor ya seleccionado → quitar selección
        if (listItem.isSelected) {
            this.clearSelection();
            return;
        }
        this.props.getPayload(listItem.item);
        this.props.close();
    }

    // null señaliza "quitar vendedor" (distinto de undefined = cancelar)
    clearSelection() {
        this.props.getPayload(null);
        this.props.close();
    }

    cancel() {
        this.props.close();
    }

    getInitials(name) {
        return (name || "?")
            .split(" ")
            .filter(Boolean)
            .slice(0, 2)
            .map((w) => w[0].toUpperCase())
            .join("");
    }

    getAvatarColor(name) {
        let hash = 0;
        for (const ch of name || "") {
            hash = (hash * 31 + ch.charCodeAt(0)) & 0xffffffff;
        }
        return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
    }
}
