/**
 * Pestañas de planificación del maestro (paquete 1.13, M113-07 a M113-11):
 * estado de la hoja en INICIO, «Actualizar CONTROL», «Traer de Odoo», ficha
 * anterior y siguiente, precio de FICHA a VENTA y fechas de PROGRAMA a OBRA.
 */
import { registries } from "@odoo/o-spreadsheet";
import { onMounted } from "@odoo/owl";
import { SpreadsheetAction } from "@documents_spreadsheet/bundle/actions/spreadsheet_action";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import {
    activateSheet,
    afterValidateHooks,
    collectSheets,
    dispatchBatch,
    keyColumns,
    lastDataRow,
    normText,
} from "@al_construction_planner_spreadsheet/send_to_planner";
import { applyImport } from "./sheet_import";
import { SheetPreviewDialog, comparePreview, readSheets } from "./sheet_restore";

const { topbarMenuRegistry } = registries;

export const START_SHEET = "INICIO";
export const CARD_SHEET = "FICHA";
export const PROGRAM_SHEET = "PROGRAMA";
export const CONTROL_SHEET = "CONTROL";
// Celdas fijas de la plantilla (models/planning_sheets.py).
const STATE_CELL = { col: 1, row: 6 }; // B7
const CARD_TYPOLOGY = { col: 1, row: 2 }; // B3
const CARD_PRICE = { col: 1, row: 21 }; // B22
const PROGRAM_START = { col: 1, row: 11 }; // B12
const PROGRAM_END = { col: 1, row: 12 }; // B13
const CONTROL_RESULT = { col: 1, row: 2 }; // B3
const CONTROL_UPDATED = { col: 1, row: 3 }; // B4
const CONTROL_FIRST_ROW = 6; // fila 7
const CONTROL_ROWS = 200;
const CONTROL_PLANNER_COL = 13; // N
const CONTROL_ORIGIN_COL = 18; // S
const MATCH = "Coincide";

const isFurniture = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "furniture";
const activeSheetIs = (env, name) =>
    isFurniture(env) &&
    env.model.getters.getSheetName(env.model.getters.getActiveSheetId()) === name;

function sheetIdOf(model, name) {
    return model.getters.getSheetIdByName(name);
}

function valueAt(model, sheetId, position) {
    const value = model.getters.getEvaluatedCell({ sheetId, ...position }).value;
    return value === null || value === undefined ? "" : value;
}

/** Texto de una celda para escribirla tal cual (las fórmulas, con «=»). */
function quoted(text) {
    return `="${String(text).replaceAll('"', '""')}"`;
}

/** Número de serie de la hoja → «AAAA-MM-DD». */
function serialToIso(serial) {
    if (typeof serial !== "number") {
        return "";
    }
    const date = new Date(Date.UTC(1899, 11, 30) + Math.round(serial) * 86400000);
    return date.toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Estado de la hoja en INICIO (M113-07, lo escribe el sistema)
// ---------------------------------------------------------------------------
function writeState(model, label) {
    const sheetId = sheetIdOf(model, START_SHEET);
    if (!sheetId || !label || valueAt(model, sheetId, STATE_CELL) === label) {
        return;
    }
    model.dispatch("UPDATE_CELL", { sheetId, ...STATE_CELL, content: label });
}

/**
 * M117-15, punto 7: el valor inicial vigente en la configuración, en la columna
 * oculta J de PARAMETROS; si difiere del copiado, la fila lo avisa. Solo escribe
 * lo que cambió: abrir la hoja no debe generar revisiones.
 */
export function writeCurrentParameters(model, current) {
    const getters = model.getters;
    const sheetId = sheetIdOf(model, "PARAMETROS");
    if (!sheetId || !current) {
        return;
    }
    const commands = [];
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const key = getters.getCell({ sheetId, col: 6, row })?.content;
        const value = key && current[key];
        if (key && value !== undefined && (getters.getCell({ sheetId, col: 9, row })?.content || "") !== value) {
            commands.push(["UPDATE_CELL", { sheetId, col: 9, row, content: value }]);
        }
    }
    dispatchBatch(model, commands);
}

/**
 * M117-16, punto 3: si la cotización cambió, OBRA se actualiza al abrir la hoja y lo
 * dice; con otro cliente o moneda, el tarifario hay que traerlo de nuevo.
 */
