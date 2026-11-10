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
            content: "Lo cambiado a mano va desmarcado",
            trigger: ".o_construction_bring_preview tr:has(td:contains('PLAN')) button:contains('Ver filas')",
            run: "click",
        },
        {
            trigger: ".o_construction_bring_preview label:contains('01.01')",
            run: () => {
                const label = [...document.querySelectorAll(".o_construction_bring_preview label")].find(
                    (node) => node.textContent.includes("01.01")
                );
                if (label.querySelector("input").checked) {
                    throw new Error("La partida editada viene marcada");
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
    ],
});
