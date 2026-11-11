/**
 * Filas de ARBOL agrupadas por piso (paquete 1.13, M113-08 punto 4): una fila
 * de resumen encima de cada piso y sus filas en un grupo nativo que se pliega.
 *
 * La fila de resumen solo tiene texto en la columna «Resumen del piso», a la
 * derecha del maestro: el envío y las cuentas de INICIO la saltan porque no
 * tiene datos en las columnas del maestro.
 */
import {
    dispatchBatch,
    keyColumns,
    normText,
} from "@al_construction_planner_spreadsheet/send_to_planner";

export const TREE_SHEET = "ARBOL";
export const SUMMARY_HEADER = "Resumen del piso";
const FLOOR_CALC = "Piso (calc.)";
const MODULES_CALC = "Módulos (calc.)";
const ML_CALC = "ML (calc.)";

function columnLetter(index) {
    let letters = "";
    index += 1;
    while (index) {
        const rest = (index - 1) % 26;
        letters = String.fromCharCode(65 + rest) + letters;
        index = Math.floor((index - 1) / 26);
    }
    return letters;
}

/** Textos de la fila 1 de la pestaña. */
export function headerRow(model, sheetId) {
    const getters = model.getters;
    const result = [];
    for (let col = 0; col < getters.getNumberCols(sheetId); col++) {
        const value = getters.getEvaluatedCell({ sheetId, col, row: 0 }).value;
        result.push(value === null || value === undefined ? "" : String(value));
    }
    return result;
}

/** Columna con el encabezado ``text`` (sin tildes ni mayúsculas); -1 si no está. */
export function headerIndex(header, text) {
    return header.findIndex((value) => normText(value) === normText(text));
}

/**
 * Valor de una celda sin evaluar la hoja: el que la hoja le dio al escribirla.
 * Sirve con la evaluación aplazada para las columnas de dato (las fórmulas dan
 * su último valor calculado).
 */
function writtenValue(getters, position) {
    const cell = getters.getCell(position);
    if (!cell) {
        return null;
    }
    if (cell.isFormula) {
        return getters.getEvaluatedCell(position).value;
    }
    return cell.format === "@" && cell.parsedValue !== null ? cell.content : cell.parsedValue;
}

const valueReader = (getters, written) =>
    written
        ? (position) => writtenValue(getters, position)
        : (position) => getters.getEvaluatedCell(position).value;

/**
 * Valores calculados de una columna, de la fila 2 a la ``last`` (0 = la primera).
 * Con ``written``, los escritos (ver ``writtenValue``).
 */
export function columnValues(model, sheetId, col, last, written = false) {
    const read = valueReader(model.getters, written);
    const values = [];
    for (let row = 1; row <= last; row++) {
        const value = read({ sheetId, col, row });
        values.push(value === null || value === undefined ? "" : value);
    }
    return values;
}

/** Última fila (0 = la primera) con dato en las columnas ``cols``. */
export function lastRowOf(model, sheetId, cols, written = false) {
    const getters = model.getters;
    const read = valueReader(getters, written);
    for (let row = getters.getNumberRows(sheetId) - 1; row >= 1; row--) {
        for (const col of cols) {
            const value = read({ sheetId, col, row });
            if (value !== null && value !== undefined && value !== "") {
                return row;
            }
        }
    }
    return 0;
}

/** Quita las filas de resumen y los grupos de filas de ARBOL. */
export function clearFloorGroups(model) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName(TREE_SHEET);
    if (!sheetId) {
        return;
    }
    for (const group of [...getters.getHeaderGroups(sheetId, "ROW")].reverse()) {
        model.dispatch("UNGROUP_HEADERS", {
            sheetId,
            dimension: "ROW",
            start: group.start,
            end: group.end,
        });
    }
    const col = headerIndex(headerRow(model, sheetId), SUMMARY_HEADER);
    if (col < 0) {
        return;
    }
    const rows = [];
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const cell = getters.getCell({ sheetId, col, row });
        if (cell && cell.content) {
            rows.push(row);
        }
    }
    if (rows.length) {
        model.dispatch("REMOVE_COLUMNS_ROWS", {
            sheetId,
            sheetName: TREE_SHEET,
            dimension: "ROW",
            elements: rows,
        });
    }
}

/** ¿ARBOL ya está agrupado por piso? */
export function hasFloorGroups(model) {
    const sheetId = model.getters.getSheetIdByName(TREE_SHEET);
    return Boolean(sheetId) && headerIndex(headerRow(model, sheetId), SUMMARY_HEADER) >= 0;
}

