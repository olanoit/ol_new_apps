/**
 * Vista previa de «Traer la venta» con huella (paquete 1.17, M117-22), común
 * a las hojas del planificador: mobiliario la usa desde el 1.17 y la hoja de
 * planificación de obra por partidas desde el paquete 5 de CREVAL (CR-45). Lo
 * escrito a mano no se pisa sin que se marque: la pestaña oculta _HUELLA
 * guarda lo que se trajo la vez anterior.
 */
import { Component, useState, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import {
    collectSheets,
    dispatchBatch,
    ensureSheet,
    keyColumns,
    normText,
} from "@al_construction_planner_spreadsheet/send_to_planner";

export const TRACE = "_HUELLA";

export function ensureRows(model, sheetId, rows) {
    const current = model.getters.getNumberRows(sheetId);
    if (current < rows) {
        model.dispatch("ADD_COLUMNS_ROWS", {
            sheetId,
            sheetName: model.getters.getSheetName(sheetId),
            dimension: "ROW",
            base: current - 1,
            quantity: rows - current,
            position: "after",
        });
    }
}

/**
 * {clave: columna} de las columnas de dato de una pestaña: la de _CLAVES o la
 * de su encabezado (``spec.headers``); las de fórmula no se escriben.
 */
export function columnsOf(model, sheetId, name, spec, keys) {
    const header = (collectSheets(model, [name])[name] || [[]])[0] || [];
    const byHeader = {};
    header.forEach((text, col) => {
        const key = normText(text);
        if (key && byHeader[key] === undefined) {
            byHeader[key] = col;
        }
    });
    const columns = {};
    spec.keys.forEach((key) => {
        let col = keys[name]?.[key];
        if (col === undefined) {
            for (const text of [key, ...(spec.headers?.[key] || [])]) {
                if (byHeader[normText(text)] !== undefined) {
                    col = byHeader[normText(text)];
                    break;
                }
            }
        }
        const cell = col !== undefined && model.getters.getCell({ sheetId, col, row: 1 });
        if (col !== undefined && !(cell && cell.isFormula)) {
            columns[key] = col;
        }
    });
    return { columns, header };
}

const norm = (value) => {
    const text = String(value ?? "").trim();
    const number = Number(text);
    return text !== "" && !Number.isNaN(number) ? String(Math.round(number * 1e6) / 1e6) : text;
};
const rowKey = (values, spec) => spec.match.map((key) => normText(values[key] ?? "")).join("|");

/** Lo que ya tiene cada pestaña: {clave de la fila: {row, values}}. */
export function readTab(model, name, spec, keys) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName(name);
    const rows = {};
    let last = 0;
    if (!sheetId) {
        return { rows, last, columns: {}, sheetId };
    }
    const { columns } = columnsOf(model, sheetId, name, spec, keys);
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const values = {};
        let filled = false;
        for (const key of spec.keys) {
            if (columns[key] === undefined) {
                continue;
            }
            const content = getters.getCell({ sheetId, col: columns[key], row })?.content ?? "";
            values[key] = content;
            filled = filled || content !== "";
        }
        if (filled) {
            last = row;
            const id = rowKey(values, spec);
            if (id.replaceAll("|", "") && !rows[id]) {
                rows[id] = { row, values };
            }
        }
    }
    return { rows, last, columns, sheetId };
}

export function readTrace(model) {
    const sheetId = model.getters.getSheetIdByName(TRACE);
    const trace = {};
    if (!sheetId) {
        return trace;
    }
    for (let row = 0; row < model.getters.getNumberRows(sheetId); row++) {
        const id = model.getters.getCell({ sheetId, col: 0, row })?.content;
        if (id) {
            trace[id] = JSON.parse(model.getters.getCell({ sheetId, col: 1, row })?.content || "{}");
        }
    }
    return trace;
}

/**
 * Nuevo, Cambia, Igual y Sobra de cada pestaña. Se marcan solas las filas que nadie
 * tocó desde la última vez; lo editado a mano y lo que sobra quedan desmarcados.
 */
