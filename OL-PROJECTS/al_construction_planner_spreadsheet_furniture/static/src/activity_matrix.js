/**
 * Matriz de actividades por etapa (paquete 1.19, M119-04, punto 9): se puede pegar
 * un bloque de cantidades desde Excel sobre las celdas amarillas; las grises
 * (calculadas, por ML o por módulo) y las filas de arriba no reciben pegado.
 */
import { registries, UIPlugin } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";

const { featurePluginRegistry } = registries;

// Filas y marcas de models/activity_matrix.py (0 = la primera fila).
const MATRIX_CODE_LABEL = "Código (calc.)";
const CODE_ROW = 1;
const KIND_ROW = 2;
const FIRST_ROW = 6;
const WRITABLE = "data";

export function isMatrixSheet(getters, sheetId) {
    return getters.getCell({ sheetId, col: 0, row: CODE_ROW })?.content === MATRIX_CODE_LABEL;
}

/** Si la celda de la matriz se escribe a mano (amarilla). */
export function isWritableCell(getters, sheetId, col, row) {
    if (col === 0) {
        return false;
    }
    const kind = getters.getEvaluatedCell({ sheetId, col, row: KIND_ROW }).value;
    const codeContent = getters.getCell({ sheetId, col, row: CODE_ROW })?.content || "";
    const spare = codeContent.startsWith("=");
    if (row === 0) {
        // El encabezado de una columna libre: la actividad que se agrega.
        return spare;
    }
    if (row < FIRST_ROW) {
        return false;
    }
    return kind === WRITABLE || (spare && kind !== "ml" && kind !== "module");
}

function pastedSize(cmd) {
    if (cmd.type !== "PASTE_FROM_OS_CLIPBOARD") {
        return { height: 1, width: 1 };
    }
    const text = cmd.clipboardContent?.text || "";
    const lines = text.replace(/\r?\n$/, "").split(/\r?\n/);
    return {
        height: Math.max(lines.length, 1),
        width: Math.max(...lines.map((line) => line.split("\t").length), 1),
    };
}

export class ConstructionMatrixPastePlugin extends UIPlugin {
    allowDispatch(cmd) {
        if (cmd.type !== "PASTE" && cmd.type !== "PASTE_FROM_OS_CLIPBOARD") {
            return "Success";
        }
        const sheetId = this.getters.getActiveSheetId();
        if (!isMatrixSheet(this.getters, sheetId)) {
            return "Success";
        }
        const { height, width } = pastedSize(cmd);
        for (const zone of cmd.target || []) {
            const bottom = Math.max(zone.bottom, zone.top + height - 1);
            const right = Math.max(zone.right, zone.left + width - 1);
            for (let col = zone.left; col <= right; col++) {
                for (let row = zone.top; row <= bottom; row++) {
                    if (!isWritableCell(this.getters, sheetId, col, row)) {
                        this.ui.notifyUI({
                            type: "warning",
                            sticky: false,
                            text: _t(
                                "Las celdas grises de la matriz se calculan: pegue solo sobre las amarillas."
                            ),
                        });
                        return "ConstructionMatrixLocked";
                    }
                }
            }
        }
        return "Success";
    }
}
featurePluginRegistry.add("al_construction_matrix_paste", ConstructionMatrixPastePlugin);
