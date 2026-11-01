import { registries } from "@odoo/o-spreadsheet";
import { useSubEnv } from "@odoo/owl";
import { SpreadsheetAction } from "@documents_spreadsheet/bundle/actions/spreadsheet_action";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

const { topbarMenuRegistry } = registries;

export const KEYS_SHEET = "_CLAVES";
export const ERRORS_SHEET = "ERRORES";

const isEmpty = (value) => value === null || value === undefined || value === "";

/**
 * Última fila (0 = la primera) con algún valor en la pestaña, leyendo solo
 * las celdas que existen (paquete 1.13, M113-02): una hoja de 8 000 filas
 * con fórmulas vacías no se recorre entera.
 */
function lastDataRow(getters, sheetId) {
    let last = -1;
    for (const cellId of Object.keys(getters.getCells(sheetId))) {
        const position = getters.getCellPosition(cellId);
        if (position.row <= last) {
            continue;
        }
        if (!isEmpty(getters.getEvaluatedCell(position).value)) {
            last = position.row;
        }
    }
    return last;
}

/**
 * Valores calculados de las pestañas de la hoja, fila por fila, sin las filas
 * vacías del final. Con ``names``, solo esas pestañas (M113-02: el envío no
 * lleva REFERENCIAS, _LISTAS ni RESUMEN).
 */
export function collectSheets(model, names = null) {
    const getters = model.getters;
    const sheets = {};
    for (const sheetId of getters.getSheetIds()) {
        const name = getters.getSheetName(sheetId);
        if (names && !names.includes(name)) {
            continue;
        }
        const zone = getters.getSheetZone(sheetId);
        const bottom = Math.min(zone.bottom, lastDataRow(getters, sheetId));
        const rows = [];
        for (let row = zone.top; row <= bottom; row++) {
            const values = [];
            for (let col = zone.left; col <= zone.right; col++) {
                const value = getters.getEvaluatedCell({ sheetId, col, row }).value;
                values.push(isEmpty(value) ? "" : value);
            }
            while (values.length && values[values.length - 1] === "") {
                values.pop();
            }
            rows.push(values);
        }
        while (rows.length && !rows[rows.length - 1].length) {
            rows.pop();
        }
        sheets[name] = rows;
    }
    return sheets;
}

/** {pestaña: {clave: columna (0 = A)}} de la pestaña oculta _CLAVES (M116-09). */
export function keyColumns(model) {
    const result = {};
    const rows = collectSheets(model, [KEYS_SHEET])[KEYS_SHEET] || [];
    for (const [sheet, key, column] of rows.slice(1)) {
        if (sheet && key && typeof column === "number" && column >= 1) {
            (result[sheet] = result[sheet] || {})[key] = column - 1;
        }
    }
    return result;
}

/** Id de la pestaña ``name``; la crea al final si no existe. */
export function ensureSheet(model, name) {
    const getters = model.getters;
    let sheetId = getters.getSheetIdByName(name);
    if (!sheetId) {
        sheetId = model.uuidGenerator.uuidv4();
        model.dispatch("CREATE_SHEET", {
            sheetId,
            name,
            position: getters.getSheetIds().length,
        });
    }
    return sheetId;
}

/** Escribe ``rows`` desde la fila ``startRow`` (0 = la primera), columna A. */
export function writeRows(model, sheetId, rows, startRow) {
    rows.forEach((values, rowIndex) => {
        values.forEach((value, col) => {
            model.dispatch("UPDATE_CELL", {
                sheetId,
                col,
                row: startRow + rowIndex,
                content: isEmpty(value) || value === false ? "" : String(value),
            });
        });
    });
}

/** Borra los datos de la pestaña desde la fila ``fromRow`` (0 = la primera). */
function clearData(model, sheetId, fromRow = 1) {
    const zone = model.getters.getSheetZone(sheetId);
    if (zone.bottom >= fromRow) {
        model.dispatch("DELETE_CONTENT", {
            sheetId,
            target: [{ top: fromRow, bottom: zone.bottom, left: zone.left, right: zone.right }],
        });
    }
}

function activateSheet(model, sheetId) {
    const from = model.getters.getActiveSheetId();
    if (from !== sheetId) {
        model.dispatch("ACTIVATE_SHEET", { sheetIdFrom: from, sheetIdTo: sheetId });
    }
}

patch(SpreadsheetAction.prototype, {
    setup() {
        super.setup(...arguments);
        const notification = useService("notification");
        useSubEnv({
            constructionSheetKind: () =>
                this.data?.construction_project_id || this.data?.construction_sheet_kind
                    ? this.data?.construction_sheet_kind || "furniture"
                    : false,
            constructionSendSheets: () => this.data?.construction_send_sheets || null,
            constructionCall: (method, ...args) =>
                this.orm.call("documents.document", method, [[this.resId], ...args]),
            constructionDoAction: (action) => this.actionService.doAction(action),
            constructionNotify: (message, type = "success") => notification.add(message, { type }),
            constructionOfferLocked: () => Boolean(this.data?.construction_offer_locked),
        });
    },
});

