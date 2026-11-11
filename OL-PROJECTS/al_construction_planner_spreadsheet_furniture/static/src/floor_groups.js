/**
 * Filas de ARBOL agrupadas por piso (paquete 1.13, M113-08 punto 4): una fila
 * de resumen encima de cada piso y sus filas en un grupo nativo que se pliega.
 *
 * La fila de resumen solo tiene texto en la columna «Resumen del piso», a la
 * derecha del maestro: el envío y las cuentas de INICIO la saltan porque no
 * tiene datos en las columnas del maestro.
 */
import {
    deferEvaluation,
    dispatchBatch,
    keyColumns,
    normText,
    resumeEvaluation,
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
        // Como se escribió: vale también con la evaluación aplazada.
        const value = writtenValue(getters, { sheetId, col, row: 0 });
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

/**
 * Quita los grupos de filas de ARBOL y el texto de sus filas de resumen. Una
 * fila de resumen es una fila de la plantilla (tiene sus fórmulas): queda vacía
 * y en su lugar, sin mover las demás. Las de antes eran filas insertadas sin
 * fórmulas y se borran.
 */
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
    const header = headerRow(model, sheetId);
    const col = headerIndex(header, SUMMARY_HEADER);
    if (col < 0) {
        return;
    }
    const calcCol = headerIndex(header, FLOOR_CALC);
    const commands = [];
    const remove = [];
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const cell = getters.getCell({ sheetId, col, row });
        if (!cell || !cell.content) {
            continue;
        }
        if (calcCol >= 0 && getters.getCell({ sheetId, col: calcCol, row })?.isFormula) {
            commands.push(["UPDATE_CELL", { sheetId, col, row, content: "", style: null }]);
        } else {
            remove.push(row);
        }
    }
    dispatchBatch(model, commands);
    if (remove.length) {
        model.dispatch("REMOVE_COLUMNS_ROWS", {
            sheetId,
            sheetName: TREE_SHEET,
            dimension: "ROW",
            elements: remove,
        });
    }
}

/** ¿ARBOL ya está agrupado por piso? */
export function hasFloorGroups(model) {
    const sheetId = model.getters.getSheetIdByName(TREE_SHEET);
    return Boolean(sheetId) && headerIndex(headerRow(model, sheetId), SUMMARY_HEADER) >= 0;
}

const SUMMARY_STYLE = { bold: true, fillColor: "#DDE4EE" };

/** «Piso 3 · 12 ambientes · 40 módulos · 31.5 ML», con lo que tenga la hoja. */
function summaryFormula(header, key) {
    const letter = (text) => {
        const col = headerIndex(header, text);
        return col < 0 ? null : columnLetter(col);
    };
    const floorCalc = letter(FLOOR_CALC);
    const modulesCalc = letter(MODULES_CALC);
    const mlCalc = letter(ML_CALC);
    const range = (col) => `$${col}:$${col}`;
    const label = key.replaceAll('"', '""');
    if (!floorCalc) {
        return `="${label}"`;
    }
    return (
        `="${label} · "&COUNTIF(${range(floorCalc)},"${label}")&" ambientes"` +
        (modulesCalc
            ? `&" · "&SUMIF(${range(floorCalc)},"${label}",${range(modulesCalc)})&" módulos"`
            : "") +
        (mlCalc
            ? `&" · "&ROUND(SUMIF(${range(floorCalc)},"${label}",${range(mlCalc)}),2)&" ML"`
            : "")
    );
}

/** Columnas de ARBOL que agrupan: piso, agrupador y ambiente. */
function treeColumns(model, sheetId) {
    const keys = keyColumns(model)[TREE_SHEET] || {};
    const header = headerRow(model, sheetId);
    return {
        header,
        floorCol: keys.floor ?? headerIndex(header, "Piso"),
        groupCol: keys.group ?? headerIndex(header, "Agrupador"),
        spaceCol: keys.space ?? headerIndex(header, "Ambiente"),
    };
}

/** Clave del piso de una fila: «Agrupador / Piso», el piso solo o "". */
function floorKey(floor, group) {
    floor = floor === null || floor === undefined ? "" : String(floor);
    group = group === null || group === undefined ? "" : String(group);
    return floor === "" ? "" : group ? `${group} / ${floor}` : floor;
}

/**
 * Rehace los grupos de ARBOL: un bloque por piso seguido (agrupador y piso),
 * con su fila de resumen encima. Devuelve cuántos pisos agrupó.
 *
 * No inserta filas: reacomoda las celdas escritas (sin fórmulas) de las filas con
 * datos, en orden y sin las filas vacías, dejando una fila de la plantilla libre
 * encima de cada piso para el resumen. Insertar 38 filas costaba unos 6 s (la
 * hoja ajusta todos los rangos del libro en cada una) y un recálculo completo
 * (unos 6 s); reacomodar celdas solo recalcula lo que depende de ellas. Si las
 * filas de la plantilla no alcanzan, inserta como antes.
 *
 * Con ``written``, lee los pisos como se escribieron, sin evaluar: la
 * importación agrupa con la evaluación aplazada.
 */
