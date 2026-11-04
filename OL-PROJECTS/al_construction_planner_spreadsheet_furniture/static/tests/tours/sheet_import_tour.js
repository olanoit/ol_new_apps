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

const sheetModel = () => findModel(odoo.__WOWL_DEBUG__.root.__owl__);

/** Paquete 1.17, M117-04: la lista de Familia cubre las filas de TIPOLOGIAS. */
function checkFamilyList() {
    const getters = sheetModel().getters;
    const sheetId = getters.getSheetIdByName("TIPOLOGIAS");
    const family = getters
        .getDataValidationRules(sheetId)
        .filter((rule) => rule.criterion.values?.includes("Cocina"));
    if (!family.length || !family.every((rule) => rule.isBlocking)) {
        throw new Error("TIPOLOGIAS perdió la lista de Familia o no rechaza el valor inválido");
    }
    const row = 8; // Una fila sin dato del archivo: DELETE_CONTENT se la quitaba.
    const covered = family.some((rule) =>
        rule.ranges.some((range) => range.zone.top <= row && range.zone.bottom >= row)
    );
    if (!covered) {
        throw new Error("La lista de Familia no cubre las filas vacías");
    }
}

const cellContent = (sheet, col, row) => {
    const getters = sheetModel().getters;
    const sheetId = getters.getSheetIdByName(sheet);
    return getters.getCell({ sheetId, col, row })?.content || "";
};

/**
 * Paquete 1.16, bloque 4b (M113-04/05): «Importar Excel a la hoja» sube un
 * libro, revisa, importa y la hoja escribe el archivo ampliando sus filas.
 */
registry.category("web_tour.tours").add("al_construction_furniture_sheet_import", {
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
        {
            trigger: ".o-topbar-menu:contains('Planificación de obra')",
            run: "click",
        },
        {
            trigger: ".o-menu-item[data-name='construction_furniture_import']",
            run: "click",
        },
        {
            content: "Subir el libro",
            trigger: ".modal .o_field_binary input[type=file]:not(:visible)",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [attachment] = await env.services.orm.searchRead(
                    "ir.attachment",
                    [["name", "=", "al_sheet_import_tour.xlsx"]],
                    ["datas"],
                    { limit: 1 }
                );
                const bytes = Uint8Array.from(atob(attachment.datas), (c) => c.charCodeAt(0));
                const file = new File([bytes], "carga_tour.xlsx", {
                    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                });
                const input = document.querySelector(".modal .o_field_binary input[type=file]");
                const transfer = new DataTransfer();
                transfer.items.add(file);
                input.files = transfer.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Revisión del archivo",
            trigger: ".modal td:contains('ARBOL')",
        },
        {
            trigger: ".modal button[name='action_import']",
            run: "click",
        },
        {
            content: "La hoja escribió el archivo y validó",
            trigger: ".o_notification:contains('Importado de carga_tour.xlsx')",
            timeout: 60000,
        },
        {
            content: "El servidor recibió lo escrito en la hoja",
            trigger: "body",
            run: async () => {
                const orm = odoo.__WOWL_DEBUG__.root.env.services.orm;
                for (let attempt = 0; attempt < 40; attempt++) {
                    const count = await orm.searchCount("spreadsheet.revision", [
                        ["res_model", "=", "documents.document"],
                        ["commands", "ilike", "Dpto 14"],
                    ]);
                    if (count) {
                        return;
                    }
                    await new Promise((resolve) => setTimeout(resolve, 250));
                }
                throw new Error("La hoja no guardó las filas importadas");
            },
        },
        {
            content: "M117-03: las pestañas de la plantilla conservan sus fórmulas",
            trigger: "body",
            run: () => {
                checkFamilyList();
                if (cellContent("INICIO", 0, 0) === "OBRA DE OTRA HOJA") {
                    throw new Error("La importación escribió en INICIO");
                }
                if (cellContent("_LISTAS", 0, 0) === "LISTA DE OTRA HOJA") {
                    throw new Error("La importación escribió en _LISTAS");
                }
                if (!sheetModel().getters.getSheetIdByName("FUENTES")) {
                    throw new Error("La pestaña FUENTES no se copió");
                }
            },
        },
        {
            content: "M117-03: restaurar la versión anterior",
            trigger: ".o-topbar-menu:contains('Planificación de obra')",
            run: "click",
        },
        {
            trigger: ".o-menu-item[data-name='construction_furniture_restore']",
            run: "click",
        },
        {
            trigger: ".modal td:contains('Antes de importar carga_tour.xlsx')",
        },
        {
            trigger: ".modal .o_construction_restore_pick:first",
            run: "click",
        },
        {
            content: "Vista previa por pestaña",
            trigger: ".modal .o_construction_restore_preview td:contains('ARBOL')",
        },
        {
            trigger: ".modal .o_construction_restore_confirm",
            run: "click",
        },
        {
            trigger: ".o_notification:contains('Importado de la versión')",
            timeout: 60000,
        },
        {
            content: "La hoja volvió a como estaba y conserva sus listas",
            trigger: "body",
            run: () => {
                const getters = sheetModel().getters;
                const sheetId = getters.getSheetIdByName("ARBOL");
                for (let row = 1; row < 20; row++) {
                    for (let col = 0; col < 6; col++) {
                        const content = getters.getCell({ sheetId, col, row })?.content;
                        if (content && !content.startsWith("=")) {
                            throw new Error(`ARBOL sigue con datos: ${content}`);
                        }
                    }
                }
                checkFamilyList();
            },
        },
    ],
});

/**
 * Paquete 1.17, M117-06: abrir la hoja después de un envío compara CONTROL con
 * el planificador, sin error y sin ninguna acción del analista.
 */
registry.category("web_tour.tours").add("al_construction_furniture_control_pending", {
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
        {
            trigger: ".o-topbar-menu:contains('Planificación de obra')",
        },
        {
            content: "El servidor recibió el resultado de CONTROL",
            trigger: "body",
            run: async () => {
                const orm = odoo.__WOWL_DEBUG__.root.env.services.orm;
                for (let attempt = 0; attempt < 40; attempt++) {
                    const count = await orm.searchCount("documents.document", [
                        ["construction_sheet_kind", "=", "furniture"],
                        ["construction_control_date", "!=", false],
                    ]);
                    if (count) {
                        return;
                    }
                    await new Promise((resolve) => setTimeout(resolve, 250));
                }
                throw new Error("CONTROL no se actualizó al abrir la hoja");
            },
        },
    ],
});
