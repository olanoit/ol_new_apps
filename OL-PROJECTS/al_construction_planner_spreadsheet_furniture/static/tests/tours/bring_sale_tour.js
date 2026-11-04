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

/** Filas con dato en la columna ``col`` de una pestaña. */
function countRows(sheet, col) {
    const getters = sheetModel().getters;
    const sheetId = getters.getSheetIdByName(sheet);
    let count = 0;
    for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
        if (getters.getCell({ sheetId, col, row })?.content) {
            count++;
        }
    }
    return count;
}

const openBring = [
    { trigger: ".o-topbar-menu:contains('Planificación de obra')", run: "click" },
    { trigger: ".o-menu-item[data-name='construction_furniture_bring_sale']", run: "click" },
];

/** Paquete 1.17, M117-22: la hoja nace con la venta, y repetir no duplica. */
registry.category("web_tour.tours").add("al_construction_bring_sale", {
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
            content: "La vista previa sale sola, con lo que no está listo",
            trigger: ".modal .o_construction_bring_preview td:contains('ARBOL')",
            timeout: 60000,
        },
        { trigger: ".modal .alert:contains('CL05 sin metrado')" },
        { trigger: ".modal .o_construction_bring_confirm", run: "click" },
        {
            trigger: ".o_notification:contains('Venta traída a la hoja')",
            timeout: 60000,
        },
        {
            content: "Las filas llegaron",
            trigger: "body",
            run: () => {
                const tree = countRows("ARBOL", 3);
                if (tree < 18) {
                    throw new Error(`ARBOL tiene ${tree} filas`);
                }
                window.alTreeRows = tree;
                if (countRows("VENTA", 1) !== 2 || countRows("VENDIDO", 0) !== 1) {
                    throw new Error("VENTA o VENDIDO no llegaron");
                }
            },
        },
        {
            content: "Una fila de VENTA cambiada a mano queda desmarcada",
            trigger: "body",
            run: () => {
                const model = sheetModel();
                const sheetId = model.getters.getSheetIdByName("VENTA");
                model.dispatch("UPDATE_CELL", { sheetId, col: 2, row: 1, content: "1234" });
            },
        },
        ...openBring,
        {
            content: "Repetir: todo igual salvo lo editado",
            trigger: ".modal .o_construction_bring_preview td:contains('VENTA')",
            timeout: 30000,
            run: () => {
                const row = [...document.querySelectorAll(".modal .o_construction_bring_preview tbody tr")]
                    .find((tr) => tr.textContent.includes("VENTA"));
                const cells = row.querySelectorAll("td");
                if (cells[1].textContent.trim() !== "0" || cells[2].textContent.trim() !== "1") {
                    throw new Error(`VENTA: ${row.textContent}`);
                }
            },
        },
        { trigger: ".modal .o_construction_bring_confirm", run: "click" },
        {
            trigger: ".o_notification:contains('Venta traída a la hoja')",
            timeout: 60000,
        },
        {
            content: "No duplicó filas ni pisó lo editado",
            trigger: "body",
            timeout: 30000,
            run: () => {
                const tree = countRows("ARBOL", 3);
                if (tree !== window.alTreeRows) {
                    throw new Error(`ARBOL pasó de ${window.alTreeRows} a ${tree}`);
                }
                const getters = sheetModel().getters;
                const sheetId = getters.getSheetIdByName("VENTA");
                if (getters.getCell({ sheetId, col: 2, row: 1 })?.content !== "1234") {
                    throw new Error("Se pisó el precio editado a mano");
                }
            },
        },
        {
            content: "M117-22, punto 8: datos para las propuestas de tablero",
            trigger: "body",
            run: () => {
                const model = sheetModel();
                const getters = model.getters;
                const keys = (name) => {
                    const clave = getters.getSheetIdByName("_CLAVES");
                    const result = {};
                    for (let row = 1; row < getters.getNumberRows(clave); row++) {
                        if (getters.getEvaluatedCell({ sheetId: clave, col: 0, row }).value === name) {
                            result[getters.getEvaluatedCell({ sheetId: clave, col: 1, row }).value] =
                                getters.getEvaluatedCell({ sheetId: clave, col: 2, row }).value - 1;
                        }
                    }
                    return result;
                };
                const put = (name, row, values) => {
                    const sheetId = getters.getSheetIdByName(name);
                    const columns = keys(name);
                    for (const [key, content] of Object.entries(values)) {
                        model.dispatch("UPDATE_CELL", { sheetId, col: columns[key], row, content });
                    }
                };
                put("MODULOS", 1, { typology: "C01", code: "MA01", type: "Alto", ml_group: "Mueble alto" });
                put("PIEZAS", 1, { typology: "C01", module: "MA01", qty: "2", piece_type: "PUERTA" });
                put("PIEZAS", 2, { typology: "C01", module: "MA01", qty: "1", piece_type: "PUERTA" });
                put("PIEZAS", 3, { typology: "C01", module: "MA01", qty: "1", piece_type: "COSTADO" });
                const finish = getters.getSheetIdByName("ACABADOS DE OBRA");
                model.dispatch("UPDATE_CELL", { sheetId: finish, col: 6, row: 1, content: "TABLERO ROVERE" });
            },
        },
        { trigger: ".o-topbar-menu:contains('Planificación de obra')", run: "click" },
        { trigger: ".o-menu-item[data-name='construction_furniture_validate']", run: "click" },
        {
            content: "Propuestas agrupadas: las dos puertas juntas, R04 sin tablero avisa",
            trigger: ".modal .o_construction_board_preview td:contains('TABLERO ROVERE')",
            timeout: 60000,
            run: () => {
                const row = document.querySelector(".modal .o_construction_board_preview tbody tr");
                const cells = row.querySelectorAll("td");
                if (cells[cells.length - 1].textContent.trim() !== "2") {
                    throw new Error(`Piezas del grupo: ${row.textContent}`);
                }
                if (!document.querySelector(".modal .alert")?.textContent.includes("R04 sin tablero")) {
                    throw new Error("No avisó que R04 no tiene tablero");
                }
            },
        },
        { trigger: ".modal .o_construction_board_apply", run: "click" },
        {
            content: "Aplicar escribe el producto solo en las piezas de frentes",
            trigger: "body",
            timeout: 30000,
            run: async () => {
                const getters = sheetModel().getters;
                const sheetId = getters.getSheetIdByName("PIEZAS");
                const read = (row) => getters.getCell({ sheetId, col: 4, row })?.content;
                for (let attempt = 0; attempt < 40 && read(1) !== "TABLERO ROVERE"; attempt++) {
                    await new Promise((resolve) => setTimeout(resolve, 250));
                }
                if (read(1) !== "TABLERO ROVERE" || read(2) !== "TABLERO ROVERE") {
                    throw new Error(`Puertas: ${read(1)} / ${read(2)}`);
                }
                if (read(3)) {
                    throw new Error(`El costado no debía cambiar: ${read(3)}`);
                }
            },
        },
    ],
});

/** M117-16, puntos 3 y 5: al abrir, la versión nueva y lo que cambió en la cotización. */
registry.category("web_tour.tours").add("al_construction_sale_reopen", {
    steps: () => [
        {
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [sheet] = await env.services.orm.searchRead(
                    "documents.document",
                    [["construction_sheet_kind", "=", "sale"]],
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
            trigger: ".o_notification:contains('OBRA actualizada desde la cotización')",
            timeout: 60000,
        },
        {
            content: "OBRA tiene la versión, la fila de cambios y el proyecto nuevo",
            trigger: "body",
            run: () => {
                const getters = sheetModel().getters;
                const sheetId = getters.getSheetIdByName("OBRA");
                const read = (col, row) => getters.getCell({ sheetId, col, row })?.content;
                if (read(1, 3) !== "N2" || read(4, 1) !== "N2" || !read(3, 1)) {
                    throw new Error(`Versión: ${read(1, 3)} / ${read(4, 1)} / ${read(3, 1)}`);
                }
                if (read(1, 1) !== "Proyecto cambiado") {
                    throw new Error(`Proyecto: ${read(1, 1)}`);
                }
            },
        },
    ],
});
