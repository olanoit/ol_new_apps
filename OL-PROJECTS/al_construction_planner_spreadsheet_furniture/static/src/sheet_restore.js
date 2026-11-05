/**
 * Paquete 1.17, M117-03 punto 6: «Restaurar versión». Lista las versiones
 * guardadas de la hoja, muestra por pestaña lo que cambiaría y, al confirmar,
 * reescribe por clave las columnas de dato. La hoja sigue vinculada a su obra y
 * guarda antes su estado actual, así que la restauración también se deshace.
 */
import { Component, useState, xml } from "@odoo/owl";
import { registries } from "@odoo/o-spreadsheet";
import { fetchSpreadsheetModel } from "@spreadsheet/helpers/model";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { keyColumns, lastDataRow, normText } from "@al_construction_planner_spreadsheet/send_to_planner";
import { applyImport, setCancelHandler } from "./sheet_import";

const { topbarMenuRegistry } = registries;

const WORK_MATERIALS_SHEET = "MATERIALES OBRA";
const isFurniture = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "furniture";

/**
 * Filas de dato de una pestaña: la clave de cada columna (la de _CLAVES o su
 * encabezado) y el contenido escrito, sin las columnas calculadas ni las filas
 * vacías. Con el contenido, no el valor: una suma escrita sigue siendo suma.
 */
function readDataRows(model, name, keys) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName(name);
    if (!sheetId) {
        return null;
    }
    const byColumn = {};
    for (const [key, col] of Object.entries(keys[name] || {})) {
        byColumn[col] = key;
    }
    const zone = getters.getSheetZone(sheetId);
    const columns = [];
    const headers = {};
    for (let col = zone.left; col <= zone.right; col++) {
        const header = getters.getEvaluatedCell({ sheetId, col, row: 0 }).value;
        if (!header || getters.getCell({ sheetId, col, row: 1 })?.isFormula) {
            continue;
        }
        const key = byColumn[col] || normText(header);
        columns.push({ col, key });
        headers[key] = [String(header)];
    }
    const rows = [];
    const bottom = lastDataRow(getters, sheetId);
    for (let row = 1; row <= bottom; row++) {
        const values = columns.map(
            ({ col }) => getters.getCell({ sheetId, col, row })?.content ?? ""
        );
        if (values.some((value) => value !== "")) {
            rows.push(values);
        }
    }
    return { keys: columns.map(({ key }) => key), headers, rows };
}

/** Las pestañas de datos, leídas de ``model``. */
export function readSheets(env, model) {
    const names = (env.constructionSendSheets() || []).filter(
        (name) => !name.startsWith("_") && name !== "RESUMEN VENTA"
    );
    const keys = keyColumns(model);
    const sheets = {};
    const planning = env.constructionSheetKind() === "furniture";
    for (const name of [...new Set(planning ? [...names, WORK_MATERIALS_SHEET] : names)]) {
        const spec = readDataRows(model, name, keys);
        if (spec) {
            sheets[name] = spec;
        }
    }
    return sheets;
}

/** Nuevo, Cambia e Igual por pestaña entre la hoja de hoy y la versión. */
export function comparePreview(current, version) {
    const preview = [];
    for (const [name, spec] of Object.entries(version)) {
        const today = current[name] || { keys: [], rows: [] };
        // Solo las claves que tienen las dos: una columna calculada de la hoja
        // no se compara con el dato que trae el otro lado.
        const shared = spec.keys.filter((key) => today.keys.includes(key));
        const pick = (keys, row) =>
            JSON.stringify(shared.map((key) => String(row[keys.indexOf(key)] ?? "")));
        const aligned = today.rows.map((row) => pick(today.keys, row));
        let same = 0;
        let changed = 0;
        spec.rows.forEach((row, index) => {
            if (index < aligned.length) {
                aligned[index] === pick(spec.keys, row) ? same++ : changed++;
            }
        });
        const added = Math.max(spec.rows.length - aligned.length, 0);
        // Una fila de hoy que la versión no tiene también cambia: se vacía.
        changed += Math.max(aligned.length - spec.rows.length, 0);
        preview.push({ name, added, changed, same, spec });
    }
    return preview;
}

/**
 * Vista previa de «Traer de Odoo» (M117-07): cuántas filas trae cada pestaña y
 * cuántas de la hoja reemplaza, antes de escribir.
 */
export class SheetPreviewDialog extends Component {
    static components = { Dialog };
    static props = ["close", "title", "intro", "rows", "confirm"];
    static template = xml`
        <Dialog title="props.title" size="'lg'">
            <p t-esc="props.intro"/>
            <table class="table table-sm o_main_table o_construction_sheet_preview">
                <thead>
                    <tr><th>Pestaña</th><th class="text-end">Nuevo</th>
                        <th class="text-end">Cambia</th><th class="text-end">Igual</th></tr>
                </thead>
                <tbody>
                    <tr t-foreach="props.rows" t-as="row" t-key="row.name">
                        <td t-esc="row.name"/>
                        <td class="text-end" t-esc="row.added"/>
                        <td class="text-end" t-esc="row.changed"/>
                        <td class="text-end" t-esc="row.same"/>
                    </tr>
                </tbody>
            </table>
            <t t-set-slot="footer">
                <button class="btn btn-primary o_construction_preview_confirm"
                        t-on-click="confirm">Confirmar</button>
                <button class="btn btn-secondary" t-on-click="props.close">Cancelar</button>
            </t>
        </Dialog>
    `;

