import { registry } from "@web/core/registry";

/**
 * Paquete 1.16, bloque 4c (M113-08): el panel Planificación agrupa ARBOL por
 * piso, copia el piso 2 a los pisos 3 y 4, numera los ambientes repetidos,
 * asigna una tipología, crea una variante y reemplaza un material.
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

function sheetId(name) {
    return sheetModel().getters.getSheetIdByName(name);
}

function header(name, text) {
    const model = sheetModel();
    const id = sheetId(name);
    for (let col = 0; col < model.getters.getNumberCols(id); col++) {
        if (model.getters.getEvaluatedCell({ sheetId: id, col, row: 0 }).value === text) {
            return col;
        }
    }
    throw new Error(`${name} no tiene la columna ${text}`);
}

/** Valores de una columna de la pestaña, sin el encabezado ni los vacíos. */
function columnOf(name, text) {
    const model = sheetModel();
    const id = sheetId(name);
    const col = header(name, text);
    const values = [];
    for (let row = 1; row < model.getters.getNumberRows(id); row++) {
        const value = model.getters.getEvaluatedCell({ sheetId: id, col, row }).value;
        if (value !== null && value !== undefined && value !== "") {
            values.push(value);
        }
    }
    return values;
}

function select(name, col, row) {
    const model = sheetModel();
    const from = model.getters.getActiveSheetId();
    if (from !== sheetId(name)) {
        model.dispatch("ACTIVATE_SHEET", { sheetIdFrom: from, sheetIdTo: sheetId(name) });
    }
    model.selection.selectCell(col, row);
}

