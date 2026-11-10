import { registry } from "@web/core/registry";

/**
 * Paquete 1.16, CR-22 g: en la hoja de presupuesto con el código al final y
 * la receta por nombre, las fórmulas dan el costo de la receta y ninguna
 * celda da error. CREVAL, paquete 5, CR-41: en PRESUPUESTO el APU se elige
 * por nombre y la especialidad sale del título de encima.
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

/** Columna (0 = A) del encabezado ``text`` en la fila 1 de la pestaña. */
function column(model, sheetId, text) {
    for (let col = 0; col < model.getters.getNumberCols(sheetId); col++) {
        if (model.getters.getEvaluatedCell({ sheetId, col, row: 0 }).value === text) {
            return col;
        }
    }
    throw new Error(`Falta la columna ${text}`);
}

function value(sheet, header, row) {
    const model = sheetModel();
    const sheetId = model.getters.getSheetIdByName(sheet);
    return model.getters.getEvaluatedCell({ sheetId, col: column(model, sheetId, header), row })
        .value;
}

/** Errores de fórmula (#NAME?, #ERROR, #REF…) en las pestañas del libro. */
function formulaErrors() {
    const model = sheetModel();
    const errors = [];
    for (const name of ["INSUMOS", "APU", "APU_DETALLE", "PRESUPUESTO"]) {
        const sheetId = model.getters.getSheetIdByName(name);
        for (const cellId of Object.keys(model.getters.getCells(sheetId))) {
            const position = model.getters.getCellPosition(cellId);
            const evaluated = model.getters.getEvaluatedCell(position);
            if (evaluated.type === "error" && position.row <= 5) {
                errors.push(`${name}!${position.col},${position.row}: ${evaluated.value}`);
            }
        }
    }
    return errors;
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

const near = (current, expected) => Math.abs(Number(current) - expected) < 0.001;

registry.category("web_tour.tours").add("al_construction_budget_formulas", {
    steps: () => [
        {
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [sheet] = await env.services.orm.searchRead(
                    "documents.document",
                    [["name", "=", "Presupuesto con el código al final (test)"]],
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
        { trigger: ".o-sheet-list .o-sheet:contains('APU_DETALLE')" },
        {
            content: "Receta, códigos, costo y banda de color",
            trigger: "body",
            timeout: 30000,
            run: async () => {
                await waitFor(() => {
                    const checks = [
                        ["APU", "Código", 1, "CR22G-R01"],
                        ["APU", "Para elegir", 1, "Muro CR-22 g (test) · CR22G-R01"],
                        ["APU_DETALLE", "Código de la receta", 1, "CR22G-R01"],
                        ["APU_DETALLE", "Tipo (calc.)", 1, "Mano de obra"],
                        ["APU_DETALLE", "Receta n.º (calc.)", 1, 1],
                    ];
                    const wrong = checks
                        .filter(([sheet, header, row, expected]) =>
                            typeof expected === "number"
                                ? !near(value(sheet, header, row), expected)
                                : value(sheet, header, row) !== expected
                        )
                        .map(([sheet, header, row, expected]) =>
                            `${sheet} ${header}: ${expected} ≠ ${value(sheet, header, row)}`
                        );
                    if (!near(value("APU", "Costo unitario", 1), 43.7838)) {
                        wrong.push(`APU Costo unitario: ${value("APU", "Costo unitario", 1)}`);
                    }
                    return [...wrong, ...formulaErrors()].join(" | ");
                });
                // CREVAL, paquete 5, CR-41: dos títulos y una partida con el
                // APU elegido por nombre; el código, el costo, la especialidad
                // y la sub-especialidad los calcula la hoja.
                const model = sheetModel();
                const sheetId = model.getters.getSheetIdByName("PRESUPUESTO");
                const write = (header, row, content) =>
                    model.dispatch("UPDATE_CELL", {
                        sheetId,
                        col: column(model, sheetId, header),
                        row,
                        content,
                    });
                write("Ítem", 1, "01");
                write("Partida", 1, "ARQUITECTURA");
                write("Ítem", 2, "01.01");
                write("Partida", 2, "MUROS");
                write("Ítem", 3, "01.0101");
                write("Partida", 3, "Muro de soga");
                write("Und", 3, "m2");
                write("Metrado", 3, "10");
                write("APU (escriba el nombre)", 3, "Muro CR-22 g (test) · CR22G-R01");
                await waitFor(() => {
                    const checks = [
                        ["Código del APU (calc.)", 3, "CR22G-R01"],
                        ["Especialidad", 3, "ARQUITECTURA"],
                        ["Sub-especialidad", 3, "MUROS"],
                        ["Especialidad", 2, "ARQUITECTURA"],
                        ["Sub-especialidad", 2, ""],
                        ["Estado", 1, "Título"],
                        ["Estado", 3, "OK"],
                    ];
                    const wrong = checks
                        .filter(([header, row, expected]) => value("PRESUPUESTO", header, row) !== expected)
                        .map(([header, row, expected]) =>
                            `PRESUPUESTO ${header} ${row}: ${expected} ≠ ${value("PRESUPUESTO", header, row)}`
                        );
                    const cost = value("PRESUPUESTO", "Costo unitario", 3);
                    if (!near(cost, 43.7838)) {
                        wrong.push(`PRESUPUESTO: costo ${cost}`);
                    }
                    return [...wrong, ...formulaErrors()].join(" | ");
                });
            },
        },
    ],
});
