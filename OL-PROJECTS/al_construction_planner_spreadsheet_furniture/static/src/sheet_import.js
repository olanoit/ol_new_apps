import { registries } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import {
    ERRORS_SHEET,
    activateSheet,
    clearCells,
    clearData,
    collectSheets,
    dispatchBatch,
    ensureSheet,
    keyColumns,
    lastDataRow,
    normText,
    validate,
    writeRows,
} from "@al_construction_planner_spreadsheet/send_to_planner";
import { TREE_SHEET, clearFloorGroups, groupTreeByFloor } from "./floor_groups";

const { topbarMenuRegistry } = registries;

const isFurniture = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "furniture";
const EXTRA_STYLE = { bold: true, fillColor: "#D9D9D9" };

/** «B12» → {col: 1, row: 11}. */
function parseRef(ref) {
    const match = /^([A-Z]+)(\d+)$/.exec(ref);
    let col = 0;
    for (const char of match[1]) {
        col = col * 26 + char.charCodeAt(0) - 64;
    }
    return { col: col - 1, row: Number(match[2]) - 1 };
}

/** La pestaña tiene al menos ``rows`` filas. */
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
 * Amplía el maestro con las fórmulas, listas y marcas de la plantilla para
 * las filas nuevas (M113-05), y los rangos de RESUMEN.
 */
function applyExtension(model, extension) {
    const getters = model.getters;
    const commands = [];
    for (const [name, part] of Object.entries(extension.sheets || {})) {
        const sheetId = getters.getSheetIdByName(name);
        if (!sheetId) {
            continue;
        }
        ensureRows(model, sheetId, part.row_number);
        for (const [ref, content] of Object.entries(part.cells)) {
            commands.push(["UPDATE_CELL", { sheetId, ...parseRef(ref), content }]);
        }
        for (const rule of part.rules) {
            commands.push([
                "ADD_DATA_VALIDATION_RULE",
                {
                    sheetId,
                    rule: { id: rule.id, criterion: rule.criterion, isBlocking: rule.isBlocking },
                    ranges: [getters.getRangeDataFromZone(sheetId, rule.zone)],
                },
            ]);
        }
        for (const cf of part.conditional) {
            commands.push([
                "ADD_CONDITIONAL_FORMAT",
                {
                    sheetId,
                    cf: { id: cf.id, rule: cf.rule, stopIfTrue: cf.stopIfTrue },
                    ranges: cf.ranges,
                },
            ]);
        }
    }
    const summaryId = getters.getSheetIdByName("RESUMEN");
    if (summaryId) {
        for (const [ref, content] of Object.entries(extension.summary || {})) {
            commands.push(["UPDATE_CELL", { sheetId: summaryId, ...parseRef(ref), content }]);
        }
    }
    dispatchBatch(model, commands);
    for (const [pivotId, bottom] of Object.entries(extension.pivots || {})) {
        try {
            const definition = getters.getPivotCoreDefinition(pivotId);
            if (definition?.dataSet?.zone) {
                model.dispatch("UPDATE_PIVOT", {
                    pivotId,
                    pivot: {
                        ...definition,
                        dataSet: {
                            ...definition.dataSet,
                            zone: { ...definition.dataSet.zone, bottom },
                        },
                    },
                });
            }
        } catch {
            // Una tabla dinámica borrada por el usuario: nada que ampliar.
        }
    }
}

/** Columna de cada clave: _CLAVES o el encabezado; sin las de fórmula. */
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

function writeSheet(model, name, spec, payload, keys) {
    const getters = model.getters;
    const sheetId = ensureSheet(model, name);
    const { columns, header } = columnsOf(model, sheetId, name, spec, keys);
    const used = Object.values(columns);
    let start = 1;
    if (payload.mode === "replace") {
        const bottom = getters.getNumberRows(sheetId) - 1;
        if (bottom >= 1 && used.length) {
            clearCells(
                model,
                sheetId,
                used.map((col) => ({ top: 1, bottom, left: col, right: col }))
            );
        }
    } else {
        start = Math.max(1, lastDataRow(getters, sheetId) + 1);
    }
    ensureRows(model, sheetId, start + spec.rows.length + 1);
    const commands = [];
    spec.rows.forEach((values, index) => {
        spec.keys.forEach((key, position) => {
            if (columns[key] === undefined) {
                return;
            }
            commands.push([
                "UPDATE_CELL",
                { sheetId, col: columns[key], row: start + index, content: values[position] ?? "" },
            ]);
        });
    });
    // Columnas extra del archivo (Fuente, Ancho calculado…): a la derecha, con
    // encabezado gris.
    if (payload.keep_extra && spec.extra_headers.length) {
        let next = header.length;
        const extraCols = spec.extra_headers.map((text) => {
            const existing = header.findIndex((value) => normText(value) === normText(text));
            if (existing >= 0) {
                // M117-03: una columna calculada de la plantilla no se pisa,
                // aunque el archivo la traiga con el mismo encabezado.
                const cell = getters.getCell({ sheetId, col: existing, row: 1 });
                return cell && cell.isFormula ? -1 : existing;
            }
            const col = next++;
            commands.push([
                "UPDATE_CELL",
                { sheetId, col, row: 0, content: text, style: EXTRA_STYLE },
            ]);
            return col;
        });
        spec.extra_rows.forEach((values, index) => {
            values.forEach((value, position) => {
                if (extraCols[position] < 0) {
                    return;
                }
                commands.push([
                    "UPDATE_CELL",
                    { sheetId, col: extraCols[position], row: start + index, content: value ?? "" },
                ]);
            });
        });
    }
    dispatchBatch(model, commands);
    return start + spec.rows.length;
}

