/**
 * Paquete 1.18, M118-13: «Copiar tipología» en la hoja de planificación.
 *
 * Copia las filas de la tipología de origen en MUEBLES, MODULOS, PIEZAS y BOM
 * (con el código de la de destino) y, en las pestañas de la matriz, las
 * celdas escritas de su fila; las grises se calculan solas. Si el destino ya
 * tiene filas, se reemplazan o se agregan. Antes guarda una versión.
 */
import { Component, useState, xml } from "@odoo/owl";
import { registries } from "@odoo/o-spreadsheet";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { dispatchBatch } from "@al_construction_planner_spreadsheet/send_to_planner";

const { topbarMenuRegistry } = registries;

const ROW_TABS = ["MUEBLES", "MODULOS", "PIEZAS", "BOM"];
const MATRIX_PREFIX = "ACT ";
const MATRIX_FIRST_ROW = 6; // fila 7 de la hoja (activity_matrix.FIRST_ROW)
const TYPOLOGY_HEADER = "Tipología";

const isFurniture = (env) =>
    env.constructionSheetKind && env.constructionSheetKind() === "furniture";

function typologyColumn(getters, sheetId) {
    const cols = getters.getNumberCols(sheetId);
    for (let col = 0; col < cols; col++) {
        const header = getters.getEvaluatedCell({ sheetId, col, row: 0 }).value;
        if (String(header || "").trim() === TYPOLOGY_HEADER) {
            return col;
        }
    }
    return -1;
}

/** Filas (índices) de cada tipología en una pestaña de filas. */
function rowsByTypology(getters, sheetId, col) {
    const result = {};
    let last = 0;
    const rows = getters.getNumberRows(sheetId);
    for (let row = 1; row < rows; row++) {
        const value = getters.getCell({ sheetId, col, row })?.content ?? "";
        if (value === "") {
            continue;
        }
        last = row;
        (result[value] = result[value] || []).push(row);
    }
    return { rows: result, last };
}

function typologyCodes(getters) {
    const sheetId = getters.getSheetIdByName("TIPOLOGIAS");
    if (!sheetId) {
        return [];
    }
    const codes = [];
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        const code = getters.getCell({ sheetId, col: 0, row })?.content ?? "";
        if (code !== "" && !codes.includes(code)) {
            codes.push(code);
        }
    }
    return codes;
}

function matrixSheets(getters) {
    return getters
        .getSheetIds()
        .filter((sheetId) => getters.getSheetName(sheetId).startsWith(MATRIX_PREFIX));
}

function matrixRow(getters, sheetId, code) {
    for (let row = MATRIX_FIRST_ROW; row < getters.getNumberRows(sheetId); row++) {
        if (getters.getEvaluatedCell({ sheetId, col: 0, row }).value === code) {
            return row;
        }
    }
    return -1;
}

/** Comandos de la copia, por pestaña. */
export function copyTypologyCommands(getters, { source, target, tabs, replace }) {
    const commands = [];
    const counts = {};
    for (const name of ROW_TABS.filter((tab) => tabs.includes(tab))) {
        const sheetId = getters.getSheetIdByName(name);
        const typologyCol = sheetId ? typologyColumn(getters, sheetId) : -1;
        if (typologyCol < 0) {
            continue;
        }
        const cols = getters.getNumberCols(sheetId);
        const { rows, last } = rowsByTypology(getters, sheetId, typologyCol);
        const origin = rows[source] || [];
        const existing = rows[target] || [];
        let free = last + 1;
        const destination = [];
        if (replace) {
            // Se reutilizan las filas del destino; las que sobran se vacían.
            destination.push(...existing.slice(0, origin.length));
            for (const row of existing.slice(origin.length)) {
                for (let col = 0; col < cols; col++) {
                    const cell = getters.getCell({ sheetId, col, row });
                    if (cell && !cell.isFormula && cell.content !== "") {
                        commands.push(["UPDATE_CELL", { sheetId, col, row, content: "" }]);
                    }
                }
            }
        }
        while (destination.length < origin.length) {
            destination.push(free++);
        }
        origin.forEach((from, index) => {
            const row = destination[index];
            for (let col = 0; col < cols; col++) {
                const cell = getters.getCell({ sheetId, col, row: from });
                if (cell?.isFormula) {
                    continue;
                }
                const content = col === typologyCol ? target : cell?.content ?? "";
                const current = getters.getCell({ sheetId, col, row });
                if (current?.isFormula) {
                    continue;
                }
                if (content !== "" || (current && current.content !== "")) {
                    commands.push(["UPDATE_CELL", { sheetId, col, row, content }]);
                }
            }
        });
        counts[name] = origin.length;
    }
    if (tabs.includes("MATRIZ")) {
        for (const sheetId of matrixSheets(getters)) {
            const from = matrixRow(getters, sheetId, source);
            const to = matrixRow(getters, sheetId, target);
            if (from < 0 || to < 0) {
                continue;
            }
            let written = 0;
            for (let col = 1; col < getters.getNumberCols(sheetId); col++) {
                const cell = getters.getCell({ sheetId, col, row: from });
                const current = getters.getCell({ sheetId, col, row: to });
                if (cell?.isFormula || current?.isFormula) {
                    continue;
                }
                const content = cell?.content ?? "";
                if (content !== "" || (replace && current && current.content !== "")) {
                    commands.push(["UPDATE_CELL", { sheetId, col, row: to, content }]);
                    written += content !== "" ? 1 : 0;
                }
            }
            counts[getters.getSheetName(sheetId)] = written;
        }
    }
    return { commands, counts };
}

