import { registries } from "@odoo/o-spreadsheet";
import { useSubEnv } from "@odoo/owl";
import { SpreadsheetAction } from "@documents_spreadsheet/bundle/actions/spreadsheet_action";
import { _t } from "@web/core/l10n/translation";
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

patch(SpreadsheetAction.prototype, {
    setup() {
        super.setup(...arguments);
        useSubEnv({
            isConstructionWorksheet: () => Boolean(this.data?.construction_project_id),
            sendToConstructionPlanner: this.sendToConstructionPlanner.bind(this),
        });
    },

    async sendToConstructionPlanner() {
        const action = await this.orm.call(
            "documents.document",
            "action_construction_send_to_planner",
            [[this.resId], collectSheets(this.model)]
        );
        await this.actionService.doAction(action);
    },
});

topbarMenuRegistry.addChild("construction_send_to_planner", ["file"], {
    name: _t("Enviar al planificador"),
    sequence: 25,
    isVisible: (env) => Boolean(env.isConstructionWorksheet && env.isConstructionWorksheet()),
    execute: (env) => env.sendToConstructionPlanner(),
    icon: "o-spreadsheet-Icon.ARROW_RIGHT",
});
