import { registry } from "@web/core/registry";

/**
 * CREVAL, paquete 5, CR-45, punto 2: «Traer la venta…» en la hoja de
 * planificación de obra abre la vista previa; con la huella, la partida que el
 * planificador cambió a mano queda desmarcada y no se pisa.
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

function planCell(col, row) {
    const model = findModel(odoo.__WOWL_DEBUG__.root.__owl__);
    const sheetId = model.getters.getSheetIdByName("PLAN");
    return { model, sheetId, value: model.getters.getEvaluatedCell({ sheetId, col, row }).value };
}

const bring = [
    { trigger: ".o-topbar-menu:contains('Planificación de obra')", run: "click" },
    { trigger: ".o-menu-item[data-name='construction_budget_plan_bring']", run: "click" },
    { trigger: ".o_construction_bring_preview:contains('PLAN')" },
];

registry.category("web_tour.tours").add("al_construction_plan_bring", {
    steps: () => [
        {
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [sheet] = await env.services.orm.searchRead(
                    "documents.document",
                    [["name", "=", "Planificación de obra (traer la venta, test)"]],
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
        { trigger: ".o-sheet-list .o-sheet:contains('PLAN')" },
        ...bring,
        { trigger: ".o_construction_bring_confirm", run: "click" },
        { trigger: ".o_notification:contains('Venta traída')" },
        {
            content: "PLAN tiene lo vendido; el planificador cambia el nombre de la partida",
            trigger: "body",
            run: () => {
                const { model, sheetId, value } = planCell(0, 1);
                if (value !== "01.01") {
                    throw new Error(`PLAN A2: ${value}`);
                }
                model.dispatch("UPDATE_CELL", { sheetId, col: 1, row: 1, content: "Muro del eje A (obra)" });
                if (!model.getters.getSheetIdByName("_HUELLA")) {
                    throw new Error("Falta la huella");
                }
            },
        },
        ...bring,
        {
            content: "PLAN es una tabla por partida, con metrado vendido y APU; lo cambiado a mano va desmarcado",
            trigger: ".o_construction_bring_table tr:has(td:contains('01.01')):contains('Cambia: Partida')",
            run: () => {
                const row = [...document.querySelectorAll(".o_construction_bring_table tbody tr")].find(
                    (node) => node.textContent.includes("01.01")
                );
                if (row.querySelector("input").checked) {
                    throw new Error("La partida editada viene marcada");
                }
                const cells = [...row.querySelectorAll("td")].map((td) => td.textContent.trim());
                if (!cells[3].startsWith("100") || !cells[4].includes("BK-R01")) {
                    throw new Error(`Fila de 01.01: ${JSON.stringify(cells)}`);
                }
            },
        },
        { trigger: ".o_construction_bring_confirm", run: "click" },
        { trigger: ".o_notification:contains('0 cambiadas')" },
        {
            content: "El nombre escrito por el planificador se conserva",
            trigger: "body",
            run: () => {
                const { value } = planCell(1, 1);
                if (value !== "Muro del eje A (obra)") {
                    throw new Error(`PLAN B2: ${value}`);
                }
            },
        },
        {
            content: "CR-43: elegir el producto por su nombre llena la fila de INSUMOS",
            trigger: "body",
            run: () => {
                const model = findModel(odoo.__WOWL_DEBUG__.root.__owl__);
                const sheetId = model.getters.getSheetIdByName("INSUMOS");
                const header = (col) => model.getters.getEvaluatedCell({ sheetId, col, row: 0 }).value;
                const colOf = (text) => {
                    for (let col = 0; col < model.getters.getNumberCols(sheetId); col++) {
                        if (header(col) === text) {
                            return col;
                        }
                    }
                    throw new Error(`INSUMOS sin la columna ${text}`);
                };
                const row = 60;
                model.dispatch("UPDATE_CELL", {
                    sheetId,
                    col: colOf("Producto (escriba el nombre)"),
                    row,
                    content: 'Tubo PVC SEL 3/4" (test) · BK-TUB',
                });
                const value = (text) => model.getters.getEvaluatedCell({ sheetId, col: colOf(text), row }).value;
                const got = [value("Código"), value("Tipo de insumo"), value("Precio sin IGV")];
                if (got[0] !== "BK-TUB" || got[1] !== "Material" || Number(got[2]) !== 3.5) {
                    throw new Error(`INSUMOS fila ${row + 1}: ${JSON.stringify(got)}`);
                }
            },
        },
        { trigger: ".o-topbar-menu:contains('Planificación de obra')", run: "click" },
        { trigger: ".o-menu-item[data-name='construction_budget_plan_control']", run: "click" },
        { trigger: ".o_notification:contains('CONTROL comparado con'):contains('2 partidas')" },
        {
            content: "CR-46, punto 3: CONTROL tiene el costo del plan de Odoo",
            trigger: "body",
            run: () => {
                const model = findModel(odoo.__WOWL_DEBUG__.root.__owl__);
                const sheetId = model.getters.getSheetIdByName("CONTROL");
                const cost = model.getters.getEvaluatedCell({ sheetId, col: 7, row: 2 }).value;
                if (!(Number(cost) > 0)) {
                    throw new Error(`CONTROL H3: ${cost}`);
                }
            },
        },
    ],
});
