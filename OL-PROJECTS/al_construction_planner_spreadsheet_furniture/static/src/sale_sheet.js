/**
 * Hoja de venta (paquete 1.17, M117-16 a M117-21): opciones del menú. La barra de
 * la hoja muestra todos los menús raíz, así que el menú es el mismo de la hoja de
 * planificación y cambia de nombre con el tipo de hoja.
 */
import { Component, useState, xml } from "@odoo/owl";
import { registries } from "@odoo/o-spreadsheet";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import {
    activateSheet,
    collectSheets,
    dispatchBatch,
    validate,
} from "@al_construction_planner_spreadsheet/send_to_planner";
import { upgradeSheet } from "./planning_panel";
import { importExcel, writeWithProgress } from "./sheet_import";
import { restoreVersion } from "./sheet_restore";

const { topbarMenuRegistry } = registries;

const RATE_LETTERS = "ABCDEFGHIJ";
const RATE_ID_COL = 11;
const RATE_STATUS_COL = 10;

export const isSale = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "sale";

const phaseOf = (env) => env.constructionMetadata?.("construction_sale_phase") || "in_progress";
const editable = (env) => ["in_progress", "additional"].includes(phaseOf(env));

function lockedReason(env) {
    return phaseOf(env) === "lost"
        ? _t("La cotización está perdida")
        : phaseOf(env) === "awarded"
          ? _t("La venta está confirmada: use Nueva versión")
          : _t("La cotización está enviada: use Nueva versión");
}

/** Una opción que no corresponde a la fase sale deshabilitada, con su motivo. */
function phaseItem(id, name, sequence, execute, options = {}) {
    topbarMenuRegistry.addChild(id, ["construction_planner"], {
        name: (env) => (editable(env) ? name : `${name} (${lockedReason(env)})`),
        sequence,
        isVisible: isSale,
        isEnabled: editable,
        execute,
        ...options,
    });
}

// ---------------------------------------------------------------------------
// «Traer tarifario» (M117-19, punto 6)
// ---------------------------------------------------------------------------
function readRates(model) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName("TARIFARIO");
    const rows = [];
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const cell = (col) => getters.getCell({ sheetId, col, row })?.content ?? "";
        if (cell(1) === "") {
            continue;
        }
        const values = {};
        [...RATE_LETTERS].forEach((letter, col) => {
            values[letter] = cell(col);
        });
        rows.push({ row, values, id: cell(RATE_ID_COL) });
    }
    return rows;
}

/** Filas Nuevo, Cambia e Igual; las Nuevo y las de precio del catálogo, marcadas. */
export function compareRates(current, catalog) {
    const byId = new Map(current.filter((line) => line.id).map((line) => [String(line.id), line]));
    const seen = new Set();
    const rows = catalog.map((rate) => {
        const line = byId.get(String(rate.L));
        seen.add(String(rate.L));
        if (!line) {
            return { rate, kind: "new", marked: true };
        }
        const differs = [...RATE_LETTERS].some(
            (letter) => String(line.values[letter] ?? "") !== String(rate[letter] ?? "")
        );
        return differs
            ? { rate, line, kind: "change", marked: false }
            : { rate, line, kind: "same", marked: false };
    });
    const gone = current.filter((line) => line.id && !seen.has(String(line.id)));
    return { rows, gone };
}