export function groupTreeByFloor(model, { written = false } = {}) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName(TREE_SHEET);
    if (!sheetId) {
        return 0;
    }
    clearFloorGroups(model);
    const { header, floorCol, groupCol, spaceCol } = treeColumns(model, sheetId);
    if (floorCol < 0 || spaceCol < 0) {
        return 0;
    }
    let summaryCol = headerIndex(header, SUMMARY_HEADER);
    const newSummary = summaryCol < 0;
    if (newSummary) {
        summaryCol = header.reduce((lastCol, text, col) => (text ? col : lastCol), -1) + 1;
    }
    // Celdas escritas de cada fila (las fórmulas son de la plantilla y no se mueven).
    const cellsByRow = new Map();
    const columns = new Set();
    for (const [cellId, cell] of Object.entries(getters.getCells(sheetId))) {
        if (cell.isFormula || cell.content === "") {
            continue;
        }
        const { col, row } = getters.getCellPosition(cellId);
        if (row < 1 || col === summaryCol) {
            continue;
        }
        if (!cellsByRow.has(row)) {
            cellsByRow.set(row, new Map());
        }
        cellsByRow.get(row).set(col, cell.content);
        columns.add(col);
    }
    const read = valueReader(getters, written);
    const rows = [...cellsByRow.keys()].sort((a, b) => a - b);
    // Destino de cada fila: una fila libre encima de cada bloque de un mismo piso.
    const target = new Map();
    const blocks = [];
    let next = 1;
    let previousKey = "";
    for (const row of rows) {
        const key = floorKey(
            read({ sheetId, col: floorCol, row }),
            groupCol >= 0 ? read({ sheetId, col: groupCol, row }) : ""
        );
        if (key && key !== previousKey) {
            blocks.push({ key, summary: next, start: next + 1, end: next + 1 });
            next++;
        } else if (key) {
            blocks[blocks.length - 1].end = next;
        }
        previousKey = key;
        target.set(next, cellsByRow.get(row));
        next++;
    }
    if (!blocks.length) {
        return 0;
    }
    const calcCol = headerIndex(header, FLOOR_CALC);
    const lastTarget = next - 1;
    if (
        calcCol < 0 ||
        lastTarget >= getters.getNumberRows(sheetId) ||
        !getters.getCell({ sheetId, col: calcCol, row: lastTarget })?.isFormula
    ) {
        return insertSummaryRows(model, { written });
    }
    const commands = [];
    if (newSummary) {
        commands.push(["UPDATE_CELL", {
            sheetId, col: summaryCol, row: 0, content: SUMMARY_HEADER,
            style: { bold: true, fillColor: "#D9D9D9" },
        }]);
    }
    const bottom = Math.max(lastTarget, rows[rows.length - 1]);
    for (let row = 1; row <= bottom; row++) {
        const wanted = target.get(row);
        const current = cellsByRow.get(row);
        for (const col of columns) {
            const content = wanted?.get(col) ?? "";
            if (content === (current?.get(col) ?? "")) {
                continue;
            }
            if (getters.getCell({ sheetId, col, row })?.isFormula) {
                continue;
            }
            commands.push(["UPDATE_CELL", { sheetId, col, row, content }]);
        }
    }
    for (const block of blocks) {
        commands.push(["UPDATE_CELL", {
            sheetId, col: summaryCol, row: block.summary,
            content: summaryFormula(header, block.key), style: SUMMARY_STYLE,
        }]);
        commands.push(["GROUP_HEADERS", {
            sheetId, dimension: "ROW", start: block.start, end: block.end,
        }]);
    }
    deferEvaluation(model);
    try {
        dispatchBatch(model, commands);
    } finally {
        resumeEvaluation(model);
    }
    return blocks.length;
}

/**
 * Agrupa insertando una fila sin fórmulas encima de cada piso: lo de antes, para
 * cuando las filas de la plantilla no alcanzan para los resúmenes.
 */
function insertSummaryRows(model, { written = false } = {}) {
    const getters = model.getters;
    const sheetId = getters.getSheetIdByName(TREE_SHEET);
    const { floorCol, groupCol, spaceCol } = treeColumns(model, sheetId);
    let { header } = treeColumns(model, sheetId);
    const last = lastRowOf(model, sheetId, [floorCol, spaceCol], written);
    const floors = columnValues(model, sheetId, floorCol, last, written);
    const groups = groupCol >= 0 ? columnValues(model, sheetId, groupCol, last, written) : [];
    // Bloques de filas seguidas con el mismo piso (fila 0 = la primera de datos).
    const blocks = [];
    for (let index = 0; index < floors.length; index++) {
        const key = floorKey(floors[index], groups[index]);
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
    const commands = [];
    let summaryCol = headerIndex(header, SUMMARY_HEADER);
    if (summaryCol < 0) {
        summaryCol = header.reduce((lastCol, text, col) => (text ? col : lastCol), -1) + 1;
        commands.push(["UPDATE_CELL", {
            sheetId, col: summaryCol, row: 0, content: SUMMARY_HEADER,
            style: { bold: true, fillColor: "#D9D9D9" },
        }]);
        header = [...header];
        header[summaryCol] = SUMMARY_HEADER;
    }
    // De abajo arriba, para que las filas de arriba no se muevan; en una sola
    // revisión de la hoja.
    for (const block of [...blocks].reverse()) {
        commands.push(["ADD_COLUMNS_ROWS", {
            sheetId,
            sheetName: TREE_SHEET,
            dimension: "ROW",
            base: block.start,
            quantity: 1,
            position: "before",
        }]);
        commands.push(["UPDATE_CELL", {
            sheetId, col: summaryCol, row: block.start,
            content: summaryFormula(header, block.key), style: SUMMARY_STYLE,
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