    async confirm() {
        this.props.close();
        await this.props.confirm();
    }
}

class RestoreVersionDialog extends Component {
    static components = { Dialog };
    static props = ["close", "versions", "preview", "restore"];
    static template = xml`
        <Dialog title="title" size="'lg'">
            <p t-if="!props.versions.length">Esta hoja todavía no tiene versiones guardadas.</p>
            <t t-elif="!state.selected">
                <p>Elija la versión a la que quiere volver.</p>
                <table class="table table-sm o_main_table">
                    <thead><tr><th>Versión</th><th>Fecha</th><th>Antes de</th><th/></tr></thead>
                    <tbody>
                        <tr t-foreach="props.versions" t-as="version" t-key="version.id">
                            <td t-esc="version.version"/>
                            <td t-esc="version.date"/>
                            <td t-esc="version.reason or '—'"/>
                            <td class="text-end">
                                <button class="btn btn-sm btn-secondary o_construction_restore_pick"
                                        t-on-click="() => this.pick(version)">Elegir</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </t>
            <t t-else="">
                <p>
                    Versión <t t-esc="state.selected.version"/> del
                    <t t-esc="state.selected.date"/>. La hoja sigue vinculada a su obra y guarda
                    antes su estado actual.
                </p>
                <p t-if="!state.rows">Leyendo la versión…</p>
                <table t-else="" class="table table-sm o_main_table o_construction_restore_preview">
                    <thead>
                        <tr><th>Pestaña</th><th class="text-end">Nuevo</th>
                            <th class="text-end">Cambia</th><th class="text-end">Igual</th></tr>
                    </thead>
                    <tbody>
                        <tr t-foreach="state.rows" t-as="row" t-key="row.name">
                            <td t-esc="row.name"/>
                            <td class="text-end" t-esc="row.added"/>
                            <td class="text-end" t-esc="row.changed"/>
                            <td class="text-end" t-esc="row.same"/>
                        </tr>
                    </tbody>
                </table>
            </t>
            <t t-set-slot="footer">
                <button t-if="state.rows" class="btn btn-primary o_construction_restore_confirm"
                        t-att-disabled="state.busy" t-on-click="confirm">Restaurar</button>
                <button t-if="state.selected" class="btn btn-secondary"
                        t-on-click="back">Volver</button>
                <button class="btn btn-secondary" t-on-click="props.close">Cancelar</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.title = _t("Restaurar versión");
        this.state = useState({ selected: null, rows: null, busy: false });
    }

    async pick(version) {
        this.state.selected = version;
        this.state.rows = await this.props.preview(version);
    }

    back() {
        this.state.selected = null;
        this.state.rows = null;
    }

    async confirm() {
        this.state.busy = true;
        this.props.close();
        await this.props.restore(this.state.selected, this.state.rows);
    }
}

/** Vuelve a ``version``: reescribe por clave lo que difiere. */
async function writeVersion(env, version, rows) {
    const sheets = {};
    for (const { name, added, changed, spec } of rows) {
        if (added || changed) {
            sheets[name] = { ...spec, extra_headers: [], extra_rows: [] };
        }
    }
    await applyImport(
        env,
        {
            filename: _t("la versión %(version)s", { version: version.version }),
            mode: "replace",
            expand_rows: true,
            keep_extra: false,
            sheets,
            other: {},
        },
        { logImport: false }
    );
}

// M117-08: «Cancelar» vuelve a la versión que guardó la acción antes de escribir.
setCancelHandler(async (env) => {
    const [version] = await env.constructionCall("construction_versions");
    if (!version) {
        return;
    }
    const old = await fetchSpreadsheetModel(env, "documents.document", version.id);
    await writeVersion(env, version, comparePreview(readSheets(env, env.model), readSheets(env, old)));
    env.constructionNotify(_t("Acción cancelada: la hoja volvió a como estaba."));
});

export async function restoreVersion(env) {
    const model = env.model;
    const versions = await env.constructionCall("construction_versions");
    env.constructionDialog(RestoreVersionDialog, {
        versions,
        preview: async (version) => {
            const old = await fetchSpreadsheetModel(env, "documents.document", version.id);
            return comparePreview(readSheets(env, model), readSheets(env, old));
        },
        restore: async (version, rows) => {
            await env.constructionCall(
                "construction_version_before",
                _t("Antes de restaurar la versión %(version)s", { version: version.version })
            );
            await writeVersion(env, version, rows);
        },
    });
}

topbarMenuRegistry.addChild("construction_furniture_restore", ["construction_planner"], {
    name: _t("Restaurar versión…"),
    sequence: 112,
    isVisible: isFurniture,
    execute: (env) => restoreVersion(env),
});
