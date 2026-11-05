/**
 * «Traer la venta» y propuestas de tablero (paquete 1.17, M117-22). Los datos pasan
 * en un solo sentido: de la venta a la planificación. Lo escrito a mano no se pisa
 * sin que el analista lo marque: la huella oculta guarda lo que trajo la vez anterior.
 */
import { Component, onMounted, useState, xml } from "@odoo/owl";
import { registries } from "@odoo/o-spreadsheet";
import { SpreadsheetAction } from "@documents_spreadsheet/bundle/actions/spreadsheet_action";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import {
    afterValidateHooks,
    collectSheets,
    dispatchBatch,
    ensureSheet,
    keyColumns,
    normText,
    validate,
} from "@al_construction_planner_spreadsheet/send_to_planner";
import { TREE_SHEET, clearFloorGroups, groupTreeByFloor } from "./floor_groups";
import { columnsOf, ensureCapacity, ensureRows, writeWithProgress } from "./sheet_import";

const { topbarMenuRegistry } = registries;
const TRACE = "_HUELLA";
const isFurniture = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "furniture";

const norm = (value) => {
    const text = String(value ?? "").trim();
    const number = Number(text);
    return text !== "" && !Number.isNaN(number) ? String(Math.round(number * 1e6) / 1e6) : text;
};
const rowKey = (values, spec) => spec.match.map((key) => normText(values[key] ?? "")).join("|");

