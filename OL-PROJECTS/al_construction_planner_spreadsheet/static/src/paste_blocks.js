/**
 * Paquete 1.18, M118-12: pegado de bloques en las pestañas de datos de las
 * hojas del planificador.
 *
 * El pegado desde el portapapeles (un bloque copiado del Excel de la
 * proyectista) se escribe aquí en un solo paso, que se deshace con un Ctrl+Z:
 * - cruza las columnas y filas fijas, que la hoja de Odoo rechaza;
 * - nunca borra una fórmula: la columna calculada se salta y el resto de la
 *   fila corre a las columnas de dato siguientes;
 * - escribe solo el contenido, así que la celda conserva su formato (el
 *   amarillo de dato).
 * La matriz de actividades conserva su propio rechazo (M119-04).
 */
import { registries, UIPlugin } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";

const { featurePluginRegistry } = registries;

const BATCH_COMMAND = "AL_CONSTRUCTION_BATCH";
// Pestañas ocultas que marcan una hoja del planificador.
const MARK_SHEETS = ["_CLAVES", "REFERENCIAS"];
// Relleno del encabezado de una columna calculada (hoja de presupuesto y
// sheet_design.py de mobiliario).
const CALC_FILLS = ["#D9D9D9", "#E6E2DD"];
// Pestañas que no son de datos.
const SKIP_SHEETS = ["INICIO", "LEEME", "ERRORES", "FICHA", "CONTROL", "PROGRAMA", "_CLAVES"];

export function parseClipboardText(text) {
    const lines = String(text || "")
        .replace(/\r?\n$/, "")
        .split(/\r?\n/);
    return lines.map((line) => line.split("\t"));
}

export function columnLetter(index) {
    let letters = "";
    let rest = index + 1;
    while (rest) {
        const mod = (rest - 1) % 26;
        letters = String.fromCharCode(65 + mod) + letters;
        rest = Math.floor((rest - 1) / 26);
    }
    return letters;
}

export class ConstructionPastePlugin extends UIPlugin {
    isPlannerSheet(sheetId) {
        const getters = this.getters;
        if (!MARK_SHEETS.some((name) => getters.getSheetIdByName(name))) {
            return false;
        }
        const name = getters.getSheetName(sheetId);
        if (SKIP_SHEETS.includes(name) || name.startsWith("ACT ")) {
            return false;
        }
        return true;
    }

    isFormulaColumn(sheetId, col) {
        // La columna calculada lleva el encabezado gris (o «(calc.)»): una
        // columna de dato con una fórmula ocasional (la unidad del APU) se
        // puede pisar, como hoy.
        const key = `${sheetId}:${col}`;
        if (!(key in this.calcColumns)) {
            const position = { sheetId, col, row: 0 };
            const header = String(this.getters.getEvaluatedCell(position).value || "");
            const fill = (this.getters.getCellStyle(position).fillColor || "").toUpperCase();
            this.calcColumns[key] = header.includes("(calc") || CALC_FILLS.includes(fill);
        }
        return this.calcColumns[key];
    }

    /** Comandos del pegado y las columnas usadas. */
    pasteCommands(sheetId, zone, grid) {
        const numberOfCols = this.getters.getNumberCols(sheetId);
        const commands = [];
        const used = new Set();
        let skipped = 0;
        grid.forEach((values, offset) => {
            const row = zone.top + offset;
            let col = zone.left;
            for (const value of values) {
                while (col < numberOfCols && this.isFormulaColumn(sheetId, col)) {
                    col++;
                    skipped++;
                }
                if (col >= numberOfCols) {
                    break;
                }
                commands.push(["UPDATE_CELL", { sheetId, col, row, content: value }]);
                used.add(col);
                col++;
            }
        });
        return { commands, used, skipped };
    }

    allowDispatch(cmd) {
        if (cmd.type !== "PASTE_FROM_OS_CLIPBOARD" || this.writing) {
            return "Success";
        }
        const sheetId = this.getters.getActiveSheetId();
        const zones = cmd.target || [];
        const text = cmd.clipboardContent?.text;
        if (zones.length !== 1 || !text || !this.isPlannerSheet(sheetId)) {
            return "Success";
        }
        this.calcColumns = {};
        const grid = parseClipboardText(text);
        const { commands, used, skipped } = this.pasteCommands(sheetId, zones[0], grid);
        if (!commands.length) {
            return "Success";
        }
        const cols = [...used].sort((a, b) => a - b);
        // Después de esta llamada: un solo paso en el historial.
        Promise.resolve().then(() => {
            this.writing = true;
            try {
                this.dispatch(BATCH_COMMAND, { commands });
            } finally {
                this.writing = false;
            }
            this.ui.notifyUI({
                type: "info",
                sticky: false,
                text:
                    _t("Pegado: %(rows)s filas en %(from)s–%(to)s", {
                        rows: grid.length,
                        from: columnLetter(cols[0]),
                        to: columnLetter(cols[cols.length - 1]),
                    }) +
                    (skipped
                        ? " · " + _t("se saltaron las columnas calculadas")
                        : ""),
            });
        });
        return "ConstructionPasteHandled";
    }
}
featurePluginRegistry.add("al_construction_paste_blocks", ConstructionPastePlugin);