function refreshSaleObra(model, data, env) {
    const values = data?.construction_sale_obra;
    const sheetId = sheetIdOf(model, "OBRA");
    if (!values || !sheetId || data.isReadonly) {
        return;
    }
    const getters = model.getters;
    const commands = [];
    const changed = [];
    for (let row = 1; row < 30; row++) {
        const name = getters.getCell({ sheetId, col: 0, row })?.content;
        if (name && values[name] !== undefined) {
            const current = String(getters.getEvaluatedCell({ sheetId, col: 1, row }).value ?? "");
            if (current !== String(values[name]) && name !== "Fecha de cotización") {
                commands.push(["UPDATE_CELL", { sheetId, col: 1, row, content: String(values[name]) }]);
                changed.push(name);
            }
        }
    }
    if (commands.length) {
        dispatchBatch(model, commands);
        const rates = changed.includes("Cliente")
            ? _t(" El tarifario se trajo para otro cliente o moneda: ejecute Traer tarifario.")
            : "";
        env.constructionNotify(
            _t("OBRA actualizada desde la cotización: %(fields)s.", { fields: changed.join(", ") }) + rates,
            rates ? "warning" : "info",
            { sticky: Boolean(rates) }
        );
    }
}

/**
 * M117-16, punto 5: la hoja ya en edición escribe la versión nueva y la fila de
 * «Cambios de la cotización» con su fecha.
 */
function writePendingVersion(model, data, env) {
    if (!data?.construction_sale_pending) {
        return;
    }
    const { version, date } = JSON.parse(data.construction_sale_pending);
    const getters = model.getters;
    const sheetId = sheetIdOf(model, "OBRA");
    const commands = [];
    for (let row = 1; row < 30; row++) {
        if (getters.getCell({ sheetId, col: 0, row })?.content === "Versión de la cotización") {
            commands.push(["UPDATE_CELL", { sheetId, col: 1, row, content: version }]);
        }
    }
    let free = 1;
    while (getters.getCell({ sheetId, col: 3, row: free })?.content) {
        free++;
    }
    commands.push(
        ["UPDATE_CELL", { sheetId, col: 3, row: free, content: date }],
        ["UPDATE_CELL", { sheetId, col: 4, row: free, content: version }]
    );
    dispatchBatch(model, commands);
    data.construction_sale_pending = "";
    env.constructionCall("construction_sale_pending_done");
}

afterValidateHooks.push((env, result) => {
    if (isFurniture(env)) {
        writeState(env.model, result.state);
    }
});

patch(SpreadsheetAction.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            if (this.model && this.data?.construction_sheet_kind === "sale") {
                writeCurrentParameters(this.model, this.data?.construction_parameter_current);
                writePendingVersion(this.model, this.data, this.env);
                refreshSaleObra(this.model, this.data, this.env);
            }
            if (!this.model || !isFurniture(this.env)) {
                return;
            }
            writeState(this.model, this.data?.construction_sheet_state);
            writeCurrentParameters(this.model, this.data?.construction_parameter_current);
            // Después de un envío, CONTROL compara la hoja con el planificador.
            if (this.data?.construction_control_pending && sheetIdOf(this.model, CONTROL_SHEET)) {
                // El entorno de la acción no trae el modelo de la hoja (M117-06).
                updateControl({ ...this.env, model: this.model }, { quiet: true });
            }
        });
    },
});

// ---------------------------------------------------------------------------
// CONTROL (M113-11)
// ---------------------------------------------------------------------------
/** Filas de FUENTES con Piso, Muebles, Módulos y ML (el origen de OT). */
export function originRows(model) {
    const rows = collectSheets(model, ["FUENTES"]).FUENTES || [];
    const header = (rows[0] || []).map(normText);
    const columns = ["piso", "muebles", "modulos", "ml"].map((name) => header.indexOf(name));
    if (columns.some((col) => col < 0)) {
        return [];
    }
    return rows
        .slice(1)
        .filter((row) => row[columns[0]] !== "" && row[columns[0]] !== undefined)
        .map((row) => columns.map((col) => row[col] ?? ""));
}

function writeBlock(model, sheetId, firstCol, rows) {
    const commands = [];
    for (let index = 0; index < CONTROL_ROWS; index++) {
        const values = rows[index] || ["", "", "", ""];
        values.forEach((value, offset) => {
            commands.push([
                "UPDATE_CELL",
                {
                    sheetId,
                    col: firstCol + offset,
                    row: CONTROL_FIRST_ROW + index,
                    // El piso como texto: «2» no debe volverse el número 2.
                    content: value === "" ? "" : offset === 0 ? quoted(value) : String(value),
                },
            ]);
        });
    }
    dispatchBatch(model, commands);
}

