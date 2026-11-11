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

/** Filas de resumen por piso de ARBOL (M113-08, punto 4). */
const summaryRows = () => {
    const getters = findModel(odoo.__WOWL_DEBUG__.root.__owl__).getters;
    const sheetId = getters.getSheetIdByName("ARBOL");
    let col = -1;
    for (let c = 0; c < getters.getNumberCols(sheetId); c++) {
        if (getters.getCell({ sheetId, col: c, row: 0 })?.content === "Resumen del piso") {
            col = c;
        }
    }
    let count = 0;
    for (let row = 1; col >= 0 && row < getters.getNumberRows(sheetId); row++) {
        if (getters.getCell({ sheetId, col, row })?.content) {
            count++;
        }
    }
    return count;
};

/**
 * Un paso de tour no espera más de 60 s. Este paso espera hasta 55 s a que
 * se cumpla la condición y sigue aunque no se cumpla: encadenado antes del
 * paso real, alarga la espera de las cargas lentas.
 */
const waitLonger = (done) => ({
    trigger: "body",
    timeout: 60000,
    run: async () => {
        const end = performance.now() + 55000;
        while (!done() && performance.now() < end) {
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
    },
});

const labelHas = (text) => () =>
    document.querySelector(".o_construction_progress_label")?.textContent.includes(text);

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
        // Antes amplía la hoja vacía a 1,650 filas: unos 85,000 comandos con
        // la plantilla vigente, unos 50 s.
        waitLonger(labelHas("ARBOL")),
        waitLonger(labelHas("ARBOL")),
        {
            content: "El cuadro muestra la pestaña y las filas",
            trigger: ".o_construction_progress_label:contains('ARBOL')",
            timeout: 60000,
            run: () => console.log(`AL_PERF ampliar: ${Math.round(performance.now() - window.alImportStart)} ms`),
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
                // La ampliación evalúa la hoja una sola vez, al final: las
                // fórmulas de las filas nuevas ya tienen su valor (G repite el
                // piso de B cuando A está vacía).
                const getters = findModel(odoo.__WOWL_DEBUG__.root.__owl__).getters;
                const sheetId = getters.getSheetIdByName("ARBOL");
                let evaluated = 0;
                for (let row = 1; row < getters.getNumberRows(sheetId); row++) {
                    const floor = getters.getCell({ sheetId, col: 1, row })?.content;
                    const value = getters.getEvaluatedCell({ sheetId, col: 6, row }).value;
                    if (floor && value === floor) {
                        evaluated++;
                    }
                }
                if (evaluated < 1500) {
                    throw new Error(`ARBOL tiene ${evaluated} filas calculadas`);
                }
            },
        },
        {
            content: "El nombre del módulo sale de la lista de su tipología",
            trigger: "body",
            run: () => {
                const model = findModel(odoo.__WOWL_DEBUG__.root.__owl__);
                const getters = model.getters;
                // {pestaña: {clave: columna}} de _CLAVES (columna desde 1).
                const keys = {};
                const keySheet = getters.getSheetIdByName("_CLAVES");
                for (let row = 1; row < getters.getNumberRows(keySheet); row++) {
                    const [sheet, key, col] = [0, 1, 2].map(
                        (c) => getters.getEvaluatedCell({ sheetId: keySheet, col: c, row }).value
                    );
                    if (sheet && key && typeof col === "number") {
                        (keys[sheet] = keys[sheet] || {})[key] = col - 1;
                    }
                }
                const put = (name, row, values) => {
                    const sheetId = getters.getSheetIdByName(name);
                    for (const [key, content] of Object.entries(values)) {
                        model.dispatch("UPDATE_CELL", { sheetId, col: keys[name][key], row, content });
                    }
                };
                const nameOf = (name) => {
                    const sheetId = getters.getSheetIdByName(name);
                    for (let col = 0; col < getters.getNumberCols(sheetId); col++) {
                        const header = getters.getEvaluatedCell({ sheetId, col, row: 0 }).value;
                        if (header === "Nombre del módulo (calc.)") {
                            return getters.getEvaluatedCell({ sheetId, col, row: 1 }).value;
                        }
                    }
                    throw new Error(`${name} sin «Nombre del módulo (calc.)»`);
                };
                put("TIPOLOGIAS", 1, { code: "TZ9" });
                // «M11» antes que «M*1»: el asterisco del código no es comodín.
                put("MODULOS", 1, { typology: "TZ9", code: "M11", name: "Otro" });
                put("MODULOS", 2, { typology: "TZ9", code: "M*1", name: "Bajo · cocina" });
                put("PIEZAS", 1, { typology: "TZ9", module: "M*1" });
                put("BOM", 1, { typology: "TZ9", module: "M11 · Otro" });
                const found = [nameOf("PIEZAS"), nameOf("BOM")];
                if (found[0] !== "Bajo · cocina" || found[1] !== "Otro") {
                    throw new Error(`Nombres del módulo: ${JSON.stringify(found)}`);
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
        {
            content: "Otra importación sobre la hoja agrupada por piso",
            trigger: "body",
            run: () => {
                if (summaryRows() !== 38) {
                    throw new Error(`ARBOL tiene ${summaryRows()} filas de resumen`);
                }
                document.querySelectorAll(".o_notification_close").forEach((b) => b.click());
            },
        },
        ...importSteps(),
        {
            content: "Reemplaza las filas y vuelve a agrupar, sin resúmenes de más",
            trigger: ".o_notification:contains('Importado de carga_grande.xlsx')",
            timeout: 60000,
            run: () => {
                console.log(`AL_PERF reimportar: ${Math.round(performance.now() - window.alImportStart)} ms`);
                if (treeRows() !== 1500 || summaryRows() !== 38) {
                    throw new Error(`ARBOL: ${treeRows()} filas y ${summaryRows()} resúmenes`);
                }
            },
        },
    ],
});