class CopyPlanningTypologyDialog extends Component {
    static components = { Dialog };
    static props = ["close", "codes", "existing", "copy"];
    static template = xml`
        <Dialog title="title">
            <div class="row mb-2">
                <div class="col">
                    <label class="form-label">Copiar de</label>
                    <select class="form-select o_copy_source" t-model="state.source">
                        <option t-foreach="props.codes" t-as="code" t-key="code" t-att-value="code" t-esc="code"/>
                    </select>
                </div>
                <div class="col">
                    <label class="form-label">A la tipología</label>
                    <select class="form-select o_copy_target" t-model="state.target">
                        <option t-foreach="props.codes" t-as="code" t-key="code" t-att-value="code" t-esc="code"/>
                    </select>
                </div>
            </div>
            <div class="mb-2">
                <div t-foreach="tabs" t-as="tab" t-key="tab.key" class="form-check">
                    <input class="form-check-input" type="checkbox" t-att-id="'copy_' + tab.key"
                           t-att-checked="state.tabs.includes(tab.key)" t-on-change="() => this.toggle(tab.key)"/>
                    <label class="form-check-label" t-att-for="'copy_' + tab.key" t-esc="tab.label"/>
                </div>
            </div>
            <div t-if="hasRows" class="mb-2">
                <div class="text-warning small mb-1">La tipología de destino ya tiene filas.</div>
                <div class="form-check form-check-inline">
                    <input class="form-check-input" type="radio" id="copy_replace" t-att-checked="state.replace" t-on-change="() => state.replace = true"/>
                    <label class="form-check-label" for="copy_replace">Reemplazar</label>
                </div>
                <div class="form-check form-check-inline">
                    <input class="form-check-input" type="radio" id="copy_add" t-att-checked="!state.replace" t-on-change="() => state.replace = false"/>
                    <label class="form-check-label" for="copy_add">Agregar</label>
                </div>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-primary o_copy_confirm" t-att-disabled="state.source === state.target"
                        t-on-click="confirm">Copiar</button>
                <button class="btn btn-secondary" t-on-click="props.close">Cancelar</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.title = _t("Copiar tipología");
        this.tabs = [
            ...ROW_TABS.map((key) => ({ key, label: key })),
            { key: "MATRIZ", label: _t("Pestañas de actividades (ACT …)") },
        ];
        this.state = useState({
            source: this.props.codes[0],
            target: this.props.codes[1] || this.props.codes[0],
            tabs: this.tabs.map((tab) => tab.key),
            replace: true,
        });
    }

    get hasRows() {
        return this.props.existing.includes(this.state.target);
    }

    toggle(key) {
        const index = this.state.tabs.indexOf(key);
        if (index >= 0) {
            this.state.tabs.splice(index, 1);
        } else {
            this.state.tabs.push(key);
        }
    }

    async confirm() {
        this.props.close();
        await this.props.copy({ ...this.state, tabs: [...this.state.tabs] });
    }
}

async function copyPlanningTypology(env) {
    const getters = env.model.getters;
    const codes = typologyCodes(getters);
    if (codes.length < 2) {
        env.constructionNotify(_t("TIPOLOGIAS necesita al menos dos tipologías."), "warning");
        return;
    }
    const existing = [];
    for (const name of ROW_TABS) {
        const sheetId = getters.getSheetIdByName(name);
        const col = sheetId ? typologyColumn(getters, sheetId) : -1;
        if (col >= 0) {
            existing.push(...Object.keys(rowsByTypology(getters, sheetId, col).rows));
        }
    }
    env.constructionDialog(CopyPlanningTypologyDialog, {
        codes,
        existing,
        copy: async (options) => {
            await env.constructionCall(
                "construction_version_before",
                _t("Antes de copiar %(source)s a %(target)s", options)
            );
            const { commands, counts } = copyTypologyCommands(env.model.getters, options);
            dispatchBatch(env.model, commands);
            const detail = Object.entries(counts)
                .map(([name, count]) => `${name} ${count}`)
                .join(" · ");
            env.constructionNotify(
                _t("%(source)s copiada a %(target)s: %(detail)s", { ...options, detail })
            );
        },
    });
}

topbarMenuRegistry.addChild("construction_planning_copy_typology", ["construction_planner"], {
    name: _t("Copiar tipología…"),
    sequence: 171,
    isVisible: isFurniture,
    execute: (env) => copyPlanningTypology(env),
});