export async function updateControl(env, { quiet = false } = {}) {
    const model = env.model;
    const sheetId = sheetIdOf(model, CONTROL_SHEET);
    if (!sheetId) {
        env.constructionNotify(_t("Esta hoja no tiene la pestaña CONTROL."), "warning");
        return;
    }
    const planner = await env.constructionCall("construction_control_counts");
    writeBlock(model, sheetId, CONTROL_PLANNER_COL, planner);
    writeBlock(model, sheetId, CONTROL_ORIGIN_COL, originRows(model));
    model.dispatch("UPDATE_CELL", {
        sheetId,
        ...CONTROL_UPDATED,
        content: luxon.DateTime.now().toFormat("dd/MM/yyyy HH:mm"),
    });
    const result = valueAt(model, sheetId, CONTROL_RESULT);
    await env.constructionCall("construction_control_done", result === MATCH);
    if (!quiet) {
        activateSheet(model, sheetId);
        env.constructionNotify(
            result === MATCH
                ? _t("CONTROL: la hoja coincide con el planificador.")
                : _t("CONTROL: %s. Vea los pisos en rojo.", result),
            result === MATCH ? "success" : "warning"
        );
    }
}

// ---------------------------------------------------------------------------
// «Traer de Odoo» del maestro (M113-11)
// ---------------------------------------------------------------------------
async function bringFromOdoo(env) {
    const payload = await env.constructionCall("construction_furniture_odoo_rows");
    const today = readSheets(env, env.model);
    env.constructionDialog(SheetPreviewDialog, {
        title: _t("Traer de Odoo"),
        intro: _t(
            "Antes de escribir, la hoja guarda una versión: se puede volver atrás con Restaurar versión."
        ),
        rows: comparePreview(today, payload.sheets),
        confirm: async () => {
            await env.constructionCall(
                "construction_version_before",
                _t("Antes de traer los datos de Odoo")
            );
            await applyImport(env, payload, { logImport: false });
            env.constructionNotify(_t("Datos de Odoo traídos a la hoja (versión anterior guardada)."));
        },
    });
}

// ---------------------------------------------------------------------------
// FICHA (M113-09)
// ---------------------------------------------------------------------------
/** Códigos de TIPOLOGIAS en su orden. */
function typologyCodes(model) {
    const keys = keyColumns(model).TIPOLOGIAS || {};
    const col = keys.code ?? 0;
    return (collectSheets(model, ["TIPOLOGIAS"]).TIPOLOGIAS || [])
        .slice(1)
        .map((row) => row[col])
        .filter((code) => code !== "" && code !== undefined);
}

export function showCard(env, code) {
    const model = env.model;
    const sheetId = sheetIdOf(model, CARD_SHEET);
    if (!sheetId) {
        env.constructionNotify(_t("Esta hoja no tiene la pestaña FICHA."), "warning");
        return;
    }
    model.dispatch("UPDATE_CELL", { sheetId, ...CARD_TYPOLOGY, content: String(code) });
    activateSheet(model, sheetId);
}

function moveCard(env, step) {
    const model = env.model;
    const codes = typologyCodes(model);
    if (!codes.length) {
        env.constructionNotify(_t("TIPOLOGIAS no tiene tipologías."), "warning");
        return;
    }
    const current = valueAt(model, sheetIdOf(model, CARD_SHEET), CARD_TYPOLOGY);
    const index = codes.findIndex((code) => String(code) === String(current));
    const next = index < 0 ? 0 : (index + step + codes.length) % codes.length;
    showCard(env, codes[next]);
}

/** Tipología de la fila seleccionada (columna «Tipología» o el código de TIPOLOGIAS). */
export function selectedTypology(env) {
    const model = env.model;
    const getters = model.getters;
    const sheetId = getters.getActiveSheetId();
    const name = getters.getSheetName(sheetId);
    const keys = keyColumns(model)[name] || {};
    const col = name === "TIPOLOGIAS" ? keys.code : keys.typology;
    if (col === undefined) {
        return "";
    }
    const { row } = getters.getActivePosition();
    return row >= 1 ? valueAt(model, sheetId, { col, row }) : "";
}

function viewCard(env) {
    const code = selectedTypology(env);
    if (code === "") {
        env.constructionNotify(_t("Seleccione una fila con tipología."), "warning");
        return;
    }
    showCard(env, code);
}

/** Fila (0 = encabezado) de ``sheet`` cuyas claves valen ``match``; -1 si no hay. */
function findRow(rows, columns, match) {
    return rows.findIndex(
        (row, index) =>
            index > 0 &&
            Object.entries(match).every(
                ([key, value]) => normText(row[columns[key]]) === normText(value)
            )
    );
}

