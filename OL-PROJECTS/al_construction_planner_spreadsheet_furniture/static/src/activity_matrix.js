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
export const CODE_ROW = 1;
export const KIND_ROW = 2;
export const FIRST_ROW = 6;
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

/**
 * Corrección 4 del 1.19: las filas de ACTIVIDADES de un Excel importado se escriben en
 * la matriz (la fila de su tipología y la columna de su actividad, o una columna libre
 * de la pestaña de su etapa), con la regla de «Actualizar a la plantilla vigente».
 * Las actividades por ML o por módulo se calculan y no se escriben.
 *
 * @param spec {keys, rows} de la pestaña ACTIVIDADES del archivo.
 * @param stageTab {código: pestaña de la matriz de su etapa}.
 * @returns [[pestaña, fila, columna, mensaje]] de lo que no se pudo ubicar.
 */
export function writeActivitiesToMatrix(model, spec, stageTab) {
    const getters = model.getters;
    const at = (key) => spec.keys.indexOf(key);
    const [iTyp, iAct, iQty] = [at("typology"), at("activity"), at("qty")];
    const sheets = getters.getSheetIds().filter((sheetId) => isMatrixSheet(getters, sheetId));
    const info = sheets.map((sheetId) => {
        const name = getters.getSheetName(sheetId);
        const { right, bottom } = getters.getSheetZone(sheetId);
        const codes = {};
        const spares = [];
        for (let col = 1; col <= right; col++) {
            const codeCell = getters.getCell({ sheetId, col, row: CODE_ROW });
            const code = getters.getEvaluatedCell({ sheetId, col, row: CODE_ROW }).value;
            if (codeCell?.content?.startsWith("=")) {
                if (code) {
                    codes[code] = col;
                } else {
                    spares.push(col);
                }
            } else if (code) {
                codes[code] = col;
            }
        }
        const rows = {};
        for (let row = FIRST_ROW; row <= bottom; row++) {
            const typology = getters.getEvaluatedCell({ sheetId, col: 0, row }).value;
            if (typology && rows[typology] === undefined) {
                rows[typology] = row;
            }
        }
        return { sheetId, name, codes, spares, rows };
    });
    const commands = [];
    const warnings = [];
    for (const values of spec.rows || []) {
        const typology = String(values[iTyp] ?? "").trim();
        const code = String(values[iAct] ?? "").trim();
        const qty = values[iQty];
        if (!typology || !code || qty === "" || qty === null || qty === undefined) {
            continue;
        }
        let target = info.find((item) => item.codes[code] !== undefined);
        if (!target) {
            target = info.find((item) => item.name === stageTab[code]);
            if (!target || !target.spares.length) {
                warnings.push([
                    target ? target.name : "ACTIVIDADES",
                    "",
                    code,
                    target
                        ? _t("%(typology)s · %(code)s: no queda columna libre en %(sheet)s.", {
                              typology,
                              code,
                              sheet: target.name,
                          })
                        : _t("%(typology)s · %(code)s: la actividad no es de una etapa de la matriz.", {
                              typology,
                              code,
                          }),
                ]);
                continue;
            }
            const col = target.spares.shift();
            target.codes[code] = col;
            commands.push(["UPDATE_CELL", { sheetId: target.sheetId, col, row: 0, content: code }]);
        }
        const col = target.codes[code];
        const kind = getters.getEvaluatedCell({ sheetId: target.sheetId, col, row: KIND_ROW }).value;
        if (kind === "ml" || kind === "module") {
            continue;
        }
        const row = target.rows[typology];
        if (row === undefined) {
            warnings.push([
                target.name,
                "",
                code,
                _t("%(typology)s no está en TIPOLOGIAS: la cantidad de %(code)s no se escribió.", {
                    typology,
                    code,
                }),
            ]);
            continue;
        }
        commands.push([
            "UPDATE_CELL",
            { sheetId: target.sheetId, col, row, content: String(qty) },
        ]);
    }
    return { commands, warnings };
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