class RatesDialog extends Component {
    static components = { Dialog };
    static props = ["close", "rows", "gone", "apply"];
    static template = xml`
        <Dialog title="title" size="'xl'">
            <div class="d-flex gap-2 mb-2 align-items-center">
                <select class="form-select w-auto" t-model="state.partida">
                    <option value="">Todas las partidas</option>
                    <option t-foreach="partidas" t-as="partida" t-key="partida" t-att-value="partida"
                            t-esc="partida"/>
                </select>
                <button class="btn btn-secondary btn-sm o_rates_all" t-on-click="() => this.mark(true)">Marcar todo</button>
                <button class="btn btn-secondary btn-sm" t-on-click="() => this.mark(false)">Ninguno</button>
                <span class="ms-auto text-muted" t-esc="counts"/>
            </div>
            <p t-if="props.gone.length" class="text-muted">
                <t t-esc="props.gone.length"/> ítems ya no están en la lista: se conservan y quedan «Ya no está».
            </p>
            <table class="table table-sm o_main_table o_construction_rates_preview">
                <thead><tr><th/><th>Partida</th><th>Ítem</th><th class="text-end">En la hoja</th>
                    <th class="text-end">En el catálogo</th><th>Estado</th></tr></thead>
                <tbody>
                    <tr t-foreach="visible" t-as="row" t-key="row.rate.L">
                        <td><input t-if="row.kind !== 'same'" type="checkbox" t-att-checked="row.marked"
                                   t-on-change="(ev) => row.marked = ev.target.checked"/></td>
                        <td t-esc="row.rate.A"/>
                        <td t-esc="row.rate.B"/>
                        <td class="text-end" t-esc="row.line?.values.F ?? '—'"/>
                        <td class="text-end" t-esc="row.rate.F"/>
                        <td t-esc="labels[row.kind]"/>
                    </tr>
                </tbody>
            </table>
            <t t-set-slot="footer">
                <button class="btn btn-primary o_rates_apply" t-on-click="apply">Aplicar</button>
                <button class="btn btn-secondary" t-on-click="props.close">Cancelar</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.title = _t("Traer tarifario");
        this.labels = { new: _t("Nuevo"), change: _t("Cambia"), same: _t("Igual") };
        this.state = useState({ partida: "", rows: this.props.rows });
    }

    get partidas() {
        return [...new Set(this.props.rows.map((row) => row.rate.A))];
    }

    get visible() {
        return this.state.rows.filter(
            (row) => !this.state.partida || row.rate.A === this.state.partida
        );
    }

    get counts() {
        const count = (kind) => this.state.rows.filter((row) => row.kind === kind).length;
        return _t("%(new)s nuevos · %(change)s cambian · %(same)s iguales", {
            new: count("new"),
            change: count("change"),
            same: count("same"),
        });
    }

    mark(value) {
        for (const row of this.visible) {
            if (row.kind !== "same") {
                row.marked = value;
            }
        }
    }

    async apply() {
        const rows = this.state.rows.filter((row) => row.marked);
        this.props.close();
        await this.props.apply(rows);
    }
}

async function bringRates(env) {
    const model = env.model;
    const current = readRates(model);
    const catalog = await env.constructionCall("construction_sale_rates");
    const { rows, gone } = compareRates(current, catalog);
    env.constructionDialog(RatesDialog, {
        rows,
        gone,
        apply: async (marked) => {
            await env.constructionCall(
                "construction_version_before",
                _t("Antes de traer el tarifario")
            );
            const getters = model.getters;
            const sheetId = getters.getSheetIdByName("TARIFARIO");
            let next = current.reduce((last, line) => Math.max(last, line.row), 0) + 1;
            const commands = [];
            for (const { rate, line } of marked) {
                const row = line ? line.row : next++;
                [...RATE_LETTERS].forEach((letter, col) => {
                    commands.push([
                        "UPDATE_CELL",
                        { sheetId, col, row, content: String(rate[letter] ?? "") },
                    ]);
                });
                commands.push([
                    "UPDATE_CELL",
                    { sheetId, col: RATE_ID_COL, row, content: String(rate.L) },
                ]);
            }
            for (const line of gone) {
                commands.push([
                    "UPDATE_CELL",
                    { sheetId, col: RATE_STATUS_COL, row: line.row, content: _t("Ya no está") },
                ]);
            }
            if (await writeWithProgress(env, _t("Traer tarifario"), commands)) {
                env.constructionNotify(_t("Tarifario actualizado (versión anterior guardada)."));
            }
        },
    });
}

/** «Proponer alta en el tarifario»: los ítems escritos a mano (M117-19, punto 7). */
async function proposeRates(env) {
    const rows = readRates(env.model)
        .filter((line) => !line.id)
        .map((line) => [line.values.A, line.values.B, line.values.F]);
    if (!rows.length) {
        env.constructionNotify(_t("Todos los ítems están en el tarifario."));
        return;
    }
    await env.constructionCall("construction_sale_propose_rates", rows);
    env.constructionNotify(
        _t("Oficina Técnica recibió la propuesta de %(count)s ítems.", { count: rows.length })
    );
}

// ---------------------------------------------------------------------------
// «Copiar tipología» (M117-20, punto 8)
// ---------------------------------------------------------------------------
const MEASURE = { typology: 0, name: 1, partida: 2, item: 3, detail: 4, plan: 5, note: 6, used: 7 };

export function measureBlocks(model) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName("METRADO");
    const blocks = {};
    let last = 0;
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const content = (col) => getters.getCell({ sheetId, col, row })?.content ?? "";
        if (content(MEASURE.item) === "") {
            continue;
        }
        last = row;
        const code = getters.getEvaluatedCell({ sheetId, col: MEASURE.used, row }).value;
        (blocks[code] = blocks[code] || []).push(row);
    }
    return { blocks, last };
}

/** El siguiente código libre de la familia: C01 → C03 si C02 ya existe. */
export function nextCode(code, used) {
    const match = /^(.*?)(\d+)([^\d]*)$/.exec(code);
    if (!match) {
        return `${code}2`;
    }
    const [, prefix, digits, suffix] = match;
    let number = Number(digits);
    let candidate;
    do {
        number++;
        candidate = `${prefix}${String(number).padStart(digits.length, "0")}${suffix}`;
    } while (used.includes(candidate));
    return candidate;
}

class CopyTypologyDialog extends Component {
    static components = { Dialog };
    static props = ["close", "codes", "copy"];
    static template = xml`
        <Dialog title="title">
            <div class="mb-2">
                <label class="form-label">Copiar</label>
                <select class="form-select o_copy_source" t-model="state.source" t-on-change="suggest">
                    <option t-foreach="props.codes" t-as="code" t-key="code" t-att-value="code" t-esc="code"/>
                </select>
            </div>
            <div class="mb-2">
                <label class="form-label">Código nuevo</label>
                <input class="form-control o_copy_code" t-model="state.code"/>
                <div t-if="taken" class="text-danger small">Ese código ya existe.</div>
            </div>
            <div class="mb-2">
                <label class="form-label">Nombre</label>
                <input class="form-control o_copy_name" t-model="state.name"/>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" t-model="state.building" id="copy_building"/>
                <label class="form-check-label" for="copy_building">Copiar también sus filas de EDIFICIO</label>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-primary o_copy_confirm" t-att-disabled="taken or !state.code"
                        t-on-click="confirm">Copiar</button>
                <button class="btn btn-secondary" t-on-click="props.close">Cancelar</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.title = _t("Copiar tipología");
        this.state = useState({ source: this.props.codes[0], code: "", name: "", building: false });
        this.suggest();
    }

    suggest() {
        this.state.code = nextCode(this.state.source, this.props.codes);
    }

    get taken() {
        return this.props.codes.includes(this.state.code);
    }

    async confirm() {
        this.props.close();
        await this.props.copy({ ...this.state });
    }
}