/** Escribe ``values`` por clave en la fila ``match`` o en una fila nueva al final. */
function upsertRow(model, name, match, values) {
    const sheetId = sheetIdOf(model, name);
    const columns = keyColumns(model)[name] || {};
    if (!sheetId || Object.keys(values).some((key) => columns[key] === undefined)) {
        return false;
    }
    const rows = collectSheets(model, [name])[name] || [];
    let row = findRow(rows, columns, match);
    if (row < 0) {
        row = Math.max(1, lastDataRow(model.getters, sheetId) + 1);
    }
    dispatchBatch(
        model,
        Object.entries(values).map(([key, value]) => [
            "UPDATE_CELL",
            { sheetId, col: columns[key], row, content: String(value) },
        ])
    );
    return true;
}

function writePrice(env) {
    const model = env.model;
    const cardId = sheetIdOf(model, CARD_SHEET);
    const typology = valueAt(model, cardId, CARD_TYPOLOGY);
    const price = valueAt(model, cardId, CARD_PRICE);
    if (typology === "" || typeof price !== "number") {
        env.constructionNotify(
            _t("Elija la tipología y escriba el precio nuevo en FICHA (celda B22)."),
            "warning"
        );
        return;
    }
    const columns = keyColumns(model);
    const sales = collectSheets(model, ["VENTA", "CONTRATOS"]);
    const saleCols = columns.VENTA || {};
    const existing = (sales.VENTA || [])
        .slice(1)
        .find((row) => normText(row[saleCols.typology]) === normText(typology));
    const contract =
        (existing && existing[saleCols.contract]) ||
        ((sales.CONTRATOS || [])[1] || [])[(columns.CONTRATOS || {}).name ?? 0] ||
        "";
    if (!contract) {
        env.constructionNotify(_t("Escriba primero el contrato en CONTRATOS."), "warning");
        return;
    }
    upsertRow(model, "VENTA", { contract, typology }, { contract, typology, price });
    env.constructionNotify(_t("Precio de %(typology)s en VENTA: %(price)s.", { typology, price }));
}

// ---------------------------------------------------------------------------
// PROGRAMA (M113-10): solo Inicio y Fin pasan a OBRA
// ---------------------------------------------------------------------------
function writeDates(env) {
    const model = env.model;
    const programId = sheetIdOf(model, PROGRAM_SHEET);
    const start = serialToIso(valueAt(model, programId, PROGRAM_START));
    const end = serialToIso(valueAt(model, programId, PROGRAM_END));
    if (!start || !end) {
        env.constructionNotify(
            _t("PROGRAMA necesita el inicio de producción y los pisos del ARBOL."),
            "warning"
        );
        return;
    }
    const ok =
        upsertRow(model, "OBRA", { key: "Inicio" }, { key: "Inicio", value: start }) &&
        upsertRow(model, "OBRA", { key: "Fin" }, { key: "Fin", value: end });
    env.constructionNotify(
        ok
            ? _t("OBRA: Inicio %(start)s y Fin %(end)s.", { start, end })
            : _t("No se encontraron las columnas Dato y Valor de OBRA."),
        ok ? "success" : "warning"
    );
}

// Opciones del menú «Planificación de obra» del maestro.
const items = [
    ["construction_furniture_control", 150, _t("Actualizar CONTROL"), updateControl],
    ["construction_furniture_odoo", 170, _t("Traer de Odoo"), bringFromOdoo],
    ["construction_furniture_view_card", 175, _t("Ver ficha de la tipología"), viewCard],
];
for (const [id, sequence, name, execute] of items) {
    topbarMenuRegistry.addChild(id, ["construction_planner"], {
        name,
        sequence,
        isVisible: isFurniture,
        execute: (env) => execute(env),
    });
}
const sheetItems = [
    ["construction_card_previous", 176, _t("‹ Tipología anterior"), CARD_SHEET, (env) => moveCard(env, -1)],
    ["construction_card_next", 177, _t("Tipología siguiente ›"), CARD_SHEET, (env) => moveCard(env, 1)],
    ["construction_card_price", 178, _t("Escribir el precio en VENTA"), CARD_SHEET, writePrice],
    ["construction_program_dates", 179, _t("Escribir fechas en OBRA"), PROGRAM_SHEET, writeDates],
];
for (const [id, sequence, name, sheet, execute] of sheetItems) {
    topbarMenuRegistry.addChild(id, ["construction_planner"], {
        name,
        sequence,
        isVisible: (env) => activeSheetIs(env, sheet),
        execute: (env) => execute(env),
    });
}