const isBudget = (env) => env.constructionSheetKind && env.constructionSheetKind() === "budget";
const isFurniture = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "furniture";

/** Las pestañas que lee el envío (M113-02). */
function collectForSend(env) {
    const names = env.constructionSendSheets && env.constructionSendSheets();
    return collectSheets(env.model, names && names.length ? names : null);
}

async function send(env, target) {
    const action = await env.constructionCall(
        "action_construction_send_to_planner",
        collectForSend(env),
        target
    );
    await env.constructionDoAction(action);
}

/**
 * Pestaña ERRORES común (paquete 1.16, M116-09): estado arriba y, por fila,
 * hoja, fila, columna, mensaje, tipo y un enlace «Ir» a la pestaña.
 */
export function writeErrors(model, result) {
    const sheetId = ensureSheet(model, ERRORS_SHEET);
    clearData(model, sheetId, 0);
    const now = luxon.DateTime.now().toFormat("dd/MM/yyyy HH:mm");
    writeRows(
        model,
        sheetId,
        [
            [
                _t("Validada el %(date)s · %(errors)s errores · %(warnings)s avisos", {
                    date: now,
                    errors: result.errors,
                    warnings: result.warnings,
                }),
            ],
            [_t("Hoja"), _t("Fila"), _t("Columna"), _t("Mensaje"), _t("Tipo"), _t("Ir")],
        ],
        0
    );
    const rows = result.rows.map(([sheet, row, column, message, kind]) => {
        const target = sheet && model.getters.getSheetIdByName(sheet);
        const link = target ? `=HYPERLINK("o-spreadsheet://${target}","${_t("Ir")}")` : "";
        return [sheet, row, column, message, kind, link];
    });
    writeRows(model, sheetId, rows, 2);
    return sheetId;
}

async function validate(env, { quiet = false } = {}) {
    const result = await env.constructionCall(
        "action_construction_validate",
        collectForSend(env)
    );
    const sheetId = writeErrors(env.model, result);
    if (result.errors) {
        activateSheet(env.model, sheetId);
    }
    if (!quiet || result.errors) {
        env.constructionNotify(
            result.errors
                ? _t("%s errores: vea la pestaña ERRORES.", result.errors)
                : _t("La hoja no tiene errores (%s avisos).", result.warnings),
            result.errors ? "danger" : "success"
        );
    }
    return result;
}

/** M113-03: el maestro se valida antes de abrir el asistente; con errores no se envía. */
async function sendFurniture(env) {
    const result = await validate(env, { quiet: true });
    if (result.errors) {
        return;
    }
    await send(env, "budget");
}

async function updateCosts(env) {
    const model = env.model;
    const sheetId = model.getters.getSheetIdByName("INSUMOS");
    if (!sheetId) {
        return;
    }
    const rows = collectSheets(model, ["INSUMOS"]).INSUMOS || [];
    const header = rows[0] || [];
    const priceCol = header.findIndex((name) =>
        ["Precio sin IGV", "Precio", "Costo vigente"].includes(name)
    );
    const codes = rows.slice(1).map((row) => row[0]).filter(Boolean);
    const costs = await env.constructionCall("construction_current_costs", codes);
    let updated = 0;
    rows.slice(1).forEach((row, index) => {
        const current = costs[row[0]];
        if (current && priceCol >= 0) {
            model.dispatch("UPDATE_CELL", {
                sheetId,
                col: priceCol,
                row: index + 1,
                content: String(current[0]),
            });
            updated++;
        }
    });
    env.constructionNotify(_t("%s insumos con el costo vigente del maestro.", updated));
}

const normText = (text) =>
    String(text || "")
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .toLowerCase()
        .trim();

/**
 * Escribe filas por la clave de cada columna (M116-09): la columna sale de
 * _CLAVES o, en una hoja anterior, de su encabezado. Las columnas de fórmula
 * no se tocan.
 */
function writeKeyed(model, name, spec, keys) {
    const sheetId = model.getters.getSheetIdByName(name);
    if (!sheetId) {
        return;
    }
    const header = (collectSheets(model, [name])[name] || [[]])[0] || [];
    const byHeader = {};
    header.forEach((text, col) => {
        byHeader[normText(text)] = byHeader[normText(text)] ?? col;
    });
    const columns = {};
    for (const key of spec.keys) {
        let col = keys[name]?.[key];
        if (col === undefined) {
            for (const alias of spec.aliases[key] || [key]) {
                if (byHeader[normText(alias)] !== undefined) {
                    col = byHeader[normText(alias)];
                    break;
                }
            }
        }
        const formula = col !== undefined && model.getters.getCell({ sheetId, col, row: 1 });
        if (col === undefined || (formula && formula.isFormula)) {
            continue;
        }
        columns[key] = col;
    }
    spec.rows.forEach((values, rowIndex) => {
        spec.keys.forEach((key, index) => {
            if (columns[key] === undefined) {
                return;
            }
            model.dispatch("UPDATE_CELL", {
                sheetId,
                col: columns[key],
                row: rowIndex + 1,
                content: isEmpty(values[index]) ? "" : String(values[index]),
            });
        });
    });
}