async function copyTypology(env) {
    const model = env.model;
    const { blocks } = measureBlocks(model);
    const codes = Object.keys(blocks);
    if (!codes.length) {
        env.constructionNotify(_t("METRADO todavía no tiene tipologías."), "warning");
        return;
    }
    env.constructionDialog(CopyTypologyDialog, {
        codes,
        copy: async ({ source, code, name, building }) => {
            await env.constructionCall(
                "construction_version_before",
                _t("Antes de copiar la tipología %(code)s", { code: source })
            );
            const getters = model.getters;
            const sheetId = getters.getSheetIdByName("METRADO");
            const { last } = measureBlocks(model);
            const commands = [];
            blocks[source].forEach((origin, index) => {
                const row = last + 1 + index;
                for (const col of [MEASURE.item, MEASURE.detail, MEASURE.plan, MEASURE.note]) {
                    const content = getters.getCell({ sheetId, col, row: origin })?.content ?? "";
                    commands.push(["UPDATE_CELL", { sheetId, col, row, content }]);
                }
                if (index === 0) {
                    const partida = getters.getEvaluatedCell({
                        sheetId,
                        col: MEASURE.used + 1,
                        row: origin,
                    }).value;
                    commands.push(
                        ["UPDATE_CELL", { sheetId, col: MEASURE.typology, row, content: code }],
                        ["UPDATE_CELL", { sheetId, col: MEASURE.name, row, content: name }],
                        ["UPDATE_CELL", { sheetId, col: MEASURE.partida, row, content: String(partida) }]
                    );
                }
            });
            if (building) {
                copyBuildingRows(model, source, code, commands);
            }
            dispatchBatch(model, commands);
            activateSheet(model, sheetId);
            model.selection.selectCell(MEASURE.typology, last + 1);
        },
    });
}