async function waitFor(check) {
    let last = "";
    for (let attempt = 0; attempt < 80; attempt++) {
        last = check();
        if (!last) {
            return;
        }
        await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error(last);
}

const openMenu = [
    { trigger: ".o-topbar-menu:contains('Planificación de obra')", run: "click" },
];

registry.category("web_tour.tours").add("al_construction_furniture_panel", {
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
        { trigger: ".o-sheet-list .o-sheet.active:contains('INICIO')" },
        ...openMenu,
        { trigger: ".o-menu-item[data-name='construction_furniture_import']", run: "click" },
        {
            content: "Subir el libro",
            trigger: ".modal .o_field_binary input[type=file]:not(:visible)",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [attachment] = await env.services.orm.searchRead(
                    "ir.attachment",
                    [["name", "=", "al_sheet_panel_tour.xlsx"]],
                    ["datas"],
                    { limit: 1 }
                );
                const bytes = Uint8Array.from(atob(attachment.datas), (c) => c.charCodeAt(0));
                const file = new File([bytes], "panel.xlsx", {
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
        { trigger: ".o_notification:contains('Importado de panel.xlsx')" },
        {
            content: "ARBOL agrupado por piso, con su fila de resumen",
            trigger: "body",
            timeout: 30000,
            run: async () => {
                await waitFor(() => {
                    const summary = columnOf("ARBOL", "Resumen del piso");
                    const groups = sheetModel().getters.getHeaderGroups(sheetId("ARBOL"), "ROW");
                    return summary.length === 1 &&
                        String(summary[0]).startsWith("Piso 2 · 4 ambientes") &&
                        groups.length === 1
                        ? ""
                        : `Resumen ${summary.join(" / ")}, grupos ${groups.length}`;
                });
                // La primera fila de datos del piso 2 (la 2 es el resumen).
                select("ARBOL", 0, 2);
            },
        },
        ...openMenu,
        { trigger: ".o-menu-item[data-name='construction_furniture_panel']", run: "click" },
        { trigger: ".o-al-planning:contains('Indicadores de Piso 2')" },
        {
            trigger: ".o-al-planning input[placeholder^='Pisos de destino']",
            run: "edit 3-4",
        },
        { trigger: ".o-al-planning button:contains('Copiar piso')", run: "click" },
        { trigger: ".o_notification:contains('8 ambientes nuevos')", timeout: 30000 },
        {
            content: "Pisos 3 y 4 con sus dptos 301 y 401, y agrupados",
            trigger: "body",
            timeout: 30000,
            run: async () => {
                await waitFor(() => {
                    const apartments = columnOf("ARBOL", "Departamento").map(String);
                    const groups = sheetModel().getters.getHeaderGroups(sheetId("ARBOL"), "ROW");
                    return apartments.includes("301") &&
                        apartments.includes("402") &&
                        apartments.length === 12 &&
                        groups.length === 3
                        ? ""
                        : `Dptos ${apartments.join(",")}, grupos ${groups.length}`;
                });
            },
        },
        { trigger: ".o-al-planning button:contains('Numerar ambientes repetidos')", run: "click" },
        { trigger: ".o_notification:contains('6 ambientes numerados')", timeout: 30000 },
        {
            content: "Elegir la fila del «Closet 2» del piso 2",
            trigger: "body",
            run: async () => {
                const model = sheetModel();
                const id = sheetId("ARBOL");
                const col = header("ARBOL", "Ambiente");
                for (let row = 1; row < model.getters.getNumberRows(id); row++) {
                    if (model.getters.getEvaluatedCell({ sheetId: id, col, row }).value === "Closet 2") {
                        select("ARBOL", col, row);
                        return;
                    }
                }
                throw new Error("No se numeraron los closets");
            },
        },
        { trigger: ".o-al-planning select:has(option[value='CL01'])", run: "select CL01" },
        {
            trigger: ".o-al-planning button:contains('Asignar a las filas seleccionadas')",
            run: "click",
        },
        { trigger: ".o_notification:contains('Tipología CL01 en 1 ambientes')", timeout: 30000 },
        {
            content: "TIPOLOGIAS: la fila de C01",
            trigger: "body",
            run: () => select("TIPOLOGIAS", 0, 1),
        },
        { trigger: ".o-al-planning:contains('Crear variante de C01')" },
        { trigger: ".o-al-planning button:contains('Crear variante')", run: "click" },
        { trigger: ".o_notification:contains('Variante C01A creada')", timeout: 30000 },
        {
            content: "La variante está en TIPOLOGIAS, MODULOS y BOM",
            trigger: "body",
            timeout: 30000,
            run: async () => {
                await waitFor(() => {
                    const typologies = columnOf("TIPOLOGIAS", "Código");
                    const variantOf = columnOf("TIPOLOGIAS", "Variante de");
                    const modules = columnOf("MODULOS", "Tipología");
                    const bom = columnOf("BOM", "Tipología");
                    return typologies.includes("C01A") &&
                        variantOf.includes("C01") &&
                        modules.includes("C01A") &&
                        bom.includes("C01A")
                        ? ""
                        : `Tipologías ${typologies}, módulos ${modules}, BOM ${bom}`;
                });
                select("BOM", 0, 1);
            },
        },
        { trigger: ".o-al-planning input[placeholder='Material actual']", run: "edit T4C2-BLA" },
        {
            trigger: ".o-al-planning input[placeholder^='Material nuevo']",
            run: "edit T4C2-ROB",
        },
        { trigger: ".o-al-planning select:has(option[value='all'])", run: "select all" },
        { trigger: ".o-al-planning button:contains('Reemplazar')", run: "click" },
        {
            trigger: ".o_notification:contains('T4C2-BLA reemplazado por T4C2-ROB en 2 filas')",
            timeout: 30000,
        },
        {
            content: "BOM ya calcula el código nuevo",
            trigger: "body",
            timeout: 30000,
            run: async () => {
                await waitFor(() => {
                    const codes = columnOf("BOM", "Código del producto");
                    return codes.length === 2 && codes.every((code) => code === "T4C2-ROB")
                        ? ""
                        : `Códigos de BOM: ${codes.join(",")}`;
                });
            },
        },
    ],
});