async function bringFromOdoo(env) {
    const data = await env.constructionCall("construction_odoo_rows");
    // OBRA y PRESUPUESTO llegan con su primera fila (encabezados y fórmulas).
    const fromTop = data._from_top || ["OBRA"];
    const keys = keyColumns(env.model);
    for (const [name, spec] of Object.entries(data._keyed || {})) {
        writeKeyed(env.model, name, spec, keys);
    }
    for (const [name, rows] of Object.entries(data)) {
        if (name.startsWith("_") || !rows.length) {
            continue;
        }
        const sheetId = env.model.getters.getSheetIdByName(name);
        if (!sheetId) {
            continue;
        }
        writeRows(env.model, sheetId, rows, fromTop.includes(name) ? 0 : 1);
    }
    env.constructionNotify(_t("Datos de Odoo traídos a la hoja."));
}

async function newVersion(env) {
    const action = await env.constructionCall("action_construction_new_version");
    await env.constructionDoAction(action);
}

async function downloadTemplate(env) {
    const action = await env.constructionCall("action_construction_download_template");
    await env.constructionDoAction(action);
}

// La barra de la hoja muestra todos los menús raíz (no evalúa su isVisible):
// un solo menú «Planificación de obra» y cada opción visible según la hoja
// (paquete 1.13, M113-03: el maestro no ve las opciones del presupuesto).
topbarMenuRegistry.add("construction_planner", {
    name: _t("Planificación de obra"),
    sequence: 95,
});
const budgetItems = [
    ["construction_send_budget", {
        name: _t("Enviar al planificador: presupuesto"),
        sequence: 10,
        // Con la cotización confirmada, precio y metrado van por cambio de obra (D3).
        isEnabled: (env) => !(env.constructionOfferLocked && env.constructionOfferLocked()),
        execute: (env) => send(env, "budget"),
        icon: "o-spreadsheet-Icon.ARROW_RIGHT",
    }],
    ["construction_send_plan", {
        name: _t("Enviar al planificador: presupuesto y plan"),
        sequence: 20,
        execute: (env) => send(env, "plan"),
    }],
    ["construction_validate", {
        name: _t("Validar plantilla"),
        sequence: 30,
        execute: (env) => validate(env),
    }],
    ["construction_update_costs", {
        name: _t("Actualizar insumos"),
        sequence: 40,
        execute: (env) => updateCosts(env),
    }],
    ["construction_bring", {
        name: _t("Traer de Odoo"),
        sequence: 50,
        execute: (env) => bringFromOdoo(env),
    }],
    ["construction_new_version", {
        name: _t("Nueva versión"),
        sequence: 60,
        execute: (env) => newVersion(env),
    }],
];
// Maestro de mobiliario: Importar Excel, Control de alcance y Traer de Odoo
// llegan con los bloques 4b y 4c.
const furnitureItems = [
    ["construction_furniture_template", {
        name: _t("Descargar formato de carga"),
        sequence: 120,
        separator: true,
        execute: (env) => downloadTemplate(env),
    }],
    ["construction_furniture_validate", {
        name: _t("Validar"),
        sequence: 140,
        execute: (env) => validate(env),
    }],
    ["construction_furniture_send", {
        name: _t("Enviar al planificador"),
        sequence: 160,
        separator: true,
        execute: (env) => sendFurniture(env),
        icon: "o-spreadsheet-Icon.ARROW_RIGHT",
    }],
    ["construction_furniture_version", {
        name: _t("Nueva versión"),
        sequence: 190,
        execute: (env) => newVersion(env),
    }],
];
for (const [id, item] of budgetItems) {
    topbarMenuRegistry.addChild(id, ["construction_planner"], { ...item, isVisible: isBudget });
}
for (const [id, item] of furnitureItems) {
    topbarMenuRegistry.addChild(id, ["construction_planner"], { ...item, isVisible: isFurniture });
}
topbarMenuRegistry.addChild("construction_no_sheet", ["construction_planner"], {
    name: _t("Abra la hoja de trabajo desde la obra o la cotización"),
    sequence: 200,
    isVisible: (env) => !isBudget(env) && !isFurniture(env),
    isEnabled: () => false,
    execute: () => {},
});
// Archivo › Enviar al planificador se queda (también valida antes).
topbarMenuRegistry.addChild("construction_send_to_planner", ["file"], {
    name: _t("Enviar al planificador"),
    sequence: 25,
    isVisible: isFurniture,
    execute: (env) => sendFurniture(env),
    icon: "o-spreadsheet-Icon.ARROW_RIGHT",
});