/** Las filas copiadas de EDIFICIO quedan con ambiente y posición en blanco. */
function copyBuildingRows(model, source, code, commands) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName("EDIFICIO");
    const TYPOLOGY = 7;
    const rows = [];
    let last = 0;
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const value = getters.getCell({ sheetId, col: TYPOLOGY, row })?.content;
        if (value || getters.getCell({ sheetId, col: 6, row })?.content) {
            last = row;
        }
        if (value === source) {
            rows.push(row);
        }
    }
    rows.forEach((origin, index) => {
        const row = last + 1 + index;
        for (const col of [0, 1, 2, 4, 5]) {
            const content = getters.getCell({ sheetId, col, row: origin })?.content ?? "";
            commands.push(["UPDATE_CELL", { sheetId, col, row, content }]);
        }
        commands.push(["UPDATE_CELL", { sheetId, col: TYPOLOGY, row, content: code }]);
    });
}

// ---------------------------------------------------------------------------
// «Pasar el resumen a la cotización» (M117-21)
// ---------------------------------------------------------------------------
function parameterValues(model) {
    const rows = collectSheets(model, ["PARAMETROS"]).PARAMETROS || [];
    const values = {};
    for (const row of rows.slice(1)) {
        if (row[6]) {
            values[row[6]] = row[8];
        }
    }
    return values;
}

function departmentsText(rows) {
    return rows
        .map((row) =>
            row.first === row.last
                ? String(row.first)
                : `${row.first} al ${row.last} (posición ${String(row.position).padStart(2, "0")})`
        )
        .join(", ");
}

