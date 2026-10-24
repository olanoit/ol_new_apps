import { registries } from "@odoo/o-spreadsheet";
import { useSubEnv } from "@odoo/owl";
import { SpreadsheetAction } from "@documents_spreadsheet/bundle/actions/spreadsheet_action";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

const { topbarMenuRegistry } = registries;

/**
 * Valores calculados de las pestañas de la hoja, fila por fila, sin las filas
 * vacías del final.
 */
export function collectSheets(model) {
    const getters = model.getters;
    const sheets = {};
    for (const sheetId of getters.getSheetIds()) {
        const zone = getters.getSheetZone(sheetId);
        const rows = [];
        for (let row = zone.top; row <= zone.bottom; row++) {
            const values = [];
            for (let col = zone.left; col <= zone.right; col++) {
                const value = getters.getEvaluatedCell({ sheetId, col, row }).value;
                values.push(value === null || value === undefined ? "" : value);
            }
            while (values.length && values[values.length - 1] === "") {
                values.pop();
            }
            rows.push(values);
        }
        while (rows.length && !rows[rows.length - 1].length) {
            rows.pop();
        }
        sheets[getters.getSheetName(sheetId)] = rows;
    }
    return sheets;
}

/** Id de la pestaña ``name``; la crea al final si no existe. */
function ensureSheet(model, name) {
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
function writeRows(model, sheetId, rows, startRow) {
    rows.forEach((values, rowIndex) => {
        values.forEach((value, col) => {
            model.dispatch("UPDATE_CELL", {
                sheetId,
                col,
                row: startRow + rowIndex,
                content: value === null || value === undefined ? "" : String(value),
            });
        });
    });
}

/** Borra los datos de la pestaña desde la segunda fila. */
function clearData(model, sheetId) {
    const zone = model.getters.getSheetZone(sheetId);
    if (zone.bottom >= 1) {
        model.dispatch("DELETE_CONTENT", {
            sheetId,
            target: [{ top: 1, bottom: zone.bottom, left: zone.left, right: zone.right }],
        });
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
            constructionCall: (method, ...args) =>
                this.orm.call("documents.document", method, [[this.resId], ...args]),
            constructionDoAction: (action) => this.actionService.doAction(action),
            constructionNotify: (message, type = "success") => notification.add(message, { type }),
        });
    },
});

const isBudget = (env) => env.constructionSheetKind && env.constructionSheetKind() === "budget";
const isFurniture = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "furniture";

async function send(env, target) {
    const action = await env.constructionCall(
        "action_construction_send_to_planner",
        collectSheets(env.model),
        target
    );
    await env.constructionDoAction(action);
}

async function validate(env) {
    const result = await env.constructionCall(
        "action_construction_validate",
        collectSheets(env.model)
    );
    const sheetId = ensureSheet(env.model, "ERRORES");
    clearData(env.model, sheetId);
    writeRows(env.model, sheetId, [[_t("Hoja"), _t("Fila"), _t("Columna"), _t("Mensaje")]], 0);
    writeRows(env.model, sheetId, result.errors, 1);
    const warnings = result.warnings.map((warning) => ["", "", _t("Aviso"), warning]);
    writeRows(env.model, sheetId, warnings, 1 + result.errors.length);
    env.constructionNotify(
        result.errors.length
            ? _t("%s errores: vea la pestaña ERRORES.", result.errors.length)
            : _t("La plantilla no tiene errores."),
        result.errors.length ? "danger" : "success"
    );
}

async function updateCosts(env) {
    const model = env.model;
    const sheetId = model.getters.getSheetIdByName("INSUMOS");
    if (!sheetId) {
        return;
    }
    const rows = collectSheets(model).INSUMOS || [];
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

async function bringFromOdoo(env) {
    const data = await env.constructionCall("construction_odoo_rows");
    for (const [name, rows] of Object.entries(data)) {
        if (!rows.length) {
            continue;
        }
        const sheetId = env.model.getters.getSheetIdByName(name);
        if (!sheetId) {
            continue;
        }
        if (name === "OBRA") {
            writeRows(env.model, sheetId, rows, 0);
            continue;
        }
        writeRows(env.model, sheetId, rows, 1);
    }
    env.constructionNotify(_t("Datos de Odoo traídos a la hoja."));
}

async function newVersion(env) {
    const action = await env.constructionCall("action_construction_new_version");
    await env.constructionDoAction(action);
}

topbarMenuRegistry.add("construction_planner", {
    name: _t("Planificación de obra"),
    sequence: 95,
    isVisible: isBudget,
});
topbarMenuRegistry.addChild("construction_send_budget", ["construction_planner"], {
    name: _t("Enviar al planificador: presupuesto"),
    sequence: 10,
    execute: (env) => send(env, "budget"),
    icon: "o-spreadsheet-Icon.ARROW_RIGHT",
});
topbarMenuRegistry.addChild("construction_send_plan", ["construction_planner"], {
    name: _t("Enviar al planificador: presupuesto y plan"),
    sequence: 20,
    execute: (env) => send(env, "plan"),
});
topbarMenuRegistry.addChild("construction_validate", ["construction_planner"], {
    name: _t("Validar plantilla"),
    sequence: 30,
    execute: (env) => validate(env),
});
topbarMenuRegistry.addChild("construction_update_costs", ["construction_planner"], {
    name: _t("Actualizar insumos"),
    sequence: 40,
    execute: (env) => updateCosts(env),
});
topbarMenuRegistry.addChild("construction_bring", ["construction_planner"], {
    name: _t("Traer de Odoo"),
    sequence: 50,
    execute: (env) => bringFromOdoo(env),
});
topbarMenuRegistry.addChild("construction_new_version", ["construction_planner"], {
    name: _t("Nueva versión"),
    sequence: 60,
    execute: (env) => newVersion(env),
});
// Maestro de mobiliario (puente de mobiliario): Archivo › Enviar al planificador.
topbarMenuRegistry.addChild("construction_send_to_planner", ["file"], {
    name: _t("Enviar al planificador"),
    sequence: 25,
    isVisible: isFurniture,
    execute: (env) => send(env, "budget"),
    icon: "o-spreadsheet-Icon.ARROW_RIGHT",
});
