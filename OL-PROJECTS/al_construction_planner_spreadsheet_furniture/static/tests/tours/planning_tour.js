import { registry } from "@web/core/registry";

/**
 * Paquete 1.16, bloque 4c (M113-07 a 11): con la obra en el planificador y el
 * mismo libro importado a la hoja, las fórmulas de INICIO, FICHA, PROGRAMA y
 * CONTROL dan las cifras de la obra.
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

function sheetModel() {
    const model = findModel(odoo.__WOWL_DEBUG__.root.__owl__);
    if (!model) {
        throw new Error("No se encontró la hoja abierta");
    }
    return model;
}

function position(ref) {
    const [, letters, digits] = /^([A-Z]+)(\d+)$/.exec(ref);
    let col = 0;
    for (const char of letters) {
        col = col * 26 + char.charCodeAt(0) - 64;
    }
    return { col: col - 1, row: Number(digits) - 1 };
}

function value(sheet, ref) {
    const model = sheetModel();
    const sheetId = model.getters.getSheetIdByName(sheet);
    return model.getters.getEvaluatedCell({ sheetId, ...position(ref) }).value;
}

function same(current, expected) {
    return typeof expected === "number"
        ? Math.abs(Number(current) - expected) < 0.001
        : String(current ?? "") === String(expected);
}

/**
 * Espera a que las celdas valgan lo esperado (las listas de Odoo cargan
 * después) y, si no, falla con todas las diferencias.
 */
async function expectValues(expectations) {
    let wrong = [];
    for (let attempt = 0; attempt < 80; attempt++) {
        wrong = expectations.filter(([sheet, ref, expected]) => !same(value(sheet, ref), expected));
        if (!wrong.length) {
            return;
        }
        await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error(
        wrong
            .map(([sheet, ref, expected]) => `${sheet}!${ref}: ${expected} ≠ ${value(sheet, ref)}`)
            .join(" | ")
    );
}

function activate(name) {
    const model = sheetModel();
    model.dispatch("ACTIVATE_SHEET", {
        sheetIdFrom: model.getters.getActiveSheetId(),
        sheetIdTo: model.getters.getSheetIdByName(name),
    });
}

const openMenu = [
    { trigger: ".o-topbar-menu:contains('Planificación de obra')", run: "click" },
];

registry.category("web_tour.tours").add("al_construction_furniture_planning", {
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
            content: "La hoja abre en INICIO",
            trigger: ".o-sheet-list .o-sheet.active:contains('INICIO')",
        },
        ...openMenu,
        { trigger: ".o-menu-item[data-name='construction_furniture_import']", run: "click" },
        {
            content: "Subir el libro",
            trigger: ".modal .o_field_binary input[type=file]:not(:visible)",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [attachment] = await env.services.orm.searchRead(
                    "ir.attachment",
                    [["name", "=", "al_sheet_planning_tour.xlsx"]],
                    ["datas"],
                    { limit: 1 }
                );
                const bytes = Uint8Array.from(atob(attachment.datas), (c) => c.charCodeAt(0));
                const file = new File([bytes], "obra_4c.xlsx", {
                    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                });
                const input = document.querySelector(".modal .o_field_binary input[type=file]");
                const transfer = new DataTransfer();
                transfer.items.add(file);
                input.files = transfer.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        { trigger: ".modal td:contains('ARBOL')" },
        { trigger: ".modal button[name='action_import']", run: "click" },
        { trigger: ".o_notification:contains('Importado de obra_4c.xlsx')" },
        {
            content: "INICIO: estado, indicadores y semáforo",
            trigger: "body",
            timeout: 30000,
            run: async () => {
                await expectValues([
                    ["INICIO", "B22", 3], // muebles (ambientes)
                    ["INICIO", "B23", 5], // módulos a armar, sin zócalo
                    ["INICIO", "B24", 3.3], // ML: 1.2 × 2 + 0.9
                    ["INICIO", "B25", 10], // piezas: 5 × 2
                    ["INICIO", "B26", 400], // materiales: 2 × 100 × 2
                    ["INICIO", "B12", "Listo"], // obra
                    ["INICIO", "B13", "Listo"], // árbol
                    ["INICIO", "B14", "Listo"], // tipologías
                    ["INICIO", "B16", "Falta"], // contratas
                    ["INICIO", "B17", "Falta"], // venta
                    ["INICIO", "G12", 3], // filas de ARBOL
                    ["INICIO", "B44", "Piso 2"],
                    ["INICIO", "D44", "Piso 2"],
                    ["INICIO", "E44", 1],
                    ["BOM", "B2", "T4C-MEL"], // código desde «nombre · unidad · código»
                    ["REFERENCIAS", "S2", "Material"],
                ]);
                if (!String(value("INICIO", "B7")).startsWith("Validada")) {
                    throw new Error(`Estado en INICIO: ${value("INICIO", "B7")}`);
                }
                activate("FICHA");
            },
        },
        ...openMenu,
        { trigger: ".o-menu-item[data-name='construction_card_next']", run: "click" },
        {
            content: "FICHA: la tipología con su controversia de ancho",
            trigger: "body",
            timeout: 30000,
            run: async () => {
                await expectValues([
                    ["FICHA", "B3", "C01"],
                    ["FICHA", "B8", 2],
                    ["FICHA", "B9", "Piso 2, Piso 3"],
                    ["FICHA", "B11", 2],
                    ["FICHA", "A27", "MB01"],
                    ["FICHA", "G27", "Controversia de ancho"],
                    ["FICHA", "G28", ""],
                ]);
                const model = sheetModel();
                model.dispatch("UPDATE_CELL", {
                    sheetId: model.getters.getSheetIdByName("PROGRAMA"),
                    ...position("B3"),
                    content: "2026-11-16",
                });
                activate("PROGRAMA");
            },
        },
        ...openMenu,
        { trigger: ".o-menu-item[data-name='construction_program_dates']", run: "click" },
        {
            content: "PROGRAMA: Inicio y Fin pasan a OBRA",
            trigger: ".o_notification:contains('OBRA: Inicio 2026-11-16')",
            timeout: 30000,
            run: async () => {
                await expectValues([
                    ["PROGRAMA", "B10", 2], // pisos
                    ["PROGRAMA", "C18", 1], // piso 2, semana 1: sub etapa 1
                ]);
            },
        },
        ...openMenu,
        { trigger: ".o-menu-item[data-name='construction_furniture_control']", run: "click" },
        {
            content: "CONTROL coincide con el planificador",
            trigger: ".o_notification:contains('CONTROL')",
            timeout: 30000,
            run: async () => {
                await expectValues([
                    ["CONTROL", "B3", "Coincide"],
                    ["CONTROL", "D7", 2.1],
                    ["CONTROL", "E7", 2],
                    ["CONTROL", "F7", 3],
                    ["CONTROL", "G7", 2.1],
                    ["CONTROL", "K8", "Coincide"],
                    ["CONTROL", "M3", 2],
                    ["CONTROL", "M4", 2],
                ]);
                const orm = odoo.__WOWL_DEBUG__.root.env.services.orm;
                for (let attempt = 0; attempt < 40; attempt++) {
                    const count = await orm.searchCount("spreadsheet.revision", [
                        ["res_model", "=", "documents.document"],
                        ["commands", "ilike", "2026-11-16"],
                    ]);
                    if (count) {
                        return;
                    }
                    await new Promise((resolve) => setTimeout(resolve, 250));
                }
                throw new Error("La hoja no guardó las fechas de OBRA");
            },
        },
    ],
});
