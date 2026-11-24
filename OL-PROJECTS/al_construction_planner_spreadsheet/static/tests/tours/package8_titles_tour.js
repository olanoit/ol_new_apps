import { registry } from "@web/core/registry";

/**
 * CREVAL 8, CR-69: la hoja de planificación de obra nace con los títulos de la
 * venta en PRESUPUESTO, cada uno antes de sus partidas; INICIO los cuenta
 * aparte y PLAN solo lleva partidas.
 */
function findModel(node) {
    if (node.component?.model?.getters?.getSheetIdByName) {
        return node.component.model;
    }
    for (const child of Object.values(node.children || {})) {
        const model = findModel(child);
        if (model) {
            return model;
        }
    }
    return null;
}

function cell(sheetName, col, row) {
    const model = findModel(odoo.__WOWL_DEBUG__.root.__owl__);
    const sheetId = model.getters.getSheetIdByName(sheetName);
    return model.getters.getEvaluatedCell({ sheetId, col, row }).value;
}

function expect(sheetName, col, row, expected) {
    const value = cell(sheetName, col, row);
    if (value !== expected) {
        throw new Error(`${sheetName} (${col}, ${row}): ${JSON.stringify(value)}`);
    }
}

registry.category("web_tour.tours").add("al_construction_package8_titles", {
    steps: () => [
        {
            content: "Abrir la hoja de planificación de la obra",
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [sheet] = await env.services.orm.searchRead(
                    "documents.document",
                    [["name", "=", "Planificación de obra (títulos, test paquete 8)"]],
                    ["id"],
                    { limit: 1 }
                );
                await env.services.action.doAction({
                    type: "ir.actions.client",
                    tag: "action_open_spreadsheet",
                    params: { spreadsheet_id: sheet.id },
                });
            },
        },
        { trigger: ".o-sheet-list .o-sheet:contains('PRESUPUESTO')" },
        {
            content: "PRESUPUESTO: el título antes de sus partidas, sin unidad",
            trigger: ".o-sheet-list .o-sheet:contains('PLAN')",
            run: () => {
                expect("PRESUPUESTO", 0, 1, "01");
                expect("PRESUPUESTO", 1, 1, "Arquitectura");
                expect("PRESUPUESTO", 0, 2, "01.01");
                expect("PRESUPUESTO", 0, 3, "01.02");
                const unit = cell("PRESUPUESTO", 3, 1);
                if (unit) {
                    throw new Error(`El título lleva unidad: ${unit}`);
                }
            },
        },
        {
            content: "INICIO: dos partidas y un título, contados aparte",
            trigger: ".o-sheet-list .o-sheet:contains('INICIO')",
            run: () => {
                expect("INICIO", 0, 16, "Partidas");
                expect("INICIO", 1, 16, 2);
                expect("INICIO", 0, 20, "Títulos");
                expect("INICIO", 1, 20, 1);
            },
        },
        {
            content: "PLAN: solo partidas",
            trigger: ".o-sheet-list .o-sheet:contains('PLAN')",
            run: () => {
                expect("PLAN", 0, 1, "01.01");
                expect("PLAN", 0, 2, "01.02");
                const next = cell("PLAN", 0, 3);
                if (next) {
                    throw new Error(`PLAN A4: ${next}`);
                }
            },
        },
    ],
});
