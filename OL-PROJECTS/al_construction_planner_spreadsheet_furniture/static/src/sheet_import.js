import { helpers, registries } from "@odoo/o-spreadsheet";
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
    resumeEvaluation,
    validate,
    writeRows,
} from "@al_construction_planner_spreadsheet/send_to_planner";
import { columnsOf, ensureRows } from "@al_construction_planner_spreadsheet/bring_preview";
// Viven en la base (vista previa común de «Traer la venta», CREVAL paquete 5).
export { columnsOf, ensureRows };
import { TREE_SHEET, clearFloorGroups, groupTreeByFloor } from "./floor_groups";
import { writeActivitiesToMatrix } from "./activity_matrix";
import { CancelledError, openProgress } from "./sheet_progress";

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

/**
 * Amplía el maestro con las fórmulas, listas y marcas de la plantilla para
 * las filas nuevas (M113-05), y los rangos de RESUMEN.
 */
async function applyExtension(env, extension, runner) {
    const model = env.model;
    const getters = model.getters;
    const parts = Object.entries(extension.sheets || {}).filter(([name]) =>
        getters.getSheetIdByName(name)
    );
    try {
        // M117-08: todas las filas en un lote. La hoja se evalúa una sola vez,
        // al cerrar la ampliación (unos 16 s con 1,650 filas): evaluar las
        // fórmulas mientras se escriben costaba unos 30 s más.
        dispatchBatch(model, rowCommands(getters, parts), { deferEvaluation: true });
        const commands = extensionCommands(getters, parts, extension);
        runner.progress.total += commands.length;
        await runner.write(model, _t("Ampliando la hoja"), commands, {
            locked: true,
            deferEvaluation: true,
        });
    } finally {
        resumeEvaluation(model, extensionTail(getters, parts, extension));
    }
}

/** Filas que faltan en cada pestaña. */
function rowCommands(getters, parts) {
    return parts
        .map(([name, part]) => [getters.getSheetIdByName(name), part.row_number])
        .filter(([sheetId, rows]) => getters.getNumberRows(sheetId) < rows)
        .map(([sheetId, rows]) => {
            const current = getters.getNumberRows(sheetId);
            return [
                "ADD_COLUMNS_ROWS",
                {
                    sheetId,
                    sheetName: getters.getSheetName(sheetId),
                    dimension: "ROW",
                    base: current - 1,
                    quantity: rows - current,
                    position: "after",
                },
            ];
        });
}