/** Lo que ya tiene cada pestaña: {clave de la fila: {row, values}}. */
function readTab(model, name, spec, keys) {
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

function readTrace(model) {
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

class BringDialog extends Component {
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

async function applyBring(env, tabs, data) {
    const model = env.model;
    const hasTree = tabs.some((tab) => tab.name === TREE_SHEET);
    if (hasTree) {
        clearFloorGroups(model);
    }
    const needed = Math.max(
        ...tabs.map((tab) => tab.last + tab.items.filter((item) => item.kind === "new").length)
    );
    await ensureCapacity(env, needed + 1);
    const commands = [];
    const traced = {};
    for (const tab of tabs) {
        const sheetId = tab.sheetId || ensureSheet(model, tab.name);
        let next = tab.last + 1;
        ensureRows(model, sheetId, next + tab.items.length + 1);
        for (const item of tab.items) {
            if (item.record) {
                traced[`${tab.name}|${item.id}`] = item.record;
            }
            if (!item.marked) {
                continue;
            }
            if (item.kind === "extra") {
                for (const col of Object.values(tab.columns)) {
                    commands.push(["UPDATE_CELL", { sheetId, col, row: item.row, content: "" }]);
                }
                continue;
            }
            const row = item.kind === "new" ? next++ : item.row;
            for (const [key, col] of Object.entries(tab.columns)) {
                commands.push([
                    "UPDATE_CELL",
                    { sheetId, col, row, content: String(item.record[key] ?? "") },
                ]);
            }
        }
    }
    // M117-08: con el avance a la vista.
    if (!(await writeWithProgress(env, _t("Traer la venta"), commands))) {
        return;
    }
    if (hasTree) {
        groupTreeByFloor(model);
    }
    writeTrace(model, traced);
    await env.constructionCall("construction_sale_bring_done", data.version);
    await validate(env, { quiet: true });
    env.constructionNotify(_t("Venta traída a la hoja (versión anterior guardada)."));
}

function writeTrace(model, traced) {
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

export async function bringSale(env) {
    const data = await env.constructionCall("construction_sale_bring");
    const tabs = compareBring(env.model, data);
    env.constructionDialog(BringDialog, {
        tabs,
        warnings: data.warnings,
        apply: async (selected) => {
            await env.constructionCall("construction_version_before", _t("Antes de traer la venta"));
            await applyBring(env, selected, data);
        },
    });
}

// ---------------------------------------------------------------------------
// Propuestas de tablero (M117-22, punto 8)
// ---------------------------------------------------------------------------
const GROUPS = { "Mueble bajo": "Mueble bajo", "Mueble alto": "Mueble alto", "Mueble completo": "Mueble completo" };

/** Grupos de piezas sin producto con su tablero propuesto, desde lo vendido. */
export function boardProposals(model) {
    const names = ["PIEZAS", "MODULOS", "VENDIDO", "ACABADOS DE OBRA", "PARAMETROS"];
    const sheets = collectSheets(model, names);
    const keys = keyColumns(model);
    const frontKinds = new Set();
    for (const row of (sheets.PARAMETROS || []).slice(1)) {
        if (row[6] === "piezas_frente") {
            String(row[8] ?? "").split(";").forEach((kind) => frontKinds.add(kind.trim().toUpperCase()));
        }
    }
    const moduleKeys = keys.MODULOS || {};
    const moduleGroup = {};
    for (const row of (sheets.MODULOS || []).slice(1)) {
        moduleGroup[`${row[moduleKeys.typology]}|${row[moduleKeys.code]}`] = row[moduleKeys.ml_group];
    }
    const sold = {};
    for (const row of (sheets.VENDIDO || []).slice(1)) {
        if (row[0]) {
            sold[`${row[0]}|${row[2]}`] = { structure: row[4], fronts: row[5] };
            // Una tipología gruesa toma los acabados de su fila Global.
            if (row[2] === "Global") {
                sold[`${row[0]}|*`] = { structure: row[4], fronts: row[5] };
            }
        }
    }
    const boards = {};
    for (const row of (sheets["ACABADOS DE OBRA"] || []).slice(1)) {
        if (row[0]) {
            boards[row[0]] = row[6];
        }
    }
    const pieceKeys = keys.PIEZAS || {};
    const groups = {};
    const missing = new Set();
    (sheets.PIEZAS || []).slice(1).forEach((row, index) => {
        const typology = row[pieceKeys.typology];
        if (!typology || row[pieceKeys.product_name]) {
            return;
        }
        const group = moduleGroup[`${typology}|${row[pieceKeys.module]}`];
        const zone = frontKinds.has(String(row[pieceKeys.piece_type] ?? "").toUpperCase())
            ? "fronts"
            : "structure";
        const line = sold[`${typology}|${GROUPS[group] || group}`] || sold[`${typology}|*`];
        const finish = line && line[zone];
        if (!finish) {
            return;
        }
        const board = boards[finish];
        if (!board) {
            missing.add(finish);
            return;
        }
        const id = `${typology}|${group}|${zone}|${board}`;
        const entry = (groups[id] = groups[id] || {
            id, typology, group, zone, finish, board, rows: [], marked: true,
        });
        entry.rows.push(index + 1);
    });
    return { groups: Object.values(groups), missing: [...missing], col: pieceKeys.product_name };
}

class BoardDialog extends Component {
    static components = { Dialog };
    static props = ["close", "groups", "missing", "apply"];
    static template = xml`
        <Dialog title="title" size="'lg'">
            <div t-foreach="props.missing" t-as="finish" t-key="finish" class="alert alert-warning py-1">
                <t t-esc="finish"/> sin tablero: elíjalo en ACABADOS DE OBRA
            </div>
            <table class="table table-sm o_main_table o_construction_board_preview">
                <thead><tr><th/><th>Tipología</th><th>Grupo</th><th>Zona</th><th>Tablero</th>
                    <th class="text-end">Piezas</th></tr></thead>
                <tbody>
                    <tr t-foreach="state.groups" t-as="group" t-key="group.id">
                        <td><input type="checkbox" t-att-checked="group.marked"
                                   t-on-change="(ev) => group.marked = ev.target.checked"/></td>
                        <td t-esc="group.typology"/>
                        <td t-esc="group.group"/>
                        <td t-esc="group.zone === 'fronts' ? zones.fronts : zones.structure"/>
                        <td t-esc="group.board"/>
                        <td class="text-end" t-esc="group.rows.length"/>
                    </tr>
                </tbody>
            </table>
            <t t-set-slot="footer">
                <button class="btn btn-secondary" t-on-click="() => this.mark(true)">Marcar todo</button>
                <button class="btn btn-primary o_construction_board_apply" t-on-click="apply">Aplicar seleccionadas</button>
                <button class="btn btn-secondary" t-on-click="props.close">Cerrar</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.title = _t("Propuestas de tablero");
        this.zones = { fronts: _t("Frentes"), structure: _t("Estructura") };
        this.state = useState({ groups: this.props.groups });
    }

    mark(value) {
        for (const group of this.state.groups) {
            group.marked = value;
        }
    }

    async apply() {
        this.props.close();
        await this.props.apply(this.state.groups.filter((group) => group.marked));
    }
}

function offerBoards(env) {
    const model = env.model;
    if (!model.getters.getSheetIdByName("VENDIDO")) {
        return;
    }
    const { groups, missing, col } = boardProposals(model);
    if (!groups.length && !missing.length) {
        return;
    }
    env.constructionDialog(BoardDialog, {
        groups,
        missing,
        apply: async (selected) => {
            if (!selected.length) {
                return;
            }
            await env.constructionCall("construction_version_before", _t("Antes de aplicar las propuestas de tablero"));
            const sheetId = model.getters.getSheetIdByName("PIEZAS");
            const commands = [];
            for (const group of selected) {
                for (const row of group.rows) {
                    commands.push(["UPDATE_CELL", { sheetId, col, row, content: group.board }]);
                }
            }
            await writeWithProgress(env, _t("Aplicar propuestas"), commands);
        },
    });
}

afterValidateHooks.push((env, result, options) => {
    if (isFurniture(env) && !options?.quiet) {
        offerBoards(env);
    }
});

topbarMenuRegistry.addChild("construction_furniture_bring_sale", ["construction_planner"], {
    name: _t("Traer la venta…"),
    sequence: 108,
    isVisible: (env) => isFurniture(env) && Boolean(env.constructionMetadata?.("construction_sale_available")),
    execute: (env) => bringSale(env),
});

// M117-22, punto 2: la hoja nace con la venta.
patch(SpreadsheetAction.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            if (this.model && this.data?.construction_sale_bring_pending) {
                this.data.construction_sale_bring_pending = false;
                bringSale({ ...this.env, model: this.model });
            }
        });
    },
});