/**
 * Amplía el maestro si sus filas con fórmulas y listas no alcanzan para
 * ``needed`` filas de datos (M113-05): las del pedido más un 10 %. Las hojas
 * anteriores al paquete 1.16 no se amplían y lo avisan.
 */
export async function ensureCapacity(env, needed) {
    const current = env.constructionSheetRows();
    if (needed <= current) {
        return true;
    }
    if (!current) {
        env.constructionNotify(
            _t(
                "Esta hoja es anterior al paquete 1.16 y no amplía sus fórmulas: las filas nuevas quedan sin listas ni columnas calculadas."
            ),
            "warning"
        );
        return false;
    }
    const target = Math.ceil(needed * 1.1);
    const extension = await env.constructionCall("construction_sheet_extension", target);
    if (extension && extension.rows) {
        applyExtension(env.model, extension);
        env.constructionSetSheetRows(extension.rows);
    }
    return true;
}

/**
 * Resumen al terminar (paquete 1.17, M117-03 punto 7): filas por pestaña,
 * pestañas copiadas e ignoradas, errores y avisos, y el vínculo a ERRORES.
 */
function notifySummary(env, payload, result) {
    const list = (names) => names.join(", ") || "—";
    const written = Object.entries(payload.sheets).map(
        ([name, spec]) => `${name} ${spec.rows.length}`
    );
    const parts = [
        _t("Importado de %(file)s · %(errors)s errores · %(warnings)s avisos", {
            file: payload.filename,
            errors: result.errors,
            warnings: result.warnings,
        }),
        _t("Filas escritas: %(sheets)s", { sheets: list(written) }),
    ];
    const copied = Object.keys(payload.other || {});
    if (copied.length) {
        parts.push(_t("Copiadas: %(sheets)s", { sheets: list(copied) }));
    }
    if (payload.ignored?.length) {
        parts.push(_t("Ignoradas: %(sheets)s", { sheets: list(payload.ignored) }));
    }
    const pending = result.errors || result.warnings;
    const errorsId = env.model.getters.getSheetIdByName(ERRORS_SHEET);
    env.constructionNotify(parts.join(" · "), result.errors ? "warning" : "success", {
        sticky: Boolean(pending),
        buttons:
            pending && errorsId
                ? [{ name: _t("Ir a ERRORES"), onClick: () => activateSheet(env.model, errorsId) }]
                : [],
    });
}

/**
 * Escribe en la hoja lo que entregó el servidor (un Excel o los datos de
 * Odoo): amplía las filas si no alcanzan, escribe por clave y valida.
 * Con ``logImport`` deja la importación en el historial y el estado de la hoja.
 */
export async function applyImport(env, payload, { logImport = true } = {}) {
    const model = env.model;
    const getters = model.getters;
    // M113-08 punto 4: ARBOL se vuelve a agrupar por piso; antes se quitan
    // las filas de resumen para que los datos queden seguidos.
    const tree = Boolean(payload.sheets[TREE_SHEET]);
    if (tree) {
        clearFloorGroups(model);
    }
    const keys = keyColumns(model);
    // Filas que necesita cada pestaña (M113-05).
    let needed = 0;
    for (const [name, spec] of Object.entries(payload.sheets)) {
        const sheetId = getters.getSheetIdByName(name);
        const base = payload.mode === "append" && sheetId ? lastDataRow(getters, sheetId) : 0;
        needed = Math.max(needed, base + spec.rows.length);
    }
    if (payload.expand_rows) {
        await ensureCapacity(env, needed);
    }
    for (const [name, spec] of Object.entries(payload.sheets)) {
        writeSheet(model, name, spec, payload, keys);
    }
    for (const [name, rows] of Object.entries(payload.other || {})) {
        const sheetId = ensureSheet(model, name);
        if (payload.mode === "replace") {
            clearData(model, sheetId, 0);
        }
        ensureRows(model, sheetId, rows.length + 1);
        writeRows(model, sheetId, rows, 0);
    }
    if (tree) {
        groupTreeByFloor(model);
    }
    const sheetCount =
        Object.keys(payload.sheets).length + Object.keys(payload.other || {}).length;
    const result = await validate(env, { quiet: true });
    if (logImport) {
        await env.constructionCall(
            "construction_sheet_import_done",
            payload.filename,
            sheetCount,
            result.errors,
            result.warnings
        );
    }
    notifySummary(env, payload, result);
    return result;
}

async function importExcel(env) {
    await env.constructionDoAction(
        {
            type: "ir.actions.act_window",
            name: _t("Importar Excel a la hoja"),
            res_model: "construction.spreadsheet.import.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { default_document_id: env.constructionResId() },
        },
        {
            onClose: async (infos) => {
                const payload = infos && infos.construction_sheet_import;
                if (payload) {
                    await applyImport(env, payload);
                }
            },
        }
    );
}

// Paquete 1.13, M113-03/04: primera opción del menú del maestro.
topbarMenuRegistry.addChild("construction_furniture_import", ["construction_planner"], {
    name: _t("Importar Excel a la hoja…"),
    sequence: 110,
    isVisible: isFurniture,
    execute: (env) => importExcel(env),
});