/** Fórmulas, listas, formato y formato condicional de las filas nuevas. */
function extensionCommands(getters, parts, extension) {
    const commands = [];
    for (const [name, part] of parts) {
        const sheetId = getters.getSheetIdByName(name);
        for (const [ref, content] of Object.entries(part.cells)) {
            commands.push(["UPDATE_CELL", { sheetId, ...parseRef(ref), content }]);
        }
        // M117-01 y M117-23: el mismo relleno y formato de la plantilla.
        for (const item of part.formatting || []) {
            commands.push([
                "SET_FORMATTING",
                {
                    sheetId,
                    target: [item.zone],
                    style: item.style,
                    ...(item.format ? { format: item.format } : {}),
                },
            ]);
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
        // La hoja de Odoo 19 exige los rangos con su pestaña y rechaza el comando
        // sin aviso si llegan como texto (M117-05); el lote avisa del rechazo.
        for (const cf of part.conditional) {
            commands.push([
                "ADD_CONDITIONAL_FORMAT",
                {
                    sheetId,
                    cf: { id: cf.id, rule: cf.rule, stopIfTrue: cf.stopIfTrue },
                    ranges: cf.ranges.map((xc) =>
                        getters.getRangeDataFromZone(sheetId, helpers.toZone(xc))
                    ),
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
    return commands;
}

/**
 * Tablas y tablas dinámicas que crecen con las filas, para el lote que cierra
 * la ampliación. UPDATE_TABLE quita las celdas combinadas de su rango y con eso
 * la hoja recalcula el libro entero, como al cambiar una tabla dinámica: todo
 * va junto, un recálculo. Una tabla que ya creció al escribir justo debajo de
 * ella no se toca.
 */
function extensionTail(getters, parts, extension) {
    const tables = [];
    for (const [name, part] of parts) {
        const sheetId = getters.getSheetIdByName(name);
        const table = part.table_bottom !== undefined && getters.getCoreTables(sheetId)[0];
        if (table && table.range.zone.bottom < part.table_bottom) {
            const zone = table.range.zone;
            tables.push([
                "UPDATE_TABLE",
                {
                    sheetId,
                    zone,
                    newTableRange: getters.getRangeDataFromZone(sheetId, {
                        ...zone,
                        bottom: part.table_bottom,
                    }),
                },
            ]);
        }
    }
    const pivots = [];
    for (const [pivotId, bottom] of Object.entries(extension.pivots || {})) {
        try {
            const definition = getters.getPivotCoreDefinition(pivotId);
            if (definition?.dataSet?.zone) {
                pivots.push([
                    "UPDATE_PIVOT",
                    {
                        pivotId,
                        pivot: {
                            ...definition,
                            dataSet: {
                                ...definition.dataSet,
                                zone: { ...definition.dataSet.zone, bottom },
                            },
                        },
                    },
                ]);
            }
        } catch {
            // Una tabla dinámica borrada por el usuario: nada que ampliar.
        }
    }
    return [...tables, ...pivots];
}

/** M117-15: el valor y el motivo de cada parámetro, por su clave (columna G). */
function writeParameters(model, parameters) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName("PARAMETROS");
    if (!sheetId || !parameters) {
        return;
    }
    const commands = [];
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const key = getters.getCell({ sheetId, col: 6, row })?.content;
        if (key && parameters[key]) {
            const [value, reason] = parameters[key];
            commands.push(["UPDATE_CELL", { sheetId, col: 2, row, content: value ?? "" }]);
            commands.push(["UPDATE_CELL", { sheetId, col: 7, row, content: reason ?? "" }]);
        }
    }
    dispatchBatch(model, commands);
}

/** M117-16: los datos de OBRA de la hoja de venta, por su nombre. */
function writeObra(model, obra) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName("OBRA");
    if (!sheetId || !obra || !Object.keys(obra).length) {
        return;
    }
    const commands = [];
    for (let row = 1; row < 40; row++) {
        const name = getters.getCell({ sheetId, col: 0, row })?.content;
        if (name && obra[name] !== undefined) {
            commands.push(["UPDATE_CELL", { sheetId, col: 1, row, content: obra[name] }]);
        }
    }
    dispatchBatch(model, commands);
}

/** Columna de cada clave: _CLAVES o el encabezado; sin las de fórmula. */

async function writeSheet(model, name, spec, payload, keys, runner) {
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
    await runner.write(model, name, commands);
    return start + spec.rows.length;
}

/**
 * Amplía el maestro si sus filas con fórmulas y listas no alcanzan para
 * ``needed`` filas de datos (M113-05): las del pedido más un 10 %. Las hojas
 * anteriores al paquete 1.16 no se amplían y lo avisan.
 */
export async function ensureCapacity(env, needed, runner = null) {
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
    if (extension && extension.needs_upgrade) {
        env.constructionNotify(
            _t(
                "Antes de ampliar esta hoja, actualícela con Planificación de obra › Actualizar a la plantilla vigente."
            ),
            "warning"
        );
        return false;
    }
    if (extension && extension.rows) {
        const own = runner || openProgress(env, 0);
        try {
            await applyExtension(env, extension, own);
        } finally {
            if (!runner) {
                own.finish();
            }
        }
        env.constructionSetSheetRows(extension.rows);
    }
    return true;
}

// Lo pone «Restaurar versión»: volver a la versión guardada antes de empezar. Es
// inyectado: restaurar usa applyImport, y un módulo no puede importar al otro.
let cancelHandler = async () => {};
export function setCancelHandler(handler) {
    cancelHandler = handler;
}

/**
 * M117-08: una acción masiva que ya guardó su versión. Escribe con el avance a la
 * vista; devuelve ``false`` si el usuario canceló y la hoja volvió a esa versión.
 */
export async function writeWithProgress(env, label, commands) {
    const runner = openProgress(env, commands.length);
    try {
        await runner.write(env.model, label, commands);
    } catch (error) {
        if (!(error instanceof CancelledError)) {
            throw error;
        }
        runner.finish();
        await cancelHandler(env);
        return false;
    }
    runner.finish();
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
    // Corrección 4 del 1.19: con la matriz, ACTIVIDADES se escribe en ella.
    const activitySpec = payload.matrix && payload.sheets.ACTIVIDADES;
    if (activitySpec) {
        delete payload.sheets.ACTIVIDADES;
    }
    // Filas que necesita cada pestaña (M113-05).
    let needed = 0;
    for (const [name, spec] of Object.entries(payload.sheets)) {
        const sheetId = getters.getSheetIdByName(name);
        const base = payload.mode === "append" && sheetId ? lastDataRow(getters, sheetId) : 0;
        needed = Math.max(needed, base + spec.rows.length);
    }
    // M117-08: por tramos, con el avance a la vista; se puede cancelar.
    const total = Object.values(payload.sheets).reduce(
        (sum, spec) => sum + spec.rows.length * spec.keys.length,
        0
    );
    const runner = openProgress(env, total);
    try {
        if (payload.expand_rows) {
            await ensureCapacity(env, needed, runner);
        }
        for (const [name, spec] of Object.entries(payload.sheets)) {
            await writeSheet(model, name, spec, payload, keys, runner);
        }
    } catch (error) {
        runner.finish();
        if (!(error instanceof CancelledError)) {
            throw error;
        }
        await cancelHandler(env);
        return { errors: 0, warnings: 0, cancelled: true };
    }
    runner.finish();
    for (const [name, rows] of Object.entries(payload.other || {})) {
        const sheetId = ensureSheet(model, name);
        if (payload.mode === "replace") {
            clearData(model, sheetId, 0);
        }
        ensureRows(model, sheetId, rows.length + 1);
        writeRows(model, sheetId, rows, 0);
    }
    let matrixWarnings = [];
    if (activitySpec) {
        // TIPOLOGIAS ya está escrita: la matriz sabe en qué fila va cada una.
        const { commands, warnings } = writeActivitiesToMatrix(
            model,
            activitySpec,
            payload.matrix.stage_tab || {}
        );
        dispatchBatch(model, commands);
        matrixWarnings = warnings;
        payload.sheets.ACTIVIDADES = activitySpec;
    }
    writeParameters(model, payload.parameters);
    writeObra(model, payload.obra);
    if (tree) {
        groupTreeByFloor(model);
    }
    const sheetCount =
        Object.keys(payload.sheets).length + Object.keys(payload.other || {}).length;
    const result = await validate(env, { quiet: true });
    if (matrixWarnings.length) {
        appendErrors(model, matrixWarnings);
        result.warnings += matrixWarnings.length;
    }
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

/** Agrega avisos al final de ERRORES (hoja, fila, columna, mensaje, «Aviso»). */
function appendErrors(model, rows) {
    const sheetId = ensureSheet(model, ERRORS_SHEET);
    const start = Math.max(2, lastDataRow(model.getters, sheetId) + 1);
    writeRows(
        model,
        sheetId,
        rows.map(([sheet, row, column, message]) => [sheet, row, column, message, _t("Aviso")]),
        start
    );
}

export async function importExcel(env) {
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