/** Lo que muestra la hoja: lo guarda la cotización para su PDF y para la planificación. */
export function collectSummary(model) {
    const sheets = collectSheets(model, [
        "OBRA", "EDIFICIO", "ACABADOS", "PRECIOS", "METRADO", "RESUMEN VENTA",
    ]);
    const parameters = parameterValues(model);
    const obra = {};
    for (const row of (sheets.OBRA || []).slice(1)) {
        if (row[0]) {
            obra[row[0]] = row[1] ?? "";
        }
    }
    const changes = (sheets.OBRA || [])
        .slice(1)
        .filter((row) => row[7] && row[4] === obra["Versión de la cotización"])
        .map((row) => row[7]);
    const finishes = {};
    for (const row of (sheets.ACABADOS || []).slice(1)) {
        if (row[0]) {
            finishes[row[0]] = {
                code: row[0], description: row[1] ?? "", kind: row[2] ?? "", thickness: row[3] ?? "",
                color: row[4] ?? "", material: row[5] ?? "",
            };
        }
    }
    const building = (sheets.EDIFICIO || []).slice(1).filter((row) => row[6]).map((row) => ({
        group: row[13] ?? "", from: row[14] ?? "", to: row[15] ?? "", position: row[16] ?? "",
        duplex: row[4] ?? "", unit_type: row[5] ?? "", space: row[6], typology: row[7] ?? "",
        count: row[9] ?? 0, first: row[10] ?? "", last: row[11] ?? "",
    }));
    const prices = {};
    const considerations = [];
    for (const row of (sheets.PRECIOS || []).slice(1)) {
        if (row[9]) {
            prices[row[9]] = { structure: row[10] ?? "", fronts: row[11] ?? "" };
        }
        if (row[7] && !considerations.includes(row[7])) {
            considerations.push(row[7]);
        }
    }
    const describe = (name, used) => {
        const parts = [
            [_t("estructura"), used.structure],
            [_t("frentes"), used.fronts],
        ]
            .filter(([, code]) => code)
            .map(([label, code]) => `${label} ${code} (${finishes[code]?.material || finishes[code]?.description || ""})`);
        return parts.length ? `${name}: ${parts.join(" + ")}` : name;
    };
    const typologies = [];
    const byCode = {};
    const sold = [];
    for (const row of (sheets.METRADO || []).slice(1)) {
        const code = row[7];
        if (!code) {
            continue;
        }
        if (!byCode[code]) {
            const summary = (sheets.METRADO || []).find((line) => line[16] === code) || [];
            const ownRows = building.filter((item) => item.typology === code);
            byCode[code] = {
                code, name: summary[17] ?? "", partida: row[8] ?? "", ml_low: summary[18] ?? 0,
                ml_high: summary[19] ?? 0, ml_full: summary[20] ?? 0, price: summary[21] ?? 0,
                spaces: summary[22] ?? 0, departments: departmentsText(ownRows), lines: [],
            };
            byCode[code].footer = `${code} · ${byCode[code].name} · DPTO: ${byCode[code].departments} · ${byCode[code].spaces} ×`;
            typologies.push(byCode[code]);
        }
        const used = prices[row[3]] || {};
        byCode[code].lines.push({
            name: row[3], description: describe(row[3], used), qty: row[10] ?? 0, uom: row[11] ?? "",
            price: row[12] ?? 0, subtotal: row[13] ?? 0, group: row[9] ?? "",
            structure: used.structure ?? "", fronts: used.fronts ?? "",
        });
    }
    for (const typology of typologies) {
        const groups = {};
        for (const line of typology.lines) {
            const key = line.group || "";
            const group = (groups[key] = groups[key] || {
                typology: typology.code, partida: typology.partida, group: key, ml: 0,
                structure: line.structure, fronts: line.fronts, price: typology.price,
                spaces: typology.spaces, departments: typology.departments,
            });
            if (line.uom === "ML") {
                group.ml += Number(line.qty) || 0;
            }
        }
        sold.push(...Object.values(groups));
    }
    const resumen = sheets["RESUMEN VENTA"] || [];
    // Paquete 1.18, M118-14: los totales arriba (filas 11-15) y las partidas
    // desde la fila 18; las hojas anteriores, totales en 32-36 y partidas en 12-31.
    const totalsOnTop = (resumen[10] || [])[0] === "Suma de partidas";
    const [firstPartida, lastPartida] = totalsOnTop ? [17, 37] : [11, 31];
    const [subtotalRow, taxRow, totalRow] = totalsOnTop ? [13, 14, 15] : [34, 35, 36];
    const partidas = [];
    for (let index = firstPartida; index < lastPartida; index++) {
        const row = resumen[index] || [];
        if (row[0]) {
            const name = row[0];
            const used = new Set();
            for (const typology of typologies.filter((item) => item.partida === name)) {
                for (const line of typology.lines) {
                    [line.structure, line.fronts].filter(Boolean).forEach((code) => used.add(code));
                }
            }
            partidas.push({
                name, spaces: row[1] ?? 0, subtotal: row[2] ?? 0,
                finishes: [...used].map((code) => finishes[code]).filter(Boolean),
            });
        }
    }
    const cell = (row) => (resumen[row - 1] || [])[2] ?? 0;
    const withoutTax = parameters.precio_sin_igv === "Sí";
    return {
        version: obra["Versión de la cotización"], obra, building, partidas, typologies, sold,
        considerations, changes, finishes: Object.values(finishes),
        igv: Number(parameters.igv) || 0, prices_without_tax: withoutTax,
        dpto_factor: Number(parameters.dpto_factor) || 100, pisos_nombre: parameters.pisos_nombre || "",
        departments_total: Number((sheets.EDIFICIO || [[]])[0]?.[19]) || 0,
        discount: Number(obra["Descuento comercial"]) || 0,
        subtotal: cell(subtotalRow), tax: cell(taxRow), total: cell(totalRow),
        order_subtotal: cell(subtotalRow),
    };
}

