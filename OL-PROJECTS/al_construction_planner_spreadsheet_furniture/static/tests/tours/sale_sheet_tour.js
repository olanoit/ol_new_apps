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

function position(ref) {
    const [, letters, digits] = /^([A-Z]+)(\d+)$/.exec(ref);
    let col = 0;
    for (const char of letters) {
        col = col * 26 + char.charCodeAt(0) - 64;
    }
    return { col: col - 1, row: Number(digits) - 1 };
}

function write(sheet, rows, firstRow = 2) {
    const model = sheetModel();
    const sheetId = model.getters.getSheetIdByName(sheet);
    rows.forEach((values, rowIndex) => {
        Object.entries(values).forEach(([letter, content]) => {
            model.dispatch("UPDATE_CELL", {
                sheetId,
                ...position(`${letter}${firstRow + rowIndex}`),
                content: String(content),
            });
        });
    });
}

function value(sheet, ref) {
    const getters = sheetModel().getters;
    return getters.getEvaluatedCell({
        sheetId: getters.getSheetIdByName(sheet),
        ...position(ref),
    }).value;
}

const close = (a, b) => typeof a === "number" && Math.abs(a - b) < 0.006;
const same = (a, b) => (typeof b === "number" ? close(a, b) : a === b);

async function expectValues(expected) {
    let wrong = [];
    for (let attempt = 0; attempt < 80; attempt++) {
        wrong = expected.filter(([sheet, ref, target]) => !same(value(sheet, ref), target));
        if (!wrong.length) {
            return;
        }
        await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error(
        wrong.map(([s, r, t]) => `${s}!${r}: ${value(s, r)} ≠ ${t}`).join(" | ")
    );
}

/**
 * Paquete 1.17: los valores de la grabación y de la maqueta del requerimiento,
 * calculados por las fórmulas de la plantilla en el navegador.
 */
registry.category("web_tour.tours").add("al_construction_sale_sheet", {
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
            content: "El menú se llama Hoja de venta",
            trigger: ".o-topbar-menu:contains('Hoja de venta')",
        },
        {
            content: "Datos de la grabación: precios y metrado",
            trigger: "body",
            timeout: 60000,
            run: async () => {
                write("ACABADOS", [
                    { A: "R02", B: "Frentes", C: "Color RH" },
                    { A: "R04", B: "Interiores", C: "Color RH" },
                    { A: "R05", B: "Mobiliario fijo", C: "Color o maderado" },
                ], 3);
                write("ACABADOS", [{ J: "R04", K: "R02" }], 2); // Cocina
                write("ACABADOS", [{ J: "STD", K: "R02" }], 3); // Closet
                const rate = (A, B, C, D, E, F, G, H, J, I = "") => ({ A, B, C, D, E, F, G, H, I, J });
                write("TARIFARIO", [
                    rate("Cocina", "Mueble bajo", "ML", 0, "Ninguna", 345, "Sí", "Sí", "Mueble bajo"),
                    rate("Cocina", "Mueble alto", "ML", 70, "Alto", 320, "Sí", "Sí", "Mueble alto"),
                    rate("Cocina", "Sobre refrigeradora", "UND", 60, "Alto", 295, "Sí", "Sí", "Accesorio"),
                    rate("Cocina", "Tapa", "UND", 0, "Ninguna", 105, "No", "Sí", "Accesorio"),
                    rate("Closet", "Puerta", "UND", 240, "Alto", 380, "No", "Sí", "Accesorio"),
                    rate("Cocina", "Cocina por ML", "ML", 0, "Ninguna", 1200, "Sí", "Sí", "Global"),
                    rate("Lavandería", "Lavandería por costo estimado", "UND", 0, "Ninguna", 0, "No", "No", "Global", "Por costo"),
                ]);
                write("PRECIOS", [
                    { A: "Cocina", B: "Mueble bajo" },
                    { A: "Cocina", B: "Mueble alto", D: 77 },
                    { A: "Cocina", B: "Sobre refrigeradora", D: 43, G: 380 },
                    { A: "Cocina", B: "Tapa", F: "R04" },
                    { A: "Closet", B: "Puerta", D: 230, F: "R05", G: 400 },
                    { A: "Cocina", B: "Cocina por ML" },
                    { A: "Lavandería", B: "Lavandería por costo estimado", I: 900 },
                ]);
                // Sin factor: el ítem por costo aún no tiene precio. Con factor 1.5:
                const model = sheetModel();
                const parameters = model.getters.getSheetIdByName("PARAMETROS");
                for (let row = 1; row < 40; row++) {
                    const key = model.getters.getCell({ sheetId: parameters, col: 6, row })?.content;
                    if (key === "factor_costo") {
                        model.dispatch("UPDATE_CELL", { sheetId: parameters, col: 2, row, content: "1.5" });
                        model.dispatch("UPDATE_CELL", { sheetId: parameters, col: 7, row, content: "Prueba" });
                    }
                }
                write("EDIFICIO", [
                    { B: 2, C: 17, D: 1, F: "Departamento", G: "Cocina", H: "C01" },
                    { G: "Closet dormitorio secundario", H: "CL01" },
                    { B: 17, C: 17, D: 2, E: 2, F: "Departamento", G: "Closet dormitorio principal", H: "CL05" },
                    { B: "Azotea", C: "Azotea", D: 1, F: "Departamento", G: "Baño principal", H: "B01" },
                ]);
                write("METRADO", [
                    { A: "C01", B: "Cocina dpto 201", C: "Cocina", D: "Mueble bajo", E: "=1.27+1.27+0.34+1.45" },
                    { D: "Mueble alto 77 cm", E: 3.09, F: 4.24 },
                ]);
                await expectValues([
                    ["PRECIOS", "P2", 625],
                    ["PRECIOS", "P3", 635],
                    ["PRECIOS", "M3", 352],
                    ["PRECIOS", "P4", 385],
                    ["PRECIOS", "Q4", 380],
                    ["PRECIOS", "P5", 150],
                    ["PRECIOS", "P6", 405],
                    ["PRECIOS", "Q6", 400],
                    ["PRECIOS", "J3", "Mueble alto 77 cm"],
                    ["PRECIOS", "P7", 2160],
                    ["PRECIOS", "P8", 1350],
                    ["EDIFICIO", "J2", 16],
                    ["EDIFICIO", "K2", 201],
                    ["EDIFICIO", "L2", 1701],
                    ["EDIFICIO", "N3", ""],
                    ["EDIFICIO", "K3", 201],
                    ["EDIFICIO", "K4", 1702],
                    ["EDIFICIO", "K5", "AZ01"],
                    ["EDIFICIO", "T1", 16],
                    ["METRADO", "K2", 4.33],
                    ["METRADO", "K3", 4.24],
                    ["METRADO", "O3", "Vale la del plano"],
                    ["METRADO", "S3", 4.33],
                    ["METRADO", "T3", 4.24],
                    ["METRADO", "W3", 16],
                    ["EDIFICIO", "M3", "Tipología sin metrado"],
                ]);
            },
        },
        {
            content: "Un rango que se cruza se marca al escribirlo",
            trigger: "body",
            timeout: 60000,
            run: async () => {
                write("EDIFICIO", [{ B: 10, C: 12, D: 1, F: "Departamento", G: "Cocina", H: "C01" }], 6);
                await expectValues([["EDIFICIO", "M6", "Se cruza con otra fila"]]);
            },
        },
        {
            content: "RESUMEN VENTA: subtotal, IGV y total, y el descuento",
            trigger: "body",
            timeout: 60000,
            run: async () => {
                // Solo C01 en el edificio: se quita el cruce para no contarlo.
                write("EDIFICIO", [{ B: "", C: "", D: "", F: "", G: "", H: "" }], 6);
                write("OBRA", [{ B: 10000 }], 14);
                const subtotal = 16 * (4.33 * 625 + 4.24 * 635);
                const net = subtotal - 10000;
                await expectValues([
                    ["RESUMEN VENTA", "A12", "Cocina"],
                    ["RESUMEN VENTA", "C34", net],
                    ["RESUMEN VENTA", "C35", net * 0.18],
                    ["RESUMEN VENTA", "C36", net * 1.18],
                    ["METRADO", "V3", 4.33 * 625 + 4.24 * 635],
                ]);
            },
        },
        {
            content: "Traer tarifario lista los ítems y agrega los marcados",
            trigger: ".o-topbar-menu:contains('Hoja de venta')",
            run: "click",
        },
        {
            trigger: ".o-menu-item[data-name='construction_sale_rates']",
            run: "click",
        },
        {
            trigger: ".modal .o_construction_rates_preview td:contains('Panel del catálogo')",
        },
        {
            trigger: ".modal .o_rates_apply",
            run: "click",
        },
        {
            trigger: ".o_notification:contains('Tarifario actualizado')",
            timeout: 30000,
        },
        {
            content: "El ítem nuevo del catálogo llegó, y el escrito a mano se conserva",
            trigger: "body",
            timeout: 60000,
            run: async () => {
                await expectValues([
                    ["TARIFARIO", "B9", "Panel del catálogo"],
                    ["TARIFARIO", "K9", "Vigente"],
                    ["TARIFARIO", "B2", "Mueble bajo"],
                    ["TARIFARIO", "K2", "Fuera del tarifario"],
                ]);
            },
        },
        {
            content: "Copiar tipología sugiere el siguiente código",
            trigger: ".o-topbar-menu:contains('Hoja de venta')",
            run: "click",
        },
        {
            trigger: ".o-menu-item[data-name='construction_sale_copy']",
            run: "click",
        },
        {
            trigger: ".modal input.o_copy_code",
            run: () => {
                if (document.querySelector(".modal input.o_copy_code").value !== "C02") {
                    throw new Error("No sugirió C02");
                }
            },
        },
        {
            trigger: ".modal .o_copy_confirm",
            run: "click",
        },
        {
            content: "La copia agrega las filas y no cambia las de C01",
            trigger: "body",
            timeout: 60000,
            run: async () => {
                await expectValues([
                    ["METRADO", "A4", "C02"],
                    ["METRADO", "H5", "C02"],
                    ["METRADO", "D4", "Mueble bajo"],
                    ["METRADO", "A2", "C01"],
                    ["METRADO", "H3", "C01"],
                ]);
            },
        },
        {
            content: "Pasar el resumen: la vista previa lista las partidas",
            trigger: ".o-topbar-menu:contains('Hoja de venta')",
            run: "click",
        },
        {
            trigger: ".o-menu-item[data-name='construction_sale_pass']",
            run: "click",
        },
        {
            content: "Los errores de validación lo impiden: CL01 no tiene metrado",
            trigger: ".o-sheet.active:contains('ERRORES')",
            timeout: 30000,
        },
        {
            content: "Se quita lo que falta y vuelve a intentar",
            trigger: "body",
            run: async () => {
                write("EDIFICIO", [
                    { G: "", H: "" },
                    { B: "", C: "", D: "", E: "", F: "", G: "", H: "" },
                    { B: "", C: "", D: "", F: "", G: "", H: "" },
                ], 3);
                await expectValues([["EDIFICIO", "M2", ""]]);
            },
            timeout: 60000,
        },
        {
            trigger: ".o-topbar-menu:contains('Hoja de venta')",
            run: "click",
        },
        {
            trigger: ".o-menu-item[data-name='construction_sale_pass']",
            run: "click",
        },
        {
            trigger: ".modal .o_construction_pass_preview td:contains('Cocina · C01')",
            timeout: 30000,
        },
        {
            trigger: ".modal .o_construction_pass_confirm",
            run: "click",
        },
        {
            trigger: ".o_notification:contains('La cotización tiene las líneas de la hoja')",
            timeout: 30000,
        },
        {
            content: "INICIO dice lo que falta",
            trigger: "body",
            timeout: 60000,
            run: async () => {
                await expectValues([
                    ["INICIO", "D13", "Listo"],
                    ["INICIO", "D15", "Listo"],
                ]);
            },
        },
    ],
});