export function compareBring(model, data) {
    const keys = keyColumns(model);
    const trace = readTrace(model);
    const tabs = [];
    for (const [name, spec] of Object.entries(data.tabs)) {
        const current = readTab(model, name, spec, keys);
        const items = [];
        const seen = new Set();
        for (const values of spec.rows) {
            const record = Object.fromEntries(spec.keys.map((key, index) => [key, values[index] ?? ""]));
            const id = rowKey(record, spec);
            seen.add(id);
            const existing = current.rows[id];
            if (!existing) {
                items.push({ id, label: id, kind: "new", marked: true, record });
                continue;
            }
            const differs = spec.keys.filter((key) => norm(existing.values[key]) !== norm(record[key]));
            if (!differs.length) {
                items.push({ id, label: id, kind: "same", marked: false, record, row: existing.row });
                continue;
            }
            const before = trace[`${name}|${id}`];
            // Vacío en la hoja no es una edición: la fila aún no tenía ese dato.
            const edited = differs.some(
                (key) => norm(existing.values[key]) !== "" &&
                    (!before || norm(before[key]) !== norm(existing.values[key]))
            );
            items.push({
                id, label: `${id}: ${differs.join(", ")}`, kind: "change", marked: !edited, record,
                row: existing.row,
            });
        }
        if (!spec.keep_extra) {
            for (const [id, existing] of Object.entries(current.rows)) {
                if (!seen.has(id)) {
                    items.push({ id, label: id, kind: "extra", marked: false, row: existing.row });
                }
            }
        }
        tabs.push({ name, spec, items, last: current.last, columns: current.columns, sheetId: current.sheetId });
    }
    return tabs;
}

export class BringDialog extends Component {
    static components = { Dialog };
    static props = ["close", "tabs", "warnings", "apply"];
    static template = xml`
        <Dialog title="title" size="'xl'">
            <div t-foreach="props.warnings" t-as="warning" t-key="warning_index"
                 class="alert alert-warning py-1" t-esc="warning"/>
            <table class="table table-sm o_main_table o_construction_bring_preview">
                <thead><tr><th>Pestaña</th><th class="text-end">Nuevo</th><th class="text-end">Cambia</th>
                    <th class="text-end">Igual</th><th class="text-end">Sobra</th><th/></tr></thead>
                <tbody>
                    <t t-foreach="state.tabs" t-as="tab" t-key="tab.name">
                        <tr>
                            <td t-esc="tab.name"/>
                            <td class="text-end" t-esc="count(tab, 'new')"/>
                            <td class="text-end" t-esc="count(tab, 'change')"/>
                            <td class="text-end" t-esc="count(tab, 'same')"/>
                            <td class="text-end" t-esc="count(tab, 'extra')"/>
                            <td class="text-end">
                                <button t-if="selectable(tab).length" class="btn btn-link btn-sm p-0"
                                        t-on-click="() => tab.open = !tab.open">Ver filas</button>
                            </td>
                        </tr>
                        <t t-if="tab.open">
                            <tr t-foreach="selectable(tab)" t-as="item" t-key="item.id" class="table-light">
                                <td colspan="5">
                                    <label><input type="checkbox" t-att-checked="item.marked"
                                                  t-on-change="(ev) => item.marked = ev.target.checked"/>
                                        <t t-esc="labels[item.kind]"/> · <t t-esc="item.label"/></label>
                                </td>
                                <td/>
                            </tr>
                        </t>
                    </t>
                </tbody>
            </table>
            <t t-set-slot="footer">
                <button class="btn btn-primary o_construction_bring_confirm" t-on-click="confirm">Confirmar</button>
                <button class="btn btn-secondary" t-on-click="props.close">Cancelar</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.title = _t("Traer la venta");
        this.labels = { new: _t("Nuevo"), change: _t("Cambia"), extra: _t("Sobra") };
        this.state = useState({ tabs: this.props.tabs });
    }

    count(tab, kind) {
        return tab.items.filter((item) => item.kind === kind).length;
    }

    selectable(tab) {
        return tab.items.filter((item) => item.kind === "change" || item.kind === "extra");
    }

    async confirm() {
        this.props.close();
        await this.props.apply(this.state.tabs);
    }
}

export function writeTrace(model, traced) {
    const sheetId = ensureSheet(model, TRACE);
    const current = readTrace(model);
    const merged = { ...current, ...traced };
    ensureRows(model, sheetId, Object.keys(merged).length + 5);
    const commands = [];
    Object.entries(merged).forEach(([id, values], row) => {
        commands.push(
            ["UPDATE_CELL", { sheetId, col: 0, row, content: `'${id}`.slice(1) }],
            ["UPDATE_CELL", { sheetId, col: 1, row, content: JSON.stringify(values) }]
        );
    });
    dispatchBatch(model, commands);
}