class PassDialog extends Component {
    static components = { Dialog };
    static props = ["close", "preview", "confirm"];
    static template = xml`
        <Dialog title="title" size="'lg'">
            <table class="table table-sm o_main_table o_construction_pass_preview">
                <thead><tr><th>Línea</th><th class="text-end">En la orden</th>
                    <th class="text-end">Con la hoja</th><th>Estado</th></tr></thead>
                <tbody>
                    <tr t-foreach="props.preview.lines" t-as="line" t-key="line.name">
                        <td t-esc="line.name"/>
                        <td class="text-end" t-esc="line.current"/>
                        <td class="text-end" t-esc="line.price"/>
                        <td t-esc="labels[line.kind]"/>
                    </tr>
                </tbody>
            </table>
            <p>Total de la orden: <strong t-esc="props.preview.order_total"/> · Total de la hoja:
               <strong t-esc="props.preview.sheet_total"/></p>
            <div t-foreach="props.preview.warnings" t-as="warning" t-key="warning_index"
                 class="alert alert-warning" t-esc="warning"/>
            <t t-set-slot="footer">
                <button class="btn btn-primary o_construction_pass_confirm" t-on-click="confirm">Confirmar</button>
                <button class="btn btn-secondary" t-on-click="props.close">Cancelar</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.title = _t("Pasar el resumen a la cotización");
        this.labels = { new: _t("Nueva"), change: _t("Cambia"), same: _t("Igual") };
    }

    async confirm() {
        this.props.close();
        await this.props.confirm();
    }
}

async function passSummary(env) {
    const result = await validate(env, { quiet: true });
    if (result.errors) {
        return;
    }
    const summary = collectSummary(env.model);
    const preview = await env.constructionCall("construction_sale_pass_preview", summary);
    env.constructionDialog(PassDialog, {
        preview,
        confirm: async () => {
            await env.constructionCall("construction_sale_pass", summary);
            env.constructionNotify(_t("La cotización tiene las líneas de la hoja."));
        },
    });
}

async function newVersion(env) {
    const action = await env.constructionCall("construction_sale_new_version");
    await env.constructionDoAction(action);
}

// ---------------------------------------------------------------------------
// Menú
// ---------------------------------------------------------------------------
topbarMenuRegistry.addChild("construction_sale_validate", ["construction_planner"], {
    name: _t("Validar"),
    sequence: 10,
    isVisible: isSale,
    execute: (env) => validate(env),
});
phaseItem("construction_sale_rates", _t("Traer tarifario…"), 20, (env) => bringRates(env));
phaseItem("construction_sale_copy", _t("Copiar tipología…"), 30, (env) => copyTypology(env));
phaseItem("construction_sale_propose", _t("Proponer alta en el tarifario"), 35, (env) =>
    proposeRates(env)
);
phaseItem("construction_sale_import", _t("Importar Excel a la hoja…"), 60, (env) => importExcel(env), {
    separator: true,
});
topbarMenuRegistry.addChild("construction_sale_template", ["construction_planner"], {
    name: _t("Descargar formato de carga"),
    sequence: 70,
    isVisible: isSale,
    execute: async (env) => {
        const action = await env.constructionCall("action_construction_download_sale_template");
        await env.constructionDoAction(action);
    },
});
phaseItem("construction_sale_restore", _t("Restaurar versión…"), 80, (env) => restoreVersion(env));
phaseItem("construction_sale_rows", _t("Ampliar filas…"), 85, (env) =>
    env.askConfirmation(
        _t("La hoja se rehace con 300 filas más y los datos que escribió. Antes se guarda una versión. ¿Continuar?"),
        () => upgradeSheet(env, "construction_sale_add_rows")
    )
);
phaseItem("construction_sale_upgrade", _t("Actualizar a la plantilla vigente…"), 90, (env) =>
    env.askConfirmation(
        _t("La hoja se rehace con la plantilla de hoy y los datos que escribió. Antes se guarda una versión. ¿Continuar?"),
        () => upgradeSheet(env)
    )
);
phaseItem("construction_sale_pass", _t("Pasar el resumen a la cotización…"), 40, (env) =>
    passSummary(env)
);
topbarMenuRegistry.addChild("construction_sale_new_version", ["construction_planner"], {
    name: _t("Nueva versión"),
    sequence: 50,
    isVisible: isSale,
    isEnabled: (env) => ["sent", "awarded"].includes(phaseOf(env)),
    execute: (env) => newVersion(env),
});
