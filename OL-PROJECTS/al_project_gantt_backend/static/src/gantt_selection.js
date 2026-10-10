/** @odoo-module **/

/**
 * Selección múltiple en cascada para la rejilla del Gantt.
 *
 * La edición MIT de dhtmlxGantt no trae la extensión `multiselect` (es PRO),
 * así que la selección es una columna propia de casillas. Es genérica: no sabe
 * qué representa cada fila, solo su id y su árbol.
 *
 * Igual que el árbol de recursos del planificador, `selected` guarda solo las
 * filas marcadas «de más arriba»: marcar una fila marca implícitamente todas
 * las que cuelgan de ella.
 *
 * Uso (desde una subclase de `GanttAction`): `get selectionEnabled()` devuelve
 * `true` y se sobrescribe `onSelectionChange()`; la acción crea la columna y
 * engancha el clic.
 */
import { _t } from "@web/core/l10n/translation";

const CHECK_ATTR = "data-algantt-check";

export class GanttSelection {
    /**
     * @param {Object} [options]
     * @param {Function} [options.onChange] () => void, tras cada cambio
     * @param {Function} [options.isSelectable] (task) => bool; las demás filas
     *        no muestran casilla (p. ej. las de proyecto o de hito)
     */
    constructor(options = {}) {
        this.options = options;
        this.selected = new Set();
        this.gantt = null;
        this.eventIds = [];
    }

    /** Ancestros de una fila, del padre hacia la raíz. */
    _ancestors(id) {
        const result = [];
        const gantt = this.gantt;
        let parent = gantt.getParent(id);
        while (parent !== undefined && parent !== null && parent !== gantt.config.root_id) {
            result.push(String(parent));
            if (!gantt.isTaskExists(parent)) {
                break;
            }
            parent = gantt.getParent(parent);
        }
        return result;
    }

    _descendants(id) {
        const result = [];
        this.gantt.eachTask((task) => result.push(String(task.id)), id);
        return result;
    }

    /** Estado de la casilla: "on", "part" u "off". */
    state(id) {
        const key = String(id);
        if (!this.gantt || !this.selected.size) {
            return "off";
        }
        if (this.selected.has(key) || this._ancestors(key).some((a) => this.selected.has(a))) {
            return "on";
        }
        for (const other of this.selected) {
            if (this.gantt.isTaskExists(other) && this._ancestors(other).includes(key)) {
                return "part";
            }
        }
        return "off";
    }

    /**
     * Marca o desmarca una fila.
     * - Marcar: entra la fila y salen sus descendientes ya marcados.
     * - Desmarcar una fila cubierta por un ancestro marcado: el ancestro sale y
     *   entran los hermanos de cada nivel del camino hasta la fila.
     */
    toggle(id) {
        const key = String(id);
        const state = this.state(key);
        if (state === "on") {
            if (this.selected.has(key)) {
                this.selected.delete(key);
            } else {
                const path = [key, ...this._ancestors(key)];
                const top = path.findIndex((node) => this.selected.has(node));
                this.selected.delete(path[top]);
                for (let index = top - 1; index >= 0; index--) {
                    const keep = path[index];
                    for (const sibling of this.gantt.getChildren(path[index + 1])) {
                        if (String(sibling) !== keep) {
                            this.selected.add(String(sibling));
                        }
                    }
                }
            }
        } else {
            for (const child of this._descendants(key)) {
                this.selected.delete(child);
            }
            this.selected.add(key);
        }
        this.refresh();
    }

    clear() {
        this.selected.clear();
        this.refresh();
    }

    /** Filas marcadas «de más arriba» (las que no cubre un ancestro). */
    get topIds() {
        return [...this.selected];
    }

    /** Todas las filas marcadas, con sus descendientes ya cargados. */
    get allIds() {
        const result = new Set();
        for (const key of this.selected) {
            if (this.gantt?.isTaskExists(key)) {
                result.add(key);
                for (const child of this._descendants(key)) {
                    result.add(child);
                }
            }
        }
        return [...result];
    }

    get size() {
        return this.selected.size;
    }

    /** Tras recargar los datos: se olvidan las filas que ya no existen. */
    prune() {
        if (!this.gantt) {
            return;
        }
        for (const key of [...this.selected]) {
            if (!this.gantt.isTaskExists(key)) {
                this.selected.delete(key);
            }
        }
    }

    refresh() {
        this.gantt?.render();
        this.options.onChange?.();
    }

    /** Columna de casillas (va la primera de la rejilla). */
    column() {
        return {
            name: "al_select",
            label: "",
            align: "center",
            width: 32,
            resize: false,
            template: (task) => {
                if (this.options.isSelectable && !this.options.isSelectable(task)) {
                    return "";
                }
                const state = this.state(task.id);
                const icon = { on: "fa-check-square", part: "fa-minus-square", off: "fa-square-o" }[state];
                return `<span class="algantt-check algantt-check-${state} fa ${icon}" ${CHECK_ATTR}="1" title="${_t("Marcar")}"></span>`;
            },
        };
    }

    /** Engancha el clic en la casilla y la clase de las filas marcadas. */
    attach(gantt) {
        this.gantt = gantt;
        this.eventIds.push(
            gantt.attachEvent("onTaskClick", (id, event) => {
                if (event?.target?.closest?.(`[${CHECK_ATTR}]`)) {
                    this.toggle(id);
                    return false;
                }
                return true;
            })
        );
        const original = gantt.templates.grid_row_class;
        gantt.templates.grid_row_class = (start, end, task) => {
            const base = original ? original(start, end, task) || "" : "";
            return this.state(task.id) === "on" ? `${base} algantt-row-selected` : base;
        };
    }

    detach() {
        if (this.gantt) {
            for (const eventId of this.eventIds) {
                this.gantt.detachEvent(eventId);
            }
        }
        this.eventIds = [];
        this.gantt = null;
    }
}
