import { registry } from "@web/core/registry";

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

const treeRows = () => {
    const getters = findModel(odoo.__WOWL_DEBUG__.root.__owl__).getters;
    const sheetId = getters.getSheetIdByName("ARBOL");
    let count = 0;
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        if (getters.getCell({ sheetId, col: 3, row })?.content) {
            count++;
        }
    }
    return count;
};

const importSteps = () => [
    { trigger: ".o-topbar-menu:contains('Planificación de obra')", run: "click" },
    { trigger: ".o-menu-item[data-name='construction_furniture_import']", run: "click" },
    {
        trigger: ".modal .o_field_binary input[type=file]:not(:visible)",
        run: async () => {
            const env = odoo.__WOWL_DEBUG__.root.env;
            const [attachment] = await env.services.orm.searchRead(
                "ir.attachment",
                [["name", "=", "al_sheet_progress_tour.xlsx"]],
                ["datas"],
                { limit: 1 }
            );
            const bytes = Uint8Array.from(atob(attachment.datas), (c) => c.charCodeAt(0));
            const file = new File([bytes], "carga_grande.xlsx", {
                type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            });
            const input = document.querySelector(".modal .o_field_binary input[type=file]");
            const transfer = new DataTransfer();
            transfer.items.add(file);
            input.files = transfer.files;
            input.dispatchEvent(new Event("change", { bubbles: true }));
        },
    },
    { trigger: ".modal td:contains('ARBOL')", timeout: 30000 },
    {
        trigger: ".modal button[name='action_import']",
        run: (helpers) => {
            window.alImportStart = performance.now();
            helpers.click();
        },
    },
];

/** Paquete 1.17, M117-08: avance, cancelar y el tiempo de una carga de 1,500 filas. */
registry.category("web_tour.tours").add("al_construction_sheet_progress", {
    steps: () => [
        {
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [sheet] = await env.services.orm.searchRead(
                    "documents.document",
                    [["construction_sheet_kind", "=", "furniture"]],
                    ["id"],
                    { limit: 1, order: "id desc" }
                );
                await env.services.action.doAction({
                    type: "ir.actions.client",
                    tag: "action_open_spreadsheet",
                    params: { spreadsheet_id: sheet.id },
                });
            },
        },
        ...importSteps(),
        {
            content: "La ampliación ya va en el cuadro de avance",
            trigger: ".o_construction_progress_label:contains('Ampliando')",
            timeout: 60000,
        },
        {
            content: "El cuadro muestra la pestaña y las filas",
            trigger: ".o_construction_progress_label:contains('ARBOL')",
            timeout: 60000,
        },
        { trigger: ".o_construction_progress_cancel", run: "click" },
        {
            content: "Cancelar deja la hoja como estaba",
            trigger: ".o_notification:contains('Acción cancelada')",
            timeout: 60000,
        },
        {
            trigger: "body",
            timeout: 60000,
            run: () => {
                if (treeRows() !== 0) {
                    throw new Error(`ARBOL quedó con ${treeRows()} filas`);
                }
            },
        },
        ...importSteps(),
        {
            content: "Sin cancelar, todas las filas",
            trigger: ".o_notification:contains('Importado de carga_grande.xlsx')",
            timeout: 60000,
            run: () => {
                console.log(`AL_PERF importar: ${Math.round(performance.now() - window.alImportStart)} ms`);
                if (treeRows() < 1500) {
                    throw new Error(`ARBOL tiene ${treeRows()} filas`);
                }
            },
        },
        {
            content: "Una regla que se solapa sigue recortando a la anterior",
            trigger: "body",
            run: () => {
                const model = findModel(odoo.__WOWL_DEBUG__.root.__owl__);
                const getters = model.getters;
                const sheetId = getters.getSheetIdByName("ARBOL");
                const add = (id, top, bottom) =>
                    model.dispatch("ADD_DATA_VALIDATION_RULE", {
                        sheetId,
                        rule: {
                            id,
                            isBlocking: false,
                            criterion: { type: "isValueInList", values: ["a"], displayStyle: "arrow" },
                        },
                        ranges: [
                            getters.getRangeDataFromZone(sheetId, {
                                top,
                                bottom,
                                left: 25,
                                right: 25,
                            }),
                        ],
                    });
                add("al_test_uno", 1, 5);
                add("al_test_dos", 3, 3);
                const rule = getters
                    .getDataValidationRules(sheetId)
                    .find((item) => item.id === "al_test_uno");
                if (rule.ranges.some((range) => range.zone.top <= 3 && range.zone.bottom >= 3)) {
                    throw new Error("La regla anterior conserva la celda de la nueva");
                }
                model.dispatch("REMOVE_DATA_VALIDATION_RULE", { sheetId, id: "al_test_uno" });
                model.dispatch("REMOVE_DATA_VALIDATION_RULE", { sheetId, id: "al_test_dos" });
            },
        },
    ],
});