/**
 * Rehace los grupos de ARBOL: un bloque por piso seguido (agrupador y piso),
 * con su fila de resumen encima. Devuelve cuántos pisos agrupó.
 *
 * Con ``written``, lee los pisos como se escribieron, sin evaluar: la
 * importación agrupa con la evaluación aplazada. Insertar las filas de resumen
 * obliga a recalcular el libro entero (unos 15 s con 1,650 filas); así ese
 * recálculo es el mismo de la ampliación y no uno más.
 */
export function groupTreeByFloor(model, { written = false } = {}) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName(TREE_SHEET);
    if (!sheetId) {
        return 0;
    }
    clearFloorGroups(model);
    const keys = keyColumns(model)[TREE_SHEET] || {};
    let header = headerRow(model, sheetId);
    const floorCol = keys.floor ?? headerIndex(header, "Piso");
    const groupCol = keys.group ?? headerIndex(header, "Agrupador");
    const spaceCol = keys.space ?? headerIndex(header, "Ambiente");
    if (floorCol < 0 || spaceCol < 0) {
        return 0;
    }
    const last = lastRowOf(model, sheetId, [floorCol, spaceCol], written);
    const floors = columnValues(model, sheetId, floorCol, last, written);
    const groups = groupCol >= 0 ? columnValues(model, sheetId, groupCol, last, written) : [];
    const floorKey = (index) => {
        const floor = String(floors[index] ?? "");
        const group = String(groups[index] ?? "");
        return floor === "" ? "" : group ? `${group} / ${floor}` : floor;
    };
    // Bloques de filas seguidas con el mismo piso (fila 0 = la primera de datos).
    const blocks = [];
    for (let index = 0; index < floors.length; index++) {
        const key = floorKey(index);
        if (!key) {
            continue;
        }
        const previous = blocks[blocks.length - 1];
        if (previous && previous.key === key && previous.end === index) {
            previous.end = index + 1;
        } else {
            blocks.push({ key, start: index + 1, end: index + 1 });
        }
    }
    if (!blocks.length) {
        return 0;
    }
    let summaryCol = headerIndex(header, SUMMARY_HEADER);
    if (summaryCol < 0) {
        summaryCol = header.reduce((lastCol, text, col) => (text ? col : lastCol), -1) + 1;
        model.dispatch("UPDATE_CELL", {
            sheetId,
            col: summaryCol,
            row: 0,
            content: SUMMARY_HEADER,
            style: { bold: true, fillColor: "#D9D9D9" },
        });
        header = headerRow(model, sheetId);
    }
    const letter = (text) => {
        const col = headerIndex(header, text);
        return col < 0 ? null : columnLetter(col);
    };
    const floorCalc = letter(FLOOR_CALC);
    const modulesCalc = letter(MODULES_CALC);
    const mlCalc = letter(ML_CALC);
    const range = (col) => `$${col}:$${col}`;
    // De abajo arriba, para que las filas de arriba no se muevan; en una sola
    // revisión de la hoja.
    const commands = [];
    for (const block of [...blocks].reverse()) {
        commands.push(["ADD_COLUMNS_ROWS", {
            sheetId,
            sheetName: TREE_SHEET,
            dimension: "ROW",
            base: block.start,
            quantity: 1,
            position: "before",
        }]);
        const label = block.key.replaceAll('"', '""');
        let content = `="${label}"`;
        if (floorCalc) {
            content =
                `="${label} · "&COUNTIF(${range(floorCalc)},"${label}")&" ambientes"` +
                (modulesCalc
                    ? `&" · "&SUMIF(${range(floorCalc)},"${label}",${range(modulesCalc)})&" módulos"`
                    : "") +
                (mlCalc
                    ? `&" · "&ROUND(SUMIF(${range(floorCalc)},"${label}",${range(mlCalc)}),2)&" ML"`
                    : "");
        }
        commands.push(["UPDATE_CELL", {
            sheetId,
            col: summaryCol,
            row: block.start,
            content,
            style: { bold: true, fillColor: "#DDE4EE" },
        }]);
        commands.push(["GROUP_HEADERS", {
            sheetId,
            dimension: "ROW",
            start: block.start + 1,
            end: block.end + 1,
        }]);
    }
    dispatchBatch(model, commands);
    return blocks.length;
}
